-- =============================================================================
-- lua/nsmbds/notifications.lua
-- Archipelago UI elements and notification state
-- =============================================================================

local M = {}
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")

function state.notification_state.read(address)
    return _G.memory.readbyte(address)
end

function state.notification_state.write(address, value)
    _G.memory.writebyte(address, value)
end

function state.notification_state.capture_snapshot(force)
    if not force and state.notification_state.snapshot ~= nil
        and state.notification_state.snapshot_age < 3 then
        state.notification_state.snapshot_age = state.notification_state.snapshot_age + 1
        return state.notification_state.snapshot
    end
    local values = {}
    for offset = 0, 8 do
        values[offset + 1] = _G.memory.readbyte(addresses.ADDR_AP_TRAP_SHIELD_COUNT + offset)
    end
    state.notification_state.snapshot = values
    state.notification_state.snapshot_age = 0
    return values
end

function state.notification_state.is_ready(snapshot)
    local values = snapshot or state.notification_state.capture_snapshot(true)
    return values ~= nil
        and values[1] ~= nil and values[1] >= 0 and values[1] <= 99
        and values[2] ~= nil and values[2] >= 0 and values[2] <= 99
end

function state.notification_state.duration(notification)
    if notification ~= nil
        and notification.kind == state.notification_state.kind.goal_complete then
        return state.notification_state.goal_duration_frames
    end
    return state.notification_state.default_duration_frames
end

function state.notification_state.receive(snapshot)
    if not state.notification_state.is_ready(snapshot) then
        state.notification_state.queue = {}
        state.notification_state.active = nil
        state.notification_state.remaining_frames = 0
        return
    end
    if #state.notification_state.queue >= state.notification_state.max_queue_size then
        return
    end

    local sequence = snapshot[6]
    local acknowledged = snapshot[9]
    if sequence == acknowledged then return end

    if state.notification_state.popup_disabled then
        -- The emulator feed remains active after release; only the temporary
        -- in-game popup mailbox is silenced once Goal Complete was shown.
        state.notification_state.write(state.notification_state.addr.acknowledged, sequence)
        snapshot[9] = sequence
        return
    end

    local received = {
        kind = snapshot[7],
        detail = snapshot[8],
    }
    if received.kind == state.notification_state.kind.trap_blocked then
        -- Shield feedback preempts filler notices but never discards them.
        if state.notification_state.active ~= nil then
            table.insert(state.notification_state.queue, 1, state.notification_state.active)
        end
        state.notification_state.active = received
        state.notification_state.duration_frames = state.notification_state.duration(received)
        state.notification_state.remaining_frames = state.notification_state.duration_frames
    else
        state.notification_state.queue[#state.notification_state.queue + 1] = received
    end
    -- Acknowledge only after the event is retained locally.
    state.notification_state.write(state.notification_state.addr.acknowledged, sequence)
    snapshot[9] = sequence
end




return M
