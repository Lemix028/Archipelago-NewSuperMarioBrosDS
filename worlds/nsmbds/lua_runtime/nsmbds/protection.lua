-- =============================================================================
-- lua/nsmbds/protection.lua
-- Life Insurance handling
-- =============================================================================

local M = {}
local addresses = require("nsmbds.addresses")
local constants = require("nsmbds.constants")
local state = require("nsmbds.state")
local context = state.context

function M.poll_life_insurance()
    if context.life_insurance_write_guard then return end

    local current = _G.memory.readbyte(addresses.ADDR_LIVES)
    local previous = context.last_observed_lives
    if previous == nil or not context.previous_frame_had_player or current >= previous then
        context.last_observed_lives = current
        return
    end

    -- Vanilla marks the pause-menu "Return to Map" path separately from an
    -- actual death. It can still lower the life counter, but must not consume
    -- Life Insurance or publish an insured-death event.
    local exit_flags = _G.memory.readbyte(addresses.ADDR_STAGE_EXIT_FLAGS)
    if math.floor(exit_flags / constants.STAGE_EXIT_RETURN_TO_MAP_MASK) % 2 == 1 then
        context.last_observed_lives = current
        return
    end

    local charges = state.notification_state.read(addresses.ADDR_AP_LIFE_INSURANCE_COUNT)
    if charges == nil or charges < 1 or charges > 99 then
        context.last_observed_lives = current
        return
    end

    context.life_insurance_write_guard = true
    context.last_observed_lives = previous
    state.notification_state.write(addresses.ADDR_AP_LIFE_INSURANCE_COUNT, charges - 1)
    local sequence = state.notification_state.read(addresses.ADDR_AP_INSURED_DEATH_SEQUENCE)
    state.notification_state.write(addresses.ADDR_AP_INSURED_DEATH_SEQUENCE, (sequence + 1) % 256)
    state.notification_state.snapshot_age = 3
    if gui and gui.clearGraphics then gui.clearGraphics() end
    context.last_drawn_insurance_count = nil

    _G.memory.writebyte(addresses.ADDR_LIVES, previous)
    context.life_insurance_write_guard = false
end

return M
