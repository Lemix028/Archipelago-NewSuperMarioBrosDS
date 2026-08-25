-- Colored Archipelago activity feed.

local M = {}

local MAX_MESSAGES = 2000
local LINE_HEIGHT = 18
local CHARACTER_WIDTH = 10
local SCREEN_MARGIN = 8
local DEFAULT_WIDTH = 500
local MIN_WIDTH = 200
local MAX_WIDTH = 1200
local FRAMES_PER_SECOND = 60

local messages = {}
local entries = {}
local visible = true
local feed_width = DEFAULT_WIDTH
local feed_position = "bottom_left"
local fade_seconds = 0
local toggle_was_down = false
local scroll_offset = 0
local browsing_history = false
local last_mouse_wheel = nil

local VALID_POSITIONS = {
    bottom_left = true,
    bottom_right = true,
    top_left = true,
    top_right = true,
}

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

local function frame_count()
    if emu and emu.framecount then
        local ok, value = pcall(emu.framecount)
        if ok and type(value) == "number" then return value end
    end
    return 0
end

local function wrap_columns()
    return math.max(12, math.floor(feed_width / CHARACTER_WIDTH))
end

local function append_wrapped(message)
    local text = ""
    local ranges = {}
    for _, segment in ipairs(message.segments) do
        local start_pos = #text + 1
        text = text .. segment.text
        ranges[#ranges + 1] = {
            first = start_pos,
            last = #text,
            color = segment.color,
        }
    end

    local columns = wrap_columns()
    local line_start = 1
    while line_start <= #text do
        local line_end = math.min(#text, line_start + columns - 1)
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
        entries[#entries + 1] = {
            segments = line_segments,
            created_frame = message.created_frame,
        }
        line_start = line_end + 1
        while text:sub(line_start, line_start) == " " do line_start = line_start + 1 end
    end
end

local function rebuild_entries()
    entries = {}
    for _, message in ipairs(messages) do append_wrapped(message) end
    scroll_offset = math.min(scroll_offset, math.max(0, #entries - 1))
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

    local previous_count = #entries
    local feed_message = {
        segments = segments,
        created_frame = frame_count(),
    }
    messages[#messages + 1] = feed_message
    append_wrapped(feed_message)
    if #messages > MAX_MESSAGES then
        table.remove(messages, 1)
        rebuild_entries()
    elseif browsing_history then
        -- Keep the same historical lines in view while the user is scrolled up.
        scroll_offset = scroll_offset + (#entries - previous_count)
    end
    return true
end

function M.configure(request)
    if type(request["enabled"]) == "boolean" then
        visible = request["enabled"]
    end

    local requested_width = tonumber(request["width"])
    if requested_width then
        requested_width = math.max(MIN_WIDTH, math.min(MAX_WIDTH, math.floor(requested_width)))
        if requested_width ~= feed_width then
            feed_width = requested_width
            rebuild_entries()
        end
    end

    local requested_position = tostring(request["position"] or "")
    if VALID_POSITIONS[requested_position] then feed_position = requested_position end

    local requested_fade = tonumber(request["fade_seconds"])
    if requested_fade then fade_seconds = math.max(0, math.min(300, requested_fade)) end
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
    if toggle_down and not toggle_was_down then visible = not visible end
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

    local maximum = math.max(0, #entries - max_visible_lines)
    if fade_seconds > 0 and wheel_delta > 0 and not browsing_history then
        -- Fade mode can show fewer than a full page. Enter history at the
        -- current end first instead of jumping past the newest messages.
        browsing_history = true
        scroll_offset = 0
        return
    end

    local requested_offset = scroll_offset + wheel_delta * 3
    scroll_offset = math.max(0, math.min(maximum, requested_offset))
    browsing_history = scroll_offset > 0
end

local function entry_alpha(entry, now)
    if fade_seconds <= 0 or browsing_history then return 1 end
    local lifetime = fade_seconds * FRAMES_PER_SECOND
    local remaining = lifetime - math.max(0, now - entry.created_frame)
    if remaining <= 0 then return 0 end
    local fade_frames = math.min(lifetime, 2 * FRAMES_PER_SECOND)
    return math.min(1, remaining / fade_frames)
end

local function faded_color(color, alpha_factor)
    if alpha_factor >= 1 then return color end
    local alpha = math.floor(color / 0x1000000) % 0x100
    local rgb = color % 0x1000000
    return math.floor(alpha * alpha_factor) * 0x1000000 + rgb
end

local function screen_dimension(method_name, fallback)
    if client and client[method_name] then
        local ok, value = pcall(client[method_name])
        if ok and type(value) == "number" then return value end
    end
    return fallback
end

local function visible_entry_indices(max_visible_lines, now)
    local indices = {}
    if browsing_history then
        local last = math.max(0, #entries - scroll_offset)
        local first = math.max(1, last - max_visible_lines + 1)
        for index = first, last do indices[#indices + 1] = index end
        return indices
    end

    for index = #entries, 1, -1 do
        if entry_alpha(entries[index], now) > 0 then
            table.insert(indices, 1, index)
            if #indices >= max_visible_lines then break end
        end
    end
    return indices
end

function M.initialize()
    if input and input.getmouse then
        local mouse = input.getmouse()
        last_mouse_wheel = math.floor((mouse.Wheel or 0) / 120)
    end
    _G.nsmbds_feed_push = M.push
    _G.nsmbds_feed_configure = M.configure
end

function M.draw()
    poll_toggle()
    if not gui or not visible or not gui.text then return end

    local width = screen_dimension("screenwidth", screen_dimension("bufferwidth", 512))
    local height = screen_dimension("screenheight", screen_dimension("bufferheight", 384))
    local max_visible_lines = math.max(1, math.floor((height * 0.35) / LINE_HEIGHT))
    poll_scroll(max_visible_lines)
    scroll_offset = math.min(scroll_offset, math.max(0, #entries - max_visible_lines))

    local now = frame_count()
    local indices = visible_entry_indices(max_visible_lines, now)
    local top_aligned = feed_position:sub(1, 3) == "top"
    local right_aligned = feed_position:sub(-5) == "right"
    local y = top_aligned and 6 or height - (#indices * LINE_HEIGHT) - 6

    -- BizHawk documents gui.text as its fast OSD text path. The OSD is
    -- cleared automatically between running frames.
    if gui.use_surface then gui.use_surface("client") end
    for _, index in ipairs(indices) do
        local entry = entries[index]
        local line_width = 0
        for _, segment in ipairs(entry.segments) do
            line_width = line_width + (#segment.text * CHARACTER_WIDTH)
        end
        local x = right_aligned
            and math.max(SCREEN_MARGIN, width - SCREEN_MARGIN - line_width)
            or SCREEN_MARGIN
        local alpha_factor = entry_alpha(entry, now)
        for _, segment in ipairs(entry.segments) do
            gui.text(x, y, segment.text, faded_color(segment.color, alpha_factor))
            x = x + (#segment.text * CHARACTER_WIDTH)
        end
        y = y + LINE_HEIGHT
    end
    if gui.use_surface then gui.use_surface("emucore") end
end

function M.shutdown()
    if _G.nsmbds_feed_push == M.push then _G.nsmbds_feed_push = nil end
    if _G.nsmbds_feed_configure == M.configure then _G.nsmbds_feed_configure = nil end
    if gui and gui.cleartext then gui.cleartext() end
    if gui and gui.clearGraphics then gui.clearGraphics("client") end
end

return M
