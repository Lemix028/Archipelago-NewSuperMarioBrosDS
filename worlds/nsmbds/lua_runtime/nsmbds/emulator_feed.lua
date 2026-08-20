-- Colored Archipelago activity feed.

local M = {}

local FEED_WIDTH = 520

local MAX_ENTRIES = 2000
local WRAP_COLUMNS = 50
local LINE_HEIGHT = 18
local CHARACTER_WIDTH = 10

local entries = {}
local visible = true
local toggle_was_down = false
local scroll_offset = 0
local last_mouse_wheel = nil

local COLORS = {
    text = 0xB3FFFFFF,
    player_self = 0xB3EE00EE,
    player = 0xB3FAFAD2,
    progression = 0xB3AF99EF,
    useful = 0xB36D8BE8,
    filler = 0xB300EEEE,
    trap = 0xB3FA8072,
    location = 0xB300FF7F,
    success = 0xB300FF7F,
    warning = 0xB3FFA500,
}

local function key_down(keys, names)
    for _, name in ipairs(names) do
        if keys[name] then return true end
    end
    return false
end

local function append_wrapped(segments)
    local previous_count = #entries
    local text = ""
    local ranges = {}
    for _, segment in ipairs(segments) do
        local start_pos = #text + 1
        text = text .. segment.text
        ranges[#ranges + 1] = {
            first = start_pos,
            last = #text,
            color = segment.color,
        }
    end

    local line_start = 1
    while line_start <= #text do
        local line_end = math.min(#text, line_start + WRAP_COLUMNS - 1)
        if line_end < #text then
            local candidate = text:sub(line_start, line_end)
            local space = candidate:match("^.*() ")
            if space and space > 12 then line_end = line_start + space - 2 end
        end

        local line_segments = {}
        for _, range in ipairs(ranges) do
            local first = math.max(line_start, range.first)
            local last = math.min(line_end, range.last)
            if first <= last then
                line_segments[#line_segments + 1] = {
                    text = text:sub(first, last),
                    color = range.color,
                }
            end
        end
        entries[#entries + 1] = {segments = line_segments}
        line_start = line_end + 1
        while text:sub(line_start, line_start) == " " do line_start = line_start + 1 end
    end

    -- Keep the same historical lines in view while the user is scrolled up.
    if scroll_offset > 0 then
        scroll_offset = scroll_offset + (#entries - previous_count)
    end
end

function M.push(message)
    local segments = {}
    for _, segment in ipairs(message["segments"] or {}) do
        segments[#segments + 1] = {
            text = tostring(segment["text"] or ""),
            color = COLORS[segment["color"]] or COLORS.text,
        }
    end
    if #segments == 0 then return false end
    append_wrapped(segments)
    while #entries > MAX_ENTRIES do table.remove(entries, 1) end
    scroll_offset = math.min(scroll_offset, math.max(0, #entries - 1))
    return true
end



local function poll_toggle()
    if not input or not input.get then return end
    local keys = input.get()
    local ctrl = key_down(keys, {
        "Ctrl", "LeftCtrl", "RightCtrl", "LeftControl", "RightControl",
        "Control", "LControlKey", "RControlKey",
    })
    local shift = key_down(keys, {"LeftShift", "RightShift", "Shift", "LShiftKey", "RShiftKey"})
    local toggle_down = ctrl and shift and key_down(keys, {"H"})
    if toggle_down and not toggle_was_down then
        visible = not visible
    end
    toggle_was_down = toggle_down
end

local function poll_scroll(max_visible_lines)
    if not visible or not input or not input.getmouse then return end
    local mouse = input.getmouse()
    local wheel = math.floor((mouse.Wheel or 0) / 120)

    if last_mouse_wheel == nil then
        last_mouse_wheel = wheel
        return
    end

    local wheel_delta = wheel - last_mouse_wheel
    last_mouse_wheel = wheel
    if wheel_delta == 0 then return end

    local mouse_x = mouse.X or 0
    
    if client and client.transformPoint then
        local ok, point = pcall(client.transformPoint, mouse.X or 0, mouse.Y or 0)

        if ok and point then
            mouse_x = point.x or point.X or mouse_x
        end
    end

     if mouse_x < 0 or mouse_x >= FEED_WIDTH then
        return
    end

    local maximum = math.max(0, #entries - max_visible_lines)
    scroll_offset = math.max(0, math.min(maximum, scroll_offset + wheel_delta * 3))
end

function M.initialize()
    if input and input.getmouse then
        local mouse = input.getmouse()
        last_mouse_wheel = math.floor((mouse.Wheel or 0) / 120)
    end
    _G.nsmbds_feed_push = M.push
end

function M.draw()
    poll_toggle()
    if not gui then return end
    if not visible or not gui.text then return end

    local height = 384
    if client and client.screenheight then
        local ok, value = pcall(client.screenheight)
        if ok and value then height = value end
    elseif client and client.bufferheight then
        local ok, value = pcall(client.bufferheight)
        if ok and value then height = value end
    end

    local max_visible_lines = math.max(1, math.floor((height * 0.35) / LINE_HEIGHT))
    poll_scroll(max_visible_lines)
    scroll_offset = math.min(scroll_offset, math.max(0, #entries - max_visible_lines))

    local last = math.max(0, #entries - scroll_offset)
    local first = math.max(1, last - max_visible_lines + 1)
    local shown = math.max(0, last - first + 1)
    local y = height - (shown * LINE_HEIGHT) - 6
    -- BizHawk documents gui.text as its fast OSD text path. Unlike drawText,
    -- it does not rasterize a configurable system font for every segment and
    -- the OSD is cleared automatically between running frames.
    if gui.use_surface then gui.use_surface("client") end
    for index = first, last do
        local entry = entries[index]
        local x = 8
        for _, segment in ipairs(entry.segments) do
            gui.text(x, y, segment.text, segment.color)
            x = x + (#segment.text * CHARACTER_WIDTH)
        end
        y = y + LINE_HEIGHT
    end
    if gui.use_surface then gui.use_surface("emucore") end
end

function M.shutdown()
    if _G.nsmbds_feed_push == M.push then _G.nsmbds_feed_push = nil end
    if gui and gui.cleartext then gui.cleartext() end
    if gui and gui.clearGraphics then gui.clearGraphics("client") end
end


return M
