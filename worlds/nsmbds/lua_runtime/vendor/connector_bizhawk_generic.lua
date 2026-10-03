--[[
Copyright (c) 2023 Zunawe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Note: Vendored generic connector v1 for NSMBDS Archipelago with pre-applied
socket cleanup and reconnect safety fixes for BizHawk pause/resume cycles.
]]

local SCRIPT_VERSION = 1

-- Set to log incoming requests
-- Will cause lag due to large console output
local DEBUG = false

local bizhawk_version = client.getversion()
local bizhawk_major, bizhawk_minor, bizhawk_patch = bizhawk_version:match("(%d+)%.(%d+)%.?(%d*)")
bizhawk_major = tonumber(bizhawk_major)
bizhawk_minor = tonumber(bizhawk_minor)
if bizhawk_patch == "" then
    bizhawk_patch = 0
else
    bizhawk_patch = tonumber(bizhawk_patch)
end

local lua_major, lua_minor = _VERSION:match("Lua (%d+)%.(%d+)")
lua_major = tonumber(lua_major)
lua_minor = tonumber(lua_minor)

if lua_major > 5 or (lua_major == 5 and lua_minor >= 3) then
    require("lua_5_3_compat")
end

local base64 = require("base64")
local socket = require("socket")
local json = require("json")

local SOCKET_PORT_FIRST = 43055
local SOCKET_PORT_RANGE_SIZE = 5
local SOCKET_PORT_LAST = SOCKET_PORT_FIRST + SOCKET_PORT_RANGE_SIZE

local STATE_NOT_CONNECTED = 0
local STATE_CONNECTED = 1

local server = nil
local client_socket = nil

local current_state = STATE_NOT_CONNECTED

local timeout_deadline = 0
local message_timer = 0
local message_interval = 0
local prev_time = 0
local current_time = 0

local locked = false
local receive_buffer = ""
local pending_response = nil
local send_offset = 1
local stopped = false

local rom_hash = nil

local function queue_push (self, value)
    self[self.right] = value
    self.right = self.right + 1
end

local function queue_is_empty (self)
    return self.right == self.left
end

local function queue_shift (self)
    local value = self[self.left]
    self[self.left] = nil
    self.left = self.left + 1
    return value
end

local function new_queue ()
    local queue = {left = 1, right = 1}
    return setmetatable(queue, {__index = {is_empty = queue_is_empty, push = queue_push, shift = queue_shift}})
end

local message_queue = new_queue()

local function lock ()
    locked = true
    client_socket:settimeout(2)
end

local function unlock ()
    locked = false
    if client_socket ~= nil then client_socket:settimeout(0) end
end

local request_handlers = {
    ["PING"] = function (req)
        local res = {}

        res["type"] = "PONG"

        return res
    end,

    ["SYSTEM"] = function (req)
        local res = {}

        res["type"] = "SYSTEM_RESPONSE"
        res["value"] = emu.getsystemid()

        return res
    end,

    ["PREFERRED_CORES"] = function (req)
        local res = {}
        local preferred_cores = client.getconfig().PreferredCores
        local systems_enumerator = preferred_cores.Keys:GetEnumerator()

        res["type"] = "PREFERRED_CORES_RESPONSE"
        res["value"] = {}

        while systems_enumerator:MoveNext() do
            res["value"][systems_enumerator.Current] = preferred_cores[systems_enumerator.Current]
        end

        return res
    end,

    ["HASH"] = function (req)
        local res = {}

        res["type"] = "HASH_RESPONSE"
        res["value"] = rom_hash

        return res
    end,

    ["MEMORY_SIZE"] = function (req)
        local res = {}

        res["type"] = "MEMORY_SIZE_RESPONSE"
        res["value"] = memory.getmemorydomainsize(req["domain"])

        return res
    end,

    ["GUARD"] = function (req)
        local res = {}
        local expected_data = base64.decode(req["expected_data"])
        local actual_data = memory.read_bytes_as_array(req["address"], #expected_data, req["domain"])

        local data_is_validated = true
        for i, byte in ipairs(actual_data) do
            if byte ~= expected_data[i] then
                data_is_validated = false
                break
            end
        end

        res["type"] = "GUARD_RESPONSE"
        res["value"] = data_is_validated
        res["address"] = req["address"]

        return res
    end,

    ["LOCK"] = function (req)
        local res = {}

        res["type"] = "LOCKED"
        lock()

        return res
    end,

    ["UNLOCK"] = function (req)
        local res = {}

        res["type"] = "UNLOCKED"
        unlock()

        return res
    end,

    ["READ"] = function (req)
        local res = {}

        res["type"] = "READ_RESPONSE"
        res["value"] = base64.encode(memory.read_bytes_as_array(req["address"], req["size"], req["domain"]))

        return res
    end,

    ["WRITE"] = function (req)
        local res = {}

        res["type"] = "WRITE_RESPONSE"
        memory.write_bytes_as_array(req["address"], base64.decode(req["value"]), req["domain"])

        return res
    end,

    ["DISPLAY_MESSAGE"] = function (req)
        local res = {}

        res["type"] = "DISPLAY_MESSAGE_RESPONSE"
        message_queue:push(req["message"])

        return res
    end,

    ["SET_MESSAGE_INTERVAL"] = function (req)
        local res = {}

        res["type"] = "SET_MESSAGE_INTERVAL_RESPONSE"
        message_interval = req["value"]

        return res
    end,

    ["NSMBDS_FEED_MESSAGE"] = function (req)
        local res = {}

        res["type"] = "NSMBDS_FEED_MESSAGE_RESPONSE"
        res["value"] = false
        if type(_G.nsmbds_feed_push) == "function" then
            local ok, accepted = pcall(_G.nsmbds_feed_push, req)
            res["value"] = ok and accepted == true
        end

        return res
    end,

    ["NSMBDS_FEED_CONFIG"] = function (req)
        local res = {}

        res["type"] = "NSMBDS_FEED_CONFIG_RESPONSE"
        res["value"] = false
        if type(_G.nsmbds_feed_configure) == "function" then
            local ok, accepted = pcall(_G.nsmbds_feed_configure, req)
            res["value"] = ok and accepted == true
        end

        return res
    end,

    ["NSMBDS_ITEM_WRITE"] = function (req)
        local marker_address = 0x00002FF8
        local domain = "Main RAM"
        local token = base64.decode(req["token"])
        assert(#token == 8, "Invalid item transaction token")
        local nonzero = false
        for _, byte in ipairs(token) do nonzero = nonzero or byte ~= 0 end
        assert(nonzero and base64.encode(token) == req["token"], "Invalid item transaction token")
        assert(type(req["writes"]) == "table" and #req["writes"] == 1, "Invalid item transaction writes")
        assert(type(req["guards"]) == "table", "Invalid item transaction guards")
        local write = req["writes"][1]
        local value = base64.decode(write["value"])
        assert(write["domain"] == domain and #value == 1 and (
            write["address"] == 0x0008B32C or write["address"] == 0x0008B364 or write["address"] == 0x0008B37C
        ), "Invalid item transaction target")
        local guards = {}
        for i, guard in ipairs(req["guards"]) do
            local expected = base64.decode(guard["expected_data"])
            assert(guard["domain"] == domain and type(guard["address"]) == "number" and (
                guard["address"] >= 0 and guard["address"] + #expected <= 0x400000
            ), "Invalid item transaction guard")
            guards[i] = {address = guard["address"], expected = expected}
        end
        local res = {type = "NSMBDS_ITEM_WRITE_RESPONSE", value = true}
        if base64.encode(memory.read_bytes_as_array(marker_address, 8, domain)) == req["token"] then
            return res -- The write committed, but its acknowledgement was lost.
        end
        for _, guard in ipairs(guards) do
            local actual = memory.read_bytes_as_array(guard.address, #guard.expected, domain)
            if #actual ~= #guard.expected then res.value = false; return res end
            for i, byte in ipairs(guard.expected) do
                if actual[i] ~= byte then res.value = false; return res end
            end
        end
        -- Both writes execute inside one frame callback. No emulation frame can
        -- run between the consumable change and its committed transaction marker.
        memory.write_bytes_as_array(write["address"], value, domain)
        memory.write_bytes_as_array(marker_address, token, domain)
        return res
    end,

    ["NSMBDS_DIAGNOSTICS"] = function (req)
        local runtime_version = package.loaded["nsmbds.version"]
        return {
            type = "NSMBDS_DIAGNOSTICS_RESPONSE",
            bizhawk_version = tostring(bizhawk_version),
            runtime_version = type(runtime_version) == "table" and runtime_version.VERSION_LABEL or nil,
        }
    end,

    ["NSMBDS_STAR_COIN_TRACKING"] = function (req)
        local res = {}

        res["type"] = "NSMBDS_STAR_COIN_TRACKING_RESPONSE"
        res["value"] = false
        if type(_G.nsmbds_star_coin_tracking_configure) == "function" then
            local ok, accepted = pcall(_G.nsmbds_star_coin_tracking_configure, req)
            res["value"] = ok and accepted == true
        end

        return res
    end,

    ["default"] = function (req)
        local res = {}

        res["type"] = "ERROR"
        res["err"] = "Unknown command: "..req["type"]

        return res
    end,
}

local function process_request (req)
    if request_handlers[req["type"]] then
        return request_handlers[req["type"]](req)
    else
        return request_handlers["default"](req)
    end
end

local function push_nsmbds_connection_status(text, color)
    if type(_G.nsmbds_feed_push) ~= "function" then return end
    pcall(_G.nsmbds_feed_push, {
        segments = {{text = text, color = color or "text"}},
    })
end

local function disconnect_client(reason)
    if current_state == STATE_CONNECTED then
        print(reason or "Connection to client closed")
        push_nsmbds_connection_status("NSMBDS Client disconnected from BizHawk.", "warning")
    end
    if client_socket ~= nil then pcall(function () client_socket:close() end) end
    client_socket = nil
    current_state = STATE_NOT_CONNECTED
    locked = false
    receive_buffer = ""
    pending_response = nil
    send_offset = 1
    timeout_deadline = 0
end

local function flush_response()
    local sent, err, partial = client_socket:send(pending_response, send_offset)
    -- LuaSocket returns the last byte index, including on a partial send.
    send_offset = (sent or partial or (send_offset - 1)) + 1
    if err ~= nil and err ~= "timeout" then
        disconnect_client("Connection to client failed: " .. tostring(err))
        return false
    end
    if send_offset <= #pending_response then
        -- A locked transaction must not silently continue on another emulation frame.
        -- The existing two-second blocking socket timeout bounds this failure.
        if locked then disconnect_client("Client stalled while locked") end
        return false
    end
    pending_response = nil
    send_offset = 1
    return true
end

-- Receive complete lines and retry incomplete writes before reading another request.
local function send_receive ()
    if client_socket == nil then return false end
    if pending_response ~= nil then return flush_response() end
    local message, err, partial = client_socket:receive("*l", receive_buffer)
    if err == "timeout" then
        receive_buffer = partial or receive_buffer
        unlock()
        return false
    elseif err ~= nil then
        disconnect_client("Connection to client failed: " .. tostring(err))
        return false
    end
    receive_buffer = ""

    -- Measure from the actual receive time, including time spent in a LOCK.
    timeout_deadline = socket.socket.gettime() + 5

    -- Process received data
    if DEBUG then
        print("Received Message ["..emu.framecount().."]: "..'"'..message..'"')
    end

    if message == "VERSION" then
        pending_response = tostring(SCRIPT_VERSION).."\n"
    else
        local res = {}
        local decoded, data = pcall(json.decode, message)
        if not decoded or type(data) ~= "table" or not message:match("^%s*%[") then
            disconnect_client("Invalid client request; closing connection")
            return false
        end
        for _, req in ipairs(data) do
            if type(req) ~= "table" or type(req["type"]) ~= "string" then
                disconnect_client("Invalid client request; closing connection")
                return false
            end
        end
        local failed_guard_response = nil
        for i, req in ipairs(data) do
            if failed_guard_response ~= nil then
                res[i] = failed_guard_response
            else
                -- An error is more likely to cause an NLua exception than to return an error here
                local status, response = pcall(process_request, req)
                if status then
                    res[i] = response

                    -- If the GUARD validation failed, skip the remaining commands
                    if response["type"] == "GUARD_RESPONSE" and not response["value"] then
                        failed_guard_response = response
                    end
                else
                    if type(response) ~= "string" then response = "Unknown error" end
                    res[i] = {type = "ERROR", err = response}
                end
            end
        end

        pending_response = json.encode(res).."\n"
    end
    return flush_response()
end

local function initialize_server ()
    local err
    local port = SOCKET_PORT_FIRST
    local res = nil

    server, err = socket.socket.tcp4()
    if server == nil then print(err); return end
    while res == nil and port <= SOCKET_PORT_LAST do
        res, err = server:bind("localhost", port)
        if res == nil and err ~= "address already in use" then
            print(err)
            server:close()
            server = nil
            return
        end

        if res == nil then
            port = port + 1
        end
    end

    if port > SOCKET_PORT_LAST then
        print("Too many instances of connector script already running. Exiting.")
        server:close()
        server = nil
        return
    end

    res, err = server:listen(0)

    if err ~= nil then
        print(err)
        server:close()
        server = nil
        return
    end

    server:settimeout(0)
end

local function main ()
    while true do
        if server == nil and current_state == STATE_NOT_CONNECTED then
            initialize_server()
        end

        current_time = socket.socket.gettime()
        message_timer = message_timer - (current_time - prev_time)
        prev_time = current_time

        if message_timer <= 0 and not message_queue:is_empty() then
            gui.addmessage(message_queue:shift())
            message_timer = message_interval
        end

        if current_state == STATE_NOT_CONNECTED then
            if server ~= nil and emu.framecount() % 30 == 0 then
                print("Looking for client...")
                local client, timeout = server:accept()
                if timeout == nil then
                    print("Client connected")
                    current_state = STATE_CONNECTED
                    client_socket = client
                    server:close()
                    server = nil
                    client_socket:settimeout(0)
                    timeout_deadline = socket.socket.gettime() + 5
                    receive_buffer = ""
                    pending_response = nil
                    send_offset = 1
                    locked = false
                    push_nsmbds_connection_status(
                        "NSMBDS Client connected to BizHawk.",
                        "success"
                    )
                end
            end
        else
            repeat
                local progressed = send_receive()
                if not progressed then break end
            until not locked

            if current_state == STATE_CONNECTED and socket.socket.gettime() >= timeout_deadline then
                disconnect_client("Client timed out; closing stale socket")
            end
        end

        coroutine.yield()
    end
end

event.onexit(function ()
    stopped = true
    print("\n-- Restarting Script --\n")
    if server ~= nil then
        pcall(function () server:close() end)
        server = nil
    end
    disconnect_client()
end)

if bizhawk_major < 2 or (bizhawk_major == 2 and bizhawk_minor < 7) then
    print("Must use BizHawk 2.7.0 or newer")
else
    if bizhawk_major > 2 or (bizhawk_major == 2 and bizhawk_minor > 10) then
        print("Warning: This version of BizHawk is newer than this script. If it doesn't work, consider downgrading to 2.10.")
    end

    if emu.getsystemid() == "NULL" then
        print("No ROM is loaded. Please load a ROM.")
        while emu.getsystemid() == "NULL" do
            emu.frameadvance()
        end
    end

    rom_hash = gameinfo.getromhash()

    print("Waiting for client to connect. This may take longer the more instances of this script you have open at once.\n")

    local co = coroutine.create(main)
    local function tick ()
        if stopped then return end
        local status, err = coroutine.resume(co)

        if not status and err ~= "cannot resume dead coroutine" then
            print("\nERROR: "..err)
            print("Consider reporting this crash.\n")

            if server ~= nil then
                pcall(function () server:close() end)
                server = nil
            end
            disconnect_client("Connector restarting after an error")
            co = coroutine.create(main)
        end
    end

    -- Gambatte has a setting which can cause script execution to become
    -- misaligned, so for GB and GBC we explicitly set the callback on
    -- vblank instead.
    -- https://github.com/TASEmulators/BizHawk/issues/3711
    if emu.getsystemid() == "GB" or emu.getsystemid() == "GBC" or emu.getsystemid() == "SGB" then
        event.onmemoryexecute(tick, 0x40, "tick", "System Bus")
    else
        event.onframeend(tick)
    end

    while true do
        emu.frameadvance()
    end
end
