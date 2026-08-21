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

function M.disable_change_tile_execute_hook()
    if not context.change_tile_execute_hook_initialized
        and not context.change_tile_execute_hook_attempted then
        return
    end
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, "nsmbds_change_tile_execute")
    end
    context.change_tile_execute_hook_initialized = false
    context.change_tile_execute_hook_attempted = false
end

function M.disable_hit_block_execute_hook()
    if not context.hit_block_execute_hook_initialized
        and not context.hit_block_execute_hook_attempted then
        return
    end
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, "nsmbds_hit_block_execute")
    end
    context.hit_block_execute_hook_initialized = false
    context.hit_block_execute_hook_attempted = false
end

function M.record_native_tile_change()
    if context.ground_pound_hook_armed_frames <= 0 then
        return
    end
    local pos_x = memory.read_arm9_register("R1")
    local pos_y = memory.read_arm9_register("R2")
    local mode = memory.read_arm9_register("R3")
    if pos_x == nil or pos_y == nil then
        return
    end
    local frame = emu and emu.framecount and emu.framecount() or 0
    local write_index = context.native_tile_change_write_index
    context.native_tile_changes[write_index] = {
        frame = frame,
        pos_x = pos_x,
        pos_y = pos_y,
        mode = mode or 0,
    }
    context.native_tile_change_write_index = write_index % 64 + 1
end

function M.ensure_change_tile_execute_hook()
    if context.change_tile_execute_hook_initialized or context.change_tile_execute_hook_attempted then
        return
    end
    context.change_tile_execute_hook_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if not on_execute or not emu or not emu.getregister then
        return
    end
    local scope = memory.sys_bus_domain or memory.domain
    local hook_address = memory.sys_bus_domain and constants.SYS_CHANGE_TILE_FUNCTION
        or memory.to_domain_addr(constants.SYS_CHANGE_TILE_FUNCTION)
    local ok, hook_id = pcall(
        on_execute,
        M.record_native_tile_change,
        hook_address,
        "nsmbds_change_tile_execute",
        scope
    )
    context.change_tile_execute_hook_initialized = ok and hook_id ~= nil
    if not context.change_tile_execute_hook_initialized then
        print("NSMBDS native changeTile hook registration failed; using Actor fallback.")
    end
end

function M.record_native_block_hit()
    if context.ground_pound_hook_armed_frames > 0 then
        local frame = emu and emu.framecount and emu.framecount() or 0
        local write_index = context.native_block_hit_write_index
        context.native_block_hits[write_index] = {
            frame = frame,
            consumed = false,
        }
        context.native_block_hit_write_index = write_index % 64 + 1
    end

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

function M.ensure_hit_block_execute_hook()
    if context.hit_block_execute_hook_initialized or context.hit_block_execute_hook_attempted then
        return
    end
    context.hit_block_execute_hook_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if not on_execute then
        print("NSMBDS native hitBlock hook unavailable; using position fallback.")
        return
    end
    local scope = memory.sys_bus_domain or memory.domain
    local hook_address = memory.sys_bus_domain and constants.SYS_HIT_BLOCK_FUNCTION
        or memory.to_domain_addr(constants.SYS_HIT_BLOCK_FUNCTION)
    local ok, hook_id = pcall(
        on_execute,
        M.record_native_block_hit,
        hook_address,
        "nsmbds_hit_block_execute",
        scope
    )
    context.hit_block_execute_hook_initialized = ok and hook_id ~= nil
    if not context.hit_block_execute_hook_initialized then
        print("NSMBDS native hitBlock hook registration failed; using position fallback.")
    end
end

return M
