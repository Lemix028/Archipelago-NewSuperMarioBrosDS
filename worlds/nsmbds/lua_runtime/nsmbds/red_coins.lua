-- ROM-native Red Coin completion queue -> the existing Lua/AP mailbox.
local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local UINT32 = 0x100000000
local last_overflow = 0

function M.is_native_ready()
    local producer = memory.to_domain_addr(constants.SYS_NATIVE_RED_COIN_PRODUCER)
    return _G.memory.read_u32_le(producer) == constants.NATIVE_RED_COIN_MAGIC
        and _G.memory.read_u32_le(producer + 4) == constants.NATIVE_RED_COIN_VERSION
end

function M.clear_invalid_pending_red_coin_event()
    local sequence = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE)
    local acknowledged = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE)
    if sequence == acknowledged then return end

    local event_type = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_TYPE)
    local world = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_WORLD)
    local level = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_LEVEL)
    local area = _G.memory.read_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_AREA)
    if event_type ~= constants.AP_EVENT_TYPE_RED_COIN_COMPLETE
        or world > 7 or level > 0x20 or area > 0xFF then
        _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, sequence)
    end
end

function M.poll_native_red_coin_completion()
    if not M.is_native_ready() then return false end
    local producer = memory.to_domain_addr(constants.SYS_NATIVE_RED_COIN_PRODUCER)
    local consumer = memory.to_domain_addr(constants.SYS_NATIVE_RED_COIN_CONSUMER)
    local records = memory.to_domain_addr(constants.SYS_NATIVE_RED_COIN_RECORDS)
    local write_sequence = _G.memory.read_u32_le(producer + 8)
    local read_sequence = _G.memory.read_u32_le(consumer)
    local overflow = _G.memory.read_u32_le(producer + 12)
    if overflow ~= last_overflow then
        last_overflow = overflow
        if overflow ~= 0 then
            print("NSMBDS Red Coin native queue overflowed by " .. tostring(overflow)
                .. " event(s). Keep the Lua script running while playing.")
        end
    end
    local count = (write_sequence - read_sequence) % UINT32
    if count > constants.NATIVE_RED_COIN_CAPACITY then
        error("Invalid Red Coin native queue cursors; cold-boot the patched ROM.")
    end
    for _ = 1, count do
        local ap_sequence = _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE)
        if ap_sequence ~= _G.memory.readbyte(addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE) then
            return true -- the AP client still owns the previous mailbox event
        end
        local slot = records + (read_sequence % constants.NATIVE_RED_COIN_CAPACITY)
            * constants.NATIVE_RED_COIN_RECORD_SIZE
        local world = _G.memory.readbyte(slot)
        local level = _G.memory.readbyte(slot + 1)
        local area = _G.memory.readbyte(slot + 2)
        local counter = _G.memory.readbyte(slot + 3)
        local player_x = _G.memory.read_s32_le(slot + 4)
        if _G.memory.read_u32_le(slot + 8) ~= read_sequence
            or world > 7 or level > constants.MAX_RUNTIME_COURSE_LEVEL
            or area == 0xFF or counter < 1 or counter > 2 then
            error("Incomplete Red Coin native event; retaining it for the next frame.")
        end

        local next_ap_sequence = (ap_sequence + 1) % 256
        _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_TYPE,
            constants.AP_EVENT_TYPE_RED_COIN_COMPLETE)
        _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_WORLD, world)
        _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_LEVEL, level)
        _G.memory.write_u32_le(addresses.ADDR_AP_RED_COIN_EVENT_AREA, area)
        _G.memory.write_s32_le(addresses.ADDR_AP_RED_COIN_EVENT_PLAYER_X, player_x)
        _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_COUNTER, counter)
        _G.memory.writebyte(addresses.ADDR_AP_RED_COIN_EVENT_SEQUENCE, next_ap_sequence)
        -- The durable AP mailbox now owns the event. A duplicate after a
        -- savestate/rewind is safe: AP location checks are idempotent.
        read_sequence = (read_sequence + 1) % UINT32
        _G.memory.write_u32_le(consumer, read_sequence)
    end
    return true
end

return M
