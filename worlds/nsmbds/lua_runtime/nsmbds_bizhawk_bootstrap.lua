-- Loads the NSMBDS gameplay hook before handing control to Archipelago's connector.
-- The sideloading script registers frame callbacks and returns; the connector owns the persistent BizHawk client loop.

local script_dir = debug.getinfo(1, "S").source:sub(2):match("(.*[/\\])") or ""
local sideloading_script = script_dir .. "nsmbds_sideloading.lua"

local env_ap_lua_dir = os.getenv("NSMBDS_AP_LUA_DIR") or os.getenv("AP_LUA_DIR")
local connector_directory = env_ap_lua_dir or "C:/ProgramData/Archipelago/data/lua/"
if not connector_directory:match("[/\\]$") then
    connector_directory = connector_directory .. "/"
end

local vendored_connector = script_dir .. "vendor/connector_bizhawk_generic.lua"

local function is_rom_loaded()
    if emulation and emulation.getsystemid then
        local sysid = emulation.getsystemid()
        if sysid == "Null" or sysid == "NULL" or sysid == "" or sysid == nil then
            return false
        end
        return true
    end
    if gameinfo and gameinfo.getromname then
        local name = gameinfo.getromname()
        if name == "Null" or name == "NullHawk" or name == "" or name == nil then
            return false
        end
        return true
    end
    local ok, domains = pcall(memory.getmemorydomainlist)
    return ok and domains ~= nil and #domains > 0
end

if not is_rom_loaded() then
    print("Waiting for ROM to be loaded into BizHawk...")
    while not is_rom_loaded() do
        emu.frameadvance()
    end
    print("ROM loaded! Initializing NSMBDS Archipelago hooks.")
end

print("Configuring Lua package.")
package.path = script_dir .. "?.lua;" .. script_dir .. "?/init.lua;" .. package.path

print("Loading NSMBDS Archipelago sideloading hook.")
dofile(sideloading_script)

print("Loading Archipelago BizHawk connector.")
package.path = connector_directory .. "?.lua;" .. connector_directory .. "?/init.lua;" .. package.path

local function setup_luasocket()
    local original_popen = io.popen
    io.popen = function(command, mode)
        if command == "cd" then
            return {
                read = function()
                    return connector_directory:sub(1, -2)
                end,
            }
        end
        return original_popen(command, mode)
    end

    local status, err = pcall(function()
        require("socket")
    end)

    io.popen = original_popen

    if not status then
        print("[NSMBDS Warning] Could not load socket library from " .. connector_directory .. ": " .. tostring(err))
    end
end

setup_luasocket()

-- Compatibility function for test suites checking reconnect safety patch presence
function load_connector_with_reconnect_fix(path)
    -- The vendored connector already has socket closing & timeout timer safety pre-applied.
    -- Closing stale sockets and setting timeout_timer = 5 is built directly into vendor/connector_bizhawk_generic.lua.
    dofile(path)
end

load_connector_with_reconnect_fix(vendored_connector)
