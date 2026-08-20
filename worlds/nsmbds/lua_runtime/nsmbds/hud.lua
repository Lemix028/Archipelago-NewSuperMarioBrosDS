-- =============================================================================
-- lua/nsmbds/hud.lua
-- HUD drawing routines
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local state = require("nsmbds.state")
local screen_geometry = require("nsmbds.screen_geometry")
local RENDER_HUD_ON_BOTH_HYBRID_SCREENS = false
local context = state.context
local draw_shield_icon
local draw_insurance_icon
local RECEIVED_ITEM_NAMES = {
    [0x00] = "DESERT PASS",
    [0x01] = "ISLE PASS",
    [0x02] = "JUNGLE PASS",
    [0x03] = "GLACIER PASS",
    [0x04] = "MOUNTAIN PASS",
    [0x05] = "CLOUD PASS",
    [0x06] = "VOLCANO PASS",
    [0x07] = "MINI MUSHROOM PERMIT",
    [0x08] = "BLUE SHELL PERMIT",
    [0x0A] = "MEGA MUSHROOM PERMIT",
    [0x0B] = "POCKET PERMIT",
    [0x0C] = "MUSHROOM PERMIT",
    [0x0D] = "FIRE FLOWER PERMIT",
    [0x0E] = "STAR COIN",
    [0x10] = "MUSHROOM",
    [0x11] = "FIRE FLOWER",
    [0x12] = "BLUE SHELL",
    [0x13] = "MINI MUSHROOM",
    [0x14] = "MEGA MUSHROOM",
    [0x15] = "STARMAN BUFF",
    [0x20] = "1-UP MUSHROOM",
    [0x21] = "3-UP MOON",
    [0x22] = "COIN BUNDLE",
    [0x40] = "GRASSLAND TOWER KEY",
    [0x41] = "GRASSLAND CASTLE KEY",
    [0x42] = "DESERT TOWER KEY",
    [0x43] = "DESERT CASTLE KEY",
    [0x44] = "TROPICAL TOWER KEY",
    [0x45] = "TROPICAL CASTLE KEY",
    [0x46] = "JUNGLE TOWER KEY",
    [0x47] = "JUNGLE CASTLE KEY",
    [0x48] = "GLACIER TOWER KEY",
    [0x49] = "GLACIER CASTLE KEY",
    [0x4A] = "MOUNTAIN TOWER KEY",
    [0x4B] = "MOUNTAIN CASTLE KEY",
    [0x4C] = "SKY TOWER KEY",
    [0x4D] = "SKY CASTLE KEY",
    [0x4E] = "VOLCANO TOWER KEY",
    [0x4F] = "VOLCANO CASTLE KEY",
    [0x50] = "PROGRESSIVE GATE PASS",
}

local function get_gameplay_screens()
    local powcnt1 = _G.memory.read_u16_le(0x04000304, memory.sys_bus_domain)
    local gameplay_kind = (powcnt1 & 0x8000) ~= 0 and "top" or "bottom"
    local screens, result = screen_geometry.get_screens(), {}

    for _, screen in ipairs(screens) do
        if screen.kind == gameplay_kind then
            result[#result + 1] = screen
        end
    end

    return result
end

local function draw_icon_box(x, y, ox, oy, w, h, color, scale)
    gui.drawBox(
        x + ox * scale,
        y + oy * scale,
        x + (ox + w) * scale - 1,
        y + (oy + h) * scale - 1,
        color,
        color
    )
end

local function get_hud_screens()
    local screens = get_gameplay_screens()

    if RENDER_HUD_ON_BOTH_HYBRID_SCREENS or #screens <= 1 then
        return screens
    end

    -- In Hybrid prefer the enlarged gameplay instance.
    for _, screen in ipairs(screens) do
        if screen.duplicate then
            return { screen }
        end
    end

    return { screens[1] }
end

function M.draw_protection_hud(snapshot)
    if not gui or not gui.drawBox or not gui.drawText then return end
    snapshot = snapshot or state.notification_state.capture_snapshot(false)
    if not snapshot or not state.notification_state.is_ready(snapshot) then
        state.notification_state.protection_hud_was_ready = false
        context.last_drawn_shield_count = nil
        context.last_drawn_insurance_count = nil
        state.notification_state.ready_wait_frames = state.notification_state.ready_wait_frames + 1
        if state.notification_state.ready_wait_frames >= 120
            and not state.notification_state.ready_warning_printed then
            state.notification_state.ready_warning_printed = true
            print(
                "NSMBDS protection mailbox not ready domain=" .. tostring(memory.domain)
                .. " magic=" .. tostring(snapshot and snapshot[4])
                .. "," .. tostring(snapshot and snapshot[5])
            )
        end
        return
    end
    state.notification_state.protection_hud_was_ready = true
    state.notification_state.ready_wait_frames = 0
    state.notification_state.ready_warning_printed = false

    local shield_count = snapshot[1]
    local insurance_count = snapshot[2]
    context.last_drawn_shield_count = shield_count
    context.last_drawn_insurance_count = insurance_count

    -- Tiny pixel icons beside the vanilla timer; on multiple screens.
    for _, screen in ipairs(get_hud_screens()) do
        local scale = screen.duplicate and 2 or 1

        local shield_base_x = 145
        local insurance_base_x = 172

        local text_size = screen.duplicate and 18 or 10
        local text_style = screen.duplicate and "bold" or "regular"
        local outline = screen.duplicate and 2 or 1

        if shield_count > 0 then
            local x = screen.x + shield_base_x * scale
            local y = screen.y + (screen.duplicate and 6 or 3)

            draw_shield_icon(x, y, "cyan", scale)
            state.notification_state.drawTextWithOutline(
                x + 10 * scale,
                y + (screen.duplicate and -2 or -1),
                tostring(shield_count),
                text_size,
                text_style,
                outline
            )
        end

        if insurance_count > 0 then
            local x = screen.x + insurance_base_x * scale
            local y = screen.y + (screen.duplicate and 6 or 3)

            draw_insurance_icon(x, y, "green", scale)
            state.notification_state.drawTextWithOutline(
                x + 10 * scale,
                y + (screen.duplicate and -2 or -1),
                tostring(insurance_count),
                text_size,
                text_style,
                outline
            )
        end
    end
end

function state.notification_state.text(notification)
    if notification.kind == state.notification_state.kind.time_capsule then
        return "TIME CAPSULE", "+30 SEC", "cyan"
    elseif notification.kind == state.notification_state.kind.starman_lite then
        return "STARMAN LITE", "+5 SEC INVINCIBLE", "yellow"
    elseif notification.kind == state.notification_state.kind.trap_shield then
        return "TRAP SHIELD", "+1 CHARGE", "cyan"
    elseif notification.kind == state.notification_state.kind.care_package then
        return "SMALL CARE PACKAGE", "+15 SEC +5 COINS +1 LIFE", "green"
    elseif notification.kind == state.notification_state.kind.life_insurance then
        return "LIFE INSURANCE", "+1 CHARGE", "green"
    elseif notification.kind == state.notification_state.kind.trap_blocked then
        local blocked_names = {
            [2] = "TIME DRAIN",
            [3] = "COIN THIEF",
            [4] = "BONK TRAP",
            [5] = "SUPER SPEED",
            [6] = "SLOWNESS",
            [7] = "SLIPPERY GLOVES",
            [8] = "GROUND BOUND",
            [9] = "HYPER CONFUSION",
            [10] = "NO SPRINT",
            [11] = "BUTTON SWAP",
            [12] = "ICE SHOES",
            [13] = "HEAVY MARIO",
            [14] = "CAN'T STOP",
            [15] = "STICKY BUTTONS",
            [16] = "COIN TAX",
            [18] = "CAMERA DRIFT",
            [19] = "SCREEN FLIP",
            [20] = "DRUNK CAMERA",
            [21] = "BOO CURSE",
            [22] = "I'M STUCK",
            [23] = "SCREEN TINT",
            [24] = "RETRO FILTER",
            [25] = "SPOTLIGHT",
            [26] = "GROUND CLAP",
            [27] = "HEAD BONK",
            [28] = "PIXELATION",
        }
        return "TRAP BLOCKED", blocked_names[notification.detail] or "SHIELD CONSUMED", "cyan"
    elseif notification.kind == state.notification_state.kind.starman_buff then
        return "STARMAN BUFF", "+15 SEC INVINCIBLE", "yellow"
    elseif notification.kind == state.notification_state.kind.goal_complete then
        return "GOAL COMPLETE!", "CONGRATULATIONS!", "green"
    elseif notification.kind == state.notification_state.kind.item_received then
        local item_name = RECEIVED_ITEM_NAMES[notification.detail]
        if item_name == nil and notification.detail >= 0x51
            and notification.detail <= 0x70 then
            item_name = "STAR COIN GATE PASS"
        end
        return "ITEM RECEIVED", item_name or "PROGRESSION ITEM", "green"
    end
    return "BONUS RECEIVED", "", "green"
end

function state.notification_state.draw()
    if not gui or not gui.drawBox or not gui.drawText then return end

    if state.notification_state.active == nil and #state.notification_state.queue > 0 then
        state.notification_state.active = table.remove(state.notification_state.queue, 1)
        state.notification_state.duration_frames = state.notification_state.duration(
            state.notification_state.active
        )
        state.notification_state.remaining_frames = state.notification_state.duration_frames
    end
    if state.notification_state.active == nil then return end

    -- A consumed shield must be visible while the blocked trap would have run.
    -- Ordinary filler notices still wait until the active Trap status is gone.
    if context.active_mode ~= "none"
        and state.notification_state.active.kind ~= state.notification_state.kind.trap_blocked then
        return
    end

    local title, subtitle, color = state.notification_state.text(state.notification_state.active)

    -- Filler details need more room than the compact Trap status.
    for _, screen in ipairs(get_hud_screens()) do
        local layout = nds.getscreenlayout()
        local scale = screen.duplicate and 1.20 or (layout == "Horizontal" and 0.85 or 1)

        local width = math.floor(145 * scale + 0.5)
        local height = math.floor(30 * scale + 0.5)
        local right_margin = screen.duplicate and 10 or 5
        local top_offset = screen.duplicate and 34 or 20

        local x1 = screen.x + screen.width - width - right_margin
        local y1 = screen.y + top_offset
        local x2 = x1 + width - 1
        local y2 = y1 + height - 1

        gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)

        local accent_width = math.max(3, math.floor(3 * scale + 0.5))
        gui.drawBox(x1, y1, x1 + accent_width - 1, y2, color, color)

        local title_size = screen.duplicate and 12 or 10
        local subtitle_size = screen.duplicate and 10 or 9

        gui.drawText(
            x1 + math.floor(4 * scale),
            y1 + math.floor(2 * scale),
            title,
            "white",
            "clear",
            title_size
        )

        gui.drawText(
            x1 + math.floor(4 * scale),
            y1 + math.floor(12 * scale),
            subtitle,
            color,
            "clear",
            subtitle_size
        )

        local bar_x1 = x1 + math.floor(4 * scale)
        local bar_x2 = x2 - math.floor(3 * scale)
        local bar_y = y2 - math.floor(3 * scale)

        local fill_width = math.floor(
            (bar_x2 - bar_x1)
            * state.notification_state.remaining_frames
            / state.notification_state.duration_frames
        )

        gui.drawBox(bar_x1, bar_y, bar_x2, bar_y, "gray", "gray")

        if fill_width > 0 then
            gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y, color, color)
        end
    end
    state.notification_state.remaining_frames = state.notification_state.remaining_frames - 1
    if state.notification_state.remaining_frames <= 0 then
        local completed_kind = state.notification_state.active.kind
        state.notification_state.active = nil
        if completed_kind == state.notification_state.kind.goal_complete then
            state.notification_state.popup_disabled = true
            state.notification_state.queue = {}
        end
    end
end

function M.draw_trap_status_hud()
    if not gui or not gui.drawBox or not gui.drawText then return end
    if context.trap_remaining_frames <= 0 then return end

    -- Trap Blocked notification replaces the normal trap status temporarily.
    if state.notification_state.active ~= nil
        and state.notification_state.active.kind == state.notification_state.kind.trap_blocked then
        return
    end

    local title = "TRAP ACTIVE"
    local color = "red"

    if context.active_mode == "hyper" then
        title, color = "SUPER SPEED", "red"
    elseif context.active_mode == "slow" then
        title, color = "SLOWNESS", "cyan"
    elseif context.active_mode == "walljump_lock" then
        title, color = "SLIPPERY GLOVES", "yellow"
    elseif context.active_mode == "no_jump" then
        title, color = "GROUND BOUND", "orange"
    elseif context.active_mode == "reverse_controls" then
        title, color = "HYPER CONFUSION", "purple"
    elseif context.active_mode == "no_sprint" then
        title, color = "NO SPRINT", "orange"
    elseif context.active_mode == "button_roulette" then
        title, color = "BUTTON SWAP", "purple"
    elseif context.active_mode == "ice_shoes" then
        title, color = "ICE SHOES", "cyan"
    elseif context.active_mode == "heavy_mario" then
        title, color = "HEAVY MARIO", "orange"
    elseif context.active_mode == "auto_run" then
        title, color = "CAN'T STOP", "red"
    elseif context.active_mode == "sticky_buttons" then
        title, color = "STICKY BUTTONS", "yellow"
    elseif context.active_mode == "camera_drift" then
        title, color = "CAMERA DRIFT", "purple"
    elseif context.active_mode == "screen_flip" then
        title, color = "SCREEN FLIP", "purple"
    elseif context.active_mode == "camera_sway" then
        title, color = "DRUNK CAMERA", "purple"
    elseif context.active_mode == "boo_curse" then
        title, color = "BOO CURSE", "purple"
    elseif context.active_mode == "im_stuck" then
        title, color = "I'M STUCK", "yellow"
    elseif context.active_mode == "screen_tint" then
        title, color = "SCREEN TINT", "purple"
    elseif context.active_mode == "retro_filter" then
        title, color = "RETRO FILTER", "orange"
    elseif context.active_mode == "spotlight" then
        title, color = "SPOTLIGHT", "yellow"
    elseif context.active_mode == "ground_clap" then
        title, color = "GROUND CLAP", "red"
    elseif context.active_mode == "head_bonk" then
        title, color = "HEAD BONK", "red"
    elseif context.active_mode == "crazy_pixels" then
        title, color = "PIXELATION", "purple"
    elseif context.active_mode == "coin_tax_notice" then
        title, color = "COIN TAX -10", "red"
    elseif context.active_mode == "timer_drain_notice" then
        title, color = "TIME DRAIN", "red"
    elseif context.active_mode == "coin_thief_notice" then
        title, color = "COIN THIEF", "red"
    elseif context.active_mode == "bonk_hit"
        or context.active_mode == "bonk_fatal"
        or context.active_mode == "bonk_protected" then
        title, color = "BONK TRAP", "red"
    end

    for _, screen in ipairs(get_hud_screens()) do
        local scale = screen.duplicate and 1.25 or 1

        local width = math.floor(93 * scale + 0.5)
        local height = math.floor(18 * scale + 0.5)
        local right_margin = screen.duplicate and 12 or 5
        local top_offset = screen.duplicate and 38 or 20

        local x1 = screen.x + screen.width - width - right_margin
        local y1 = screen.y + top_offset
        local x2 = x1 + width - 1
        local y2 = y1 + height - 1

        gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)

        local accent_width = math.max(3, math.floor(3 * scale + 0.5))
        gui.drawBox(x1, y1, x1 + accent_width - 1, y2, color, color)

        gui.drawText(
            x1 + math.floor(4 * scale),
            y1 + math.floor(2 * scale),
            title,
            "white",
            "clear",
            screen.duplicate and 11 or 10
        )

        if context.trap_total_frames > 0 then
            local bar_x1 = x1 + math.floor(4 * scale)
            local bar_x2 = x2 - math.floor(3 * scale)
            local bar_y = y2 - math.floor(3 * scale)

            local fill_width = math.max(
                0,
                math.floor(
                    (bar_x2 - bar_x1)
                    * context.trap_remaining_frames
                    / context.trap_total_frames
                )
            )

            gui.drawBox(bar_x1, bar_y, bar_x2, bar_y, "gray", "gray")

            if fill_width > 0 then
                gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y, color, color)
            end
        end
    end
end


function state.notification_state.drawTextWithOutline(x, y, text, size, style, outline)
    style = style or "regular"
    outline = outline or 1

    if outline == 1 then
        gui.drawText(x - 1, y, text, "black", "clear", size, "Courier New", style)
        gui.drawText(x + 1, y, text, "black", "clear", size, "Courier New", style)
        gui.drawText(x, y - 1, text, "black", "clear", size, "Courier New", style)
        gui.drawText(x, y + 1, text, "black", "clear", size, "Courier New", style)
    else
        for ox = -outline, outline do
            for oy = -outline, outline do
                if ox ~= 0 or oy ~= 0 then
                    gui.drawText(x + ox, y + oy, text, "black", "clear", size, "Courier New", style)
                end
            end
        end
    end

    gui.drawText(x, y, text, "white", "clear", size, "Courier New", style)
end

draw_shield_icon = function(x, y, color, scale)
    scale = scale or 1

    for _, o in ipairs({{-1,0},{1,0},{0,-1},{0,1}}) do
        draw_icon_box(x, y, o[1],     o[2],     9, 5, "black", scale)
        draw_icon_box(x, y, o[1] + 1, o[2] + 5, 7, 2, "black", scale)
        draw_icon_box(x, y, o[1] + 2, o[2] + 7, 5, 2, "black", scale)
        draw_icon_box(x, y, o[1] + 4, o[2] + 9, 1, 1, "black", scale)
    end

    draw_icon_box(x, y, 0, 0, 9, 5, color, scale)
    draw_icon_box(x, y, 1, 5, 7, 2, color, scale)
    draw_icon_box(x, y, 2, 7, 5, 2, color, scale)
    draw_icon_box(x, y, 4, 9, 1, 1, color, scale)
end

draw_insurance_icon = function(x, y, color, scale)
    scale = scale or 1

    for _, o in ipairs({{-1,0},{1,0},{0,-1},{0,1}}) do
        draw_icon_box(x, y, o[1] + 1, o[2],     3, 3, "black", scale)
        draw_icon_box(x, y, o[1] + 5, o[2],     3, 3, "black", scale)
        draw_icon_box(x, y, o[1],     o[2] + 2, 9, 3, "black", scale)
        draw_icon_box(x, y, o[1] + 1, o[2] + 5, 7, 2, "black", scale)
        draw_icon_box(x, y, o[1] + 2, o[2] + 7, 5, 2, "black", scale)
        draw_icon_box(x, y, o[1] + 4, o[2] + 9, 1, 1, "black", scale)
    end

    draw_icon_box(x, y, 1, 0, 3, 3, color, scale)
    draw_icon_box(x, y, 5, 0, 3, 3, color, scale)
    draw_icon_box(x, y, 0, 2, 9, 3, color, scale)
    draw_icon_box(x, y, 1, 5, 7, 2, color, scale)
    draw_icon_box(x, y, 2, 7, 5, 2, color, scale)
    draw_icon_box(x, y, 4, 9, 1, 1, color, scale)
end

return M
