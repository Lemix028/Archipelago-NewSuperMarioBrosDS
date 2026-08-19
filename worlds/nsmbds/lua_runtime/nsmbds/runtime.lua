-- =============================================================================
-- lua/nsmbds/runtime.lua
-- Initialization and persistent runtime state
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local context = state.context

function M.ensure_initialized()
    if context.is_initialized then return true end
    if not memory.is_rom_loaded() then return false end

    memory.domain = memory.detect_memory_domain()
    memory.sys_bus_domain = memory.detect_system_bus_domain()
    pcall(function() _G.memory.usememorydomain(memory.domain) end)

    addresses.resolve()

    pcall(_G.memory.writebyte, addresses.ADDR_AP_TRAP_TRIGGER, 0)
    if gui and gui.clearGraphics then gui.clearGraphics() end
    print("NSMBDS sideloading " .. constants.VERSION_LABEL .. " domain=" .. tostring(memory.domain))

    for index, counter_address in ipairs(addresses.ADDR_RED_COIN_COUNTERS) do
        local ok_count, count = pcall(_G.memory.readbyte, counter_address)
        context.red_coin_peak_latched[index] = ok_count and count ~= nil and count >= 8
    end

    context.is_initialized = true
    return true
end

return M
