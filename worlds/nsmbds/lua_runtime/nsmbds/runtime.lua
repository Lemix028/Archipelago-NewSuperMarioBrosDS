-- =============================================================================
-- lua/nsmbds/runtime.lua
-- Initialization and persistent runtime state
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local native_blocks = require("nsmbds.native_blocks")
local blocksanity = require("nsmbds.blocksanity")
local context = state.context
local incompatible_rom_reported = false

function M.ensure_initialized()
    if not memory.is_rom_loaded() then return false end
    -- A ROM switch can occur without a frame in the Null core. Do not carry
    -- queued deliveries into another seed merely because Lua stayed loaded.
    local rom_hash = gameinfo.getromhash()
    if context.initialized_rom_hash ~= rom_hash then
        context.is_initialized = false
        context.initialized_rom_hash = rom_hash
        incompatible_rom_reported = false
    end
    if context.is_initialized then return true end

    memory.domain = memory.detect_memory_domain()
    memory.sys_bus_domain = memory.detect_system_bus_domain()
    pcall(function() _G.memory.usememorydomain(memory.domain) end)

    addresses.resolve()

    if not native_blocks.is_ready() then
        if not incompatible_rom_reported then
            print("NSMBDS: Native block ROM patch required. Regenerate the seed patch with the current APWorld, cold-boot the new ROM, and do not load an old savestate.")
            incompatible_rom_reported = true
        end
        return false
    end
    incompatible_rom_reported = false
    blocksanity.initialize_delivery()

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
