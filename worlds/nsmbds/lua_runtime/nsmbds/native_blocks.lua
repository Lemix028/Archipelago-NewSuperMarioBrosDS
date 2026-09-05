-- ROM-owned ring. Lua only writes the separate consumer cache line.
local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local UINT32 = 0x100000000
local reported_error = nil
local last_overflow = 0

function M.is_ready()
    local header = memory.to_domain_addr(constants.SYS_NATIVE_BLOCK_PRODUCER)
    return _G.memory.read_u32_le(header) == constants.NATIVE_BLOCK_MAGIC
        and _G.memory.read_u32_le(header + 4) == constants.NATIVE_BLOCK_VERSION
end

local function report(message)
    if reported_error ~= message then
        reported_error = message
        print("NSMBDS BLOCK ERROR: " .. message)
    end
end

function M.drain(accept)
    if not M.is_ready() then
        report("Native block ROM patch missing. Regenerate the patch and cold-boot the new ROM; do not load an old savestate.")
        return false
    end
    local producer = memory.to_domain_addr(constants.SYS_NATIVE_BLOCK_PRODUCER)
    local consumer = memory.to_domain_addr(constants.SYS_NATIVE_BLOCK_CONSUMER)
    local records = memory.to_domain_addr(constants.SYS_NATIVE_BLOCK_RECORDS)
    local write_sequence = _G.memory.read_u32_le(producer + 8)
    local read_sequence = _G.memory.read_u32_le(consumer)
    local overflow = _G.memory.read_u32_le(producer + 12)
    if overflow ~= last_overflow then
        last_overflow = overflow
        if overflow ~= 0 then
            report("Native ring overflow: " .. tostring(overflow)
                .. " hit(s) could not be buffered. Keep the Lua script running while playing.")
        end
    end
    local count = (write_sequence - read_sequence) % UINT32
    if count > constants.NATIVE_BLOCK_CAPACITY then
        report("Invalid native ring cursors; cold-boot the patched ROM. Unread records were not discarded.")
        return false
    end
    for _ = 1, count do
        local slot = records + (read_sequence % constants.NATIVE_BLOCK_CAPACITY)
            * constants.NATIVE_BLOCK_RECORD_SIZE
        if _G.memory.read_u32_le(slot + 12) ~= read_sequence then
            report("Incomplete native block record; retaining it for the next frame.")
            return false
        end
        local accepted = accept(
            _G.memory.readbyte(slot), _G.memory.readbyte(slot + 1),
            _G.memory.readbyte(slot + 2), _G.memory.readbyte(slot + 3),
            _G.memory.read_u32_le(slot + 4), _G.memory.read_s32_le(slot + 8)
        )
        if not accepted then return false end
        read_sequence = (read_sequence + 1) % UINT32
        -- Acknowledge only AFTER the delivery queue owns the complete event.
        -- Do not reset these cursors on area changes, reload or savestate load.
        _G.memory.write_u32_le(consumer, read_sequence)
    end
    return true
end

return M
