-- =============================================================================
-- lua/nsmbds/hooks.lua
-- Native ARM9 execution hooks
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local context = state.context

local NATIVE_BLOCK_HIT_BUFFER_SIZE = 64
local UINT32_MODULUS = 0x100000000
local HIT_BLOCK_TILE_HOOK_NAME = "nsmbds_hit_block_change_tile"
local HEAD_BONK_HOOK_NAME = "nsmbds_head_bonk_hit_block"
local LEGACY_HIT_BLOCK_ENTRY_HOOK_NAME = "nsmbds_hit_block_execute"
local LEGACY_HIT_BLOCK_TILE_HOOK_NAME_PREFIX = "nsmbds_hit_block_tile_"
local hit_block_change_tile_returns = {}
for _, return_address in ipairs(constants.SYS_HIT_BLOCK_CHANGE_TILE_RETURNS) do
    hit_block_change_tile_returns[return_address] = true
end

local function unsigned32(value)
    return value % UINT32_MODULUS
end

local function signed16(value)
    value = value % 0x10000
    if value >= 0x8000 then
        return value - 0x10000
    end
    return value
end

-- At changeTile entry, hitBlock has already converted its collision inputs.
-- R1 is exact tile X and R2 is exact tile Y, both u16.
local function hit_block_tile(register_x, register_y)
    return register_x % 0x10000, signed16(register_y)
end

local function native_hit_diagnostic_label(world, level, area, tile_x, tile_y)
    if world == 1 and level == 9 and area == 34 and tile_x == 140 then
        if tile_y == -16 then return "W2-A Block 6" end
        if tile_y == -25 then return "W2-A Block 7" end
    end
    return "-"
end

local function log_native_hit_registers(world, level, area, tile_x, tile_y)
    if not rawget(_G, "NSMBDS_NATIVE_HIT_DIAGNOSTICS") then
        return
    end
    local registers = {}
    for index = 0, 12 do
        registers[#registers + 1] = string.format(
            "R%d=%08X",
            index,
            unsigned32(memory.read_arm9_register("R" .. index) or 0)
        )
    end
    print(string.format(
        "NSMBDS HIT_BLOCK_REGS frame=%d world=%d level=0x%02X area=%d "
            .. "tile=(%d,%d) target=%s %s LR=%08X",
        emu and emu.framecount and emu.framecount() or 0,
        world,
        level,
        area,
        tile_x,
        tile_y,
        native_hit_diagnostic_label(world, level, area, tile_x, tile_y),
        table.concat(registers, " "),
        unsigned32(memory.read_arm9_register("LR") or 0)
    ))
end

function M.disable_hit_block_execute_hook()
    if not context.hit_block_execute_hook_initialized
        and not context.hit_block_execute_hook_attempted
        and not context.head_bonk_execute_hook_initialized
        and not context.head_bonk_execute_hook_attempted then
        return
    end
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, HIT_BLOCK_TILE_HOOK_NAME)
        pcall(event.unregisterbyname, HEAD_BONK_HOOK_NAME)
        pcall(event.unregisterbyname, LEGACY_HIT_BLOCK_ENTRY_HOOK_NAME)
        for index = 1, 4 do
            pcall(event.unregisterbyname, LEGACY_HIT_BLOCK_TILE_HOOK_NAME_PREFIX .. index)
        end
    end
    context.hit_block_execute_hook_initialized = false
    context.hit_block_execute_hook_attempted = false
    context.hit_block_execute_hook_usable = false
    context.head_bonk_execute_hook_initialized = false
    context.head_bonk_execute_hook_attempted = false
end

local function capture_native_block_hit()
    local return_address = memory.read_arm9_register("LR")
    if return_address == nil
        or not hit_block_change_tile_returns[unsigned32(return_address)] then
        return
    end
    local register_x = memory.read_arm9_register("R1")
    local register_y = memory.read_arm9_register("R2")
    if register_x == nil or register_y == nil then
        context.hit_block_execute_hook_usable = false
        if not context.hit_block_register_failure_logged then
            context.hit_block_register_failure_logged = true
            print("NSMBDS hitBlock tile hook cannot read ARM9 R1/R2; using Actor fallback.")
        end
    else
        local tile_x, tile_y = hit_block_tile(register_x, register_y)
        local world = _G.memory.readbyte(addresses.ADDR_CURRENT_WORLD_MAP)
        local level = _G.memory.readbyte(addresses.ADDR_CURRENT_COURSE_LEVEL)
        local area = _G.memory.readbyte(addresses.ADDR_CURRENT_COURSE_AREA)
        context.hit_block_execute_hook_usable = true

        local event_type = constants.AP_EVENT_TYPE_BLOCK_BUMP
        local player = state.input_trap_state.active_player
        if player ~= nil then
            local ground_pound_state = _G.memory.readbyte(memory.to_domain_addr(
                player + constants.PLAYER_GROUND_POUND_STATE_OFFSET
            ))
            if ground_pound_state == constants.PLAYER_GROUND_POUND_ACTIVE_STATE then
                event_type = constants.AP_EVENT_TYPE_BLOCK_GROUND_POUND
            end
        end

        if world <= 7
            and level <= constants.MAX_RUNTIME_COURSE_LEVEL
            and area ~= 0xFF then
            local hits = context.native_block_hits
            if #hits < NATIVE_BLOCK_HIT_BUFFER_SIZE then
                hits[#hits + 1] = {
                    event_type = event_type,
                    world = world,
                    level = level,
                    area = area,
                    tile_x = tile_x,
                    tile_y = tile_y,
                }
            elseif not context.native_block_hit_overflow_logged then
                context.native_block_hit_overflow_logged = true
                print("NSMBDS native block-hit buffer full; dropping additional hits this frame.")
            end
        end
        log_native_hit_registers(world, level, area, tile_x, tile_y)
    end
end

function M.record_native_block_tile()
    local capture_ok, capture_error = pcall(capture_native_block_hit)
    if not capture_ok then
        context.hit_block_execute_hook_usable = false
        if not context.hit_block_register_failure_logged then
            context.hit_block_register_failure_logged = true
            print("NSMBDS hitBlock capture failed; using Actor fallback: " .. tostring(capture_error))
        end
    end
end

function M.record_native_block_hit()
    local player = state.input_trap_state.active_player
    if context.active_mode == "head_bonk" and player ~= nil then
        local velocity = _G.memory.read_s32_le(memory.to_domain_addr(player + constants.PLAYER_Y_VELOCITY_OFFSET))
        local animation = _G.memory.readbyte(memory.to_domain_addr(player + constants.PLAYER_ANIMATION_OFFSET))
        if (velocity > 0 or state.input_trap_state.player_was_moving_up)
            and animation ~= constants.PLAYER_ANIMATION_GROUND_POUND_IMPACT then
            state.input_trap_state.player_was_moving_up = false
            state.input_trap_state.apply_action_damage(player)
        end
    end
end

function M.sync_head_bonk_execute_hook()
    local should_enable = context.active_mode == "head_bonk"
    if not should_enable then
        if context.head_bonk_execute_hook_initialized
            or context.head_bonk_execute_hook_attempted then
            if event and event.unregisterbyname then
                pcall(event.unregisterbyname, HEAD_BONK_HOOK_NAME)
            end
            context.head_bonk_execute_hook_initialized = false
            context.head_bonk_execute_hook_attempted = false
        end
        return
    end
    if context.head_bonk_execute_hook_initialized
        or context.head_bonk_execute_hook_attempted then
        return
    end
    context.head_bonk_execute_hook_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if not on_execute then
        return
    end
    local scope = memory.sys_bus_domain or memory.domain
    local hook_address = memory.sys_bus_domain and constants.SYS_HIT_BLOCK_FUNCTION
        or memory.to_domain_addr(constants.SYS_HIT_BLOCK_FUNCTION)
    local ok, hook_id = pcall(
        on_execute,
        M.record_native_block_hit,
        hook_address,
        HEAD_BONK_HOOK_NAME,
        scope
    )
    context.head_bonk_execute_hook_initialized = ok and hook_id ~= nil
end

function M.ensure_hit_block_execute_hook()
    if context.hit_block_execute_hook_initialized or context.hit_block_execute_hook_attempted then
        return
    end
    context.hit_block_execute_hook_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if not on_execute then
        print("NSMBDS native hitBlock hook unavailable; using Actor fallback.")
        return
    end
    -- Remove hook names used by earlier revisions in case BizHawk retained
    -- them across a hot reload.
    if event.unregisterbyname then
        pcall(event.unregisterbyname, HIT_BLOCK_TILE_HOOK_NAME)
        pcall(event.unregisterbyname, LEGACY_HIT_BLOCK_ENTRY_HOOK_NAME)
        for index = 1, 4 do
            pcall(event.unregisterbyname, LEGACY_HIT_BLOCK_TILE_HOOK_NAME_PREFIX .. index)
        end
    end
    local scope = memory.sys_bus_domain or memory.domain
    local hook_address = memory.sys_bus_domain and constants.SYS_CHANGE_TILE_FUNCTION
        or memory.to_domain_addr(constants.SYS_CHANGE_TILE_FUNCTION)
    local ok, hook_id = pcall(
        on_execute,
        M.record_native_block_tile,
        hook_address,
        HIT_BLOCK_TILE_HOOK_NAME,
        scope
    )
    context.hit_block_execute_hook_initialized = ok and hook_id ~= nil
    if not context.hit_block_execute_hook_initialized then
        print("NSMBDS native hitBlock hook registration failed; using Actor fallback.")
    end
end

M.hit_block_tile = hit_block_tile

return M
