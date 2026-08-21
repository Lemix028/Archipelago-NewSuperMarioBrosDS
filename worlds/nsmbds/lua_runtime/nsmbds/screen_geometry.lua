-- =============================================================================
-- NSMBDS NDS Screen Geometry
-- Supported:
--   Natural
--   Vertical
--   Horizontal
--   Hybrid
--   Top
--   Bottom
-- =============================================================================

local M = {}

local NDS_WIDTH = 256
local NDS_HEIGHT = 192

local ROTATION_INDEX = {
    Rotate0 = 0,
    Rotate90 = 1,
    Rotate180 = 2,
    Rotate270 = 3,
}


local function safe_call(fn, fallback)
    if not fn then
        return fallback
    end

    local ok, value = pcall(fn)

    if ok and value ~= nil then
        return value
    end

    return fallback
end


local function get_layout()
    return safe_call(
        nds and nds.getscreenlayout,
        "Natural"
    )
end


local function get_rotation()
    local rotation = safe_call(
        nds and nds.getscreenrotation,
        "Rotate0"
    )

    if ROTATION_INDEX[rotation] == nil then
        return "Rotate0"
    end

    return rotation
end


local function get_inverted()
    return safe_call(
        nds and nds.getscreeninvert,
        false
    ) == true
end


local function get_gap()
    local gap = safe_call(
        nds and nds.getscreengap,
        0
    )

    return math.max(0, tonumber(gap) or 0)
end


local function get_buffer_size()
    local width = safe_call(
        client and client.bufferwidth,
        NDS_WIDTH
    )

    local height = safe_call(
        client and client.bufferheight,
        NDS_HEIGHT * 2
    )

    return math.max(1, width), math.max(1, height)
end


function M.get_gameplay_kind(system_bus_domain)
    if system_bus_domain == nil
        or not _G.memory
        or not _G.memory.read_u16_le then
        return "top"
    end

    local ok, powcnt1 = pcall(
        _G.memory.read_u16_le,
        0x04000304,
        system_bus_domain
    )
    if not ok or type(powcnt1) ~= "number" then return "top" end
    return (powcnt1 & 0x8000) ~= 0 and "top" or "bottom"
end


local function infer_render_scale(
    layout,
    gap,
    buffer_width,
    buffer_height
)
    local scale = 1

    if layout == "Horizontal" then
        scale = buffer_height / NDS_HEIGHT

    elseif layout == "Hybrid" then
        -- Hybrid's unrotated height is:
        -- (192 * 2 + gap) * scale
        scale = buffer_height / ((NDS_HEIGHT * 2) + gap)

    else
        -- Natural, Vertical, Top and Bottom all have a native
        -- unrotated width of 256 pixels.
        scale = buffer_width / NDS_WIDTH
    end

    scale = math.floor(scale + 0.5)

    return math.max(1, scale)
end

local function add_screen(
    screens,
    kind,
    x,
    y,
    width,
    height,
    duplicate
)
    screens[#screens + 1] = {
        kind = kind,

        x = math.floor(x),
        y = math.floor(y),

        width = math.floor(width),
        height = math.floor(height),

        duplicate = duplicate == true,
    }
end


local function first_screen_kind(inverted)
    if inverted then
        return "bottom", "top"
    end

    return "top", "bottom"
end


local function add_pair(
    screens,
    axis,
    origin_x,
    origin_y,
    screen_width,
    screen_height,
    gap,
    inverted
)
    local first_kind, second_kind =
        first_screen_kind(inverted)

    if axis == "horizontal" then
        add_screen(
            screens,
            first_kind,
            origin_x,
            origin_y,
            screen_width,
            screen_height,
            false
        )

        add_screen(
            screens,
            second_kind,
            origin_x + screen_width + gap,
            origin_y,
            screen_width,
            screen_height,
            false
        )
    else
        add_screen(
            screens,
            first_kind,
            origin_x,
            origin_y,
            screen_width,
            screen_height,
            false
        )

        add_screen(
            screens,
            second_kind,
            origin_x,
            origin_y + screen_height + gap,
            screen_width,
            screen_height,
            false
        )
    end
end


local function rotate_rect(
    screen,
    canvas_width,
    canvas_height,
    rotation_index,
    rotation
)
    screen.base_x = screen.x
    screen.base_y = screen.y
    screen.base_width = screen.width
    screen.base_height = screen.height

    screen.base_canvas_width = canvas_width
    screen.base_canvas_height = canvas_height

    screen.rotation_index = rotation_index
    screen.rotation = rotation

    local x = screen.x
    local y = screen.y
    local width = screen.width
    local height = screen.height

    if rotation_index == 1 then
        -- Rotate90: rotate the complete canvas
        screen.x =
            canvas_height - (y + height)

        screen.y = x

        screen.width = height
        screen.height = width

    elseif rotation_index == 2 then
        -- Rotate180
        screen.x =
            canvas_width - (x + width)

        screen.y =
            canvas_height - (y + height)

    elseif rotation_index == 3 then
        -- Rotate270
        screen.x = y

        screen.y =
            canvas_width - (x + width)

        screen.width = height
        screen.height = width
    end
end


-- Rotate a point on the complete unrotated emulator canvas.
local function rotate_point(
    x,
    y,
    canvas_width,
    canvas_height,
    rotation_index
)
    if rotation_index == 1 then
        return
            (canvas_height - 1) - y,
            x

    elseif rotation_index == 2 then
        return
            (canvas_width - 1) - x,
            (canvas_height - 1) - y

    elseif rotation_index == 3 then
        return
            y,
            (canvas_width - 1) - x
    end

    return x, y
end


function M.get_screens()
    local layout = get_layout()
    local rotation = get_rotation()
    local rotation_index = ROTATION_INDEX[rotation] or 0
    local inverted = get_inverted()
    local configured_gap = get_gap()

    local buffer_width, buffer_height =
        get_buffer_size()

    local base_buffer_width = buffer_width
    local base_buffer_height = buffer_height

    if rotation_index == 1
        or rotation_index == 3 then

        base_buffer_width = buffer_height
        base_buffer_height = buffer_width
    end

    local render_scale = infer_render_scale(
        layout,
        configured_gap,
        base_buffer_width,
        base_buffer_height
    )

    local screen_width =
        NDS_WIDTH * render_scale

    local screen_height =
        NDS_HEIGHT * render_scale

    local scaled_gap =
        configured_gap * render_scale

    local screens = {}


    if layout == "Top" then
        add_screen(
            screens,
            "top",
            0,
            0,
            base_buffer_width,
            base_buffer_height,
            false
        )

    elseif layout == "Bottom" then
        add_screen(
            screens,
            "bottom",
            0,
            0,
            base_buffer_width,
            base_buffer_height,
            false
        )

    elseif layout == "Horizontal" then
        add_pair(
            screens,
            "horizontal",
            0,
            0,
            screen_width,
            screen_height,
            scaled_gap,
            inverted
        )

    elseif layout == "Hybrid" then
        local hybrid_kind =
            inverted and "bottom" or "top"

        local large_width =
            base_buffer_width - screen_width

        add_screen(
            screens,
            hybrid_kind,
            0,
            0,
            large_width,
            base_buffer_height,
            true
        )

        add_pair(
            screens,
            "vertical",
            large_width,
            0,
            screen_width,
            screen_height,
            scaled_gap,
            false
        )

    else
        -- Natural and Vertical use the normal vertical DS arrangement
        add_pair(
            screens,
            "vertical",
            0,
            0,
            screen_width,
            screen_height,
            scaled_gap,
            inverted
        )
    end


    for _, screen in ipairs(screens) do
        rotate_rect(
            screen,
            base_buffer_width,
            base_buffer_height,
            rotation_index,
            rotation
        )
    end


    return screens, {
        layout = layout,
        rotation = rotation,
        rotation_index = rotation_index,
        inverted = inverted,

        configured_gap = configured_gap,
        scaled_gap = scaled_gap,
        render_scale = render_scale,

        buffer_width = buffer_width,
        buffer_height = buffer_height,

        base_buffer_width = base_buffer_width,
        base_buffer_height = base_buffer_height,

        screen_width = screen_width,
        screen_height = screen_height,
    }
end


-- Transform an unrotated native DS coordinate (0..255, 0..191)
function M.transform_point(screen, x, y)
    if not screen then
        return x, y
    end

    local base_x =
        screen.base_x or screen.x

    local base_y =
        screen.base_y or screen.y

    local base_width =
        screen.base_width or screen.width

    local base_height =
        screen.base_height or screen.height

    -- Map the native 256x192 DS coordinate onto this screen instance.
    -- Using width-1 / height-1 keeps edge pixels inside the rectangle.
    local scale_x = 1
    local scale_y = 1

    if NDS_WIDTH > 1 then
        scale_x =
            (base_width - 1) / (NDS_WIDTH - 1)
    end

    if NDS_HEIGHT > 1 then
        scale_y =
            (base_height - 1) / (NDS_HEIGHT - 1)
    end

    local canvas_x =
        base_x + x * scale_x

    local canvas_y =
        base_y + y * scale_y

    return rotate_point(
        canvas_x,
        canvas_y,
        screen.base_canvas_width or base_width,
        screen.base_canvas_height or base_height,
        screen.rotation_index or 0
    )
end

function M.transform_rect(screen, x1, y1, x2, y2)
    local ax, ay = M.transform_point(screen, x1, y1)
    local bx, by = M.transform_point(screen, x2, y1)
    local cx, cy = M.transform_point(screen, x1, y2)
    local dx, dy = M.transform_point(screen, x2, y2)

    local min_x = math.min(ax, bx, cx, dx)
    local max_x = math.max(ax, bx, cx, dx)
    local min_y = math.min(ay, by, cy, dy)
    local max_y = math.max(ay, by, cy, dy)

    return
        math.floor(min_x),
        math.floor(min_y),
        math.ceil(max_x),
        math.ceil(max_y)
end



return M
