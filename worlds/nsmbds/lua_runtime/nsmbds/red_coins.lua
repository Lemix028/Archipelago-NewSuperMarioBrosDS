-- =============================================================================
-- lua/nsmbds/red_coins.lua
-- Red coin completion detection and tracking
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local actors = require("nsmbds.actors")
local context = state.context

function M.clear_invalid_pending_red_coin_event()
    local sequence = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE)
    local acknowledged = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE)
    if sequence == acknowledged then
        return
    end

    local event_type = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_TYPE)
    local world = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_WORLD)
    local level = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_LEVEL)
    local area = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_AREA)
    if event_type ~= constants.AP_EVENT_TYPE_RED_COIN_COMPLETE
        or world > 7 or level > 0x20 or area > 0xFF then
        _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, sequence)
    end
end

function M.publish_pending_red_coin_completion()
    if context.pending_red_coin_completion == nil then
        return
    end
    local sequence = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE)
    local acknowledged = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE)
    if sequence ~= acknowledged then
        return
    end

    local next_sequence = (sequence + 1) % 256
    _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_TYPE, constants.AP_EVENT_TYPE_RED_COIN_COMPLETE)
    _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_WORLD, context.pending_red_coin_completion.world)
    _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_LEVEL, context.pending_red_coin_completion.level)
    _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_AREA, context.pending_red_coin_completion.area)
    _G.memory.write_s32_le(addresses.ADDR_AP_RED_COIN_EVENT_PLAYER_X, context.pending_red_coin_completion.player_x)
    _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_COUNTER, context.pending_red_coin_completion.counter)
    _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE, next_sequence)
    context.pending_red_coin_completion = nil
end

function M.observe_red_coin_counter(counter_index, value)
    if not memory.is_rom_loaded() then return end
    local counter_address = addresses.ADDR_RED_COIN_COUNTERS[counter_index]
    if counter_address == nil then return end
    local ok, count = pcall(function() return value or _G.memory.readbyte(counter_address) end)
    if not ok or count == nil then return end
    count = count % 256

    if count >= 8 and not context.red_coin_peak_latched[counter_index] then
        context.red_coin_peak_latched[counter_index] = true
        local world, level, area = actors.current_course_identity()
        local player_x = -1
        local player = state.input_trap_state.active_player
        if player ~= nil then
            player_x = actors.object_tile(player)
        end
        context.pending_red_coin_completion = {
            world = world,
            level = level,
            area = area,
            player_x = player_x,
            counter = counter_index,
        }
        M.publish_pending_red_coin_completion()
    elseif count < 8 then
        context.red_coin_peak_latched[counter_index] = false
    end
end

function M.ensure_red_coin_write_hook()
    if context.red_coin_write_hook_initialized then return end
    local on_write = event and (event.on_bus_write or event.onmemorywrite)
    if not on_write then return end

    local all_hooks_ready = true
    for index, domain_address in ipairs(addresses.ADDR_RED_COIN_COUNTERS) do
        local hook_name = "NSMBDS Red Coin Counter " .. tostring(index)
        if event.unregisterbyname then
            pcall(event.unregisterbyname, hook_name)
        end
        local counter_index = index
        local hook_address = memory.sys_bus_domain
            and constants.SYS_RED_COIN_COUNTERS[index]
            or domain_address
        local scope = memory.sys_bus_domain or memory.domain
        local ok, hook_id = pcall(
            on_write,
            function(_, value)
                if memory.is_rom_loaded() then
                    M.observe_red_coin_counter(counter_index, value)
                end
            end,
            hook_address,
            hook_name,
            scope
        )
        all_hooks_ready = all_hooks_ready and ok and hook_id ~= nil
    end
    context.red_coin_write_hook_initialized = all_hooks_ready
end

return M
