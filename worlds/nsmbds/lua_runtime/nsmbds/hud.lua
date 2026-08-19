-- =============================================================================
-- lua/nsmbds/hud.lua
-- HUD drawing routines
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local state = require("nsmbds.state")
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

    -- Tiny pixel icons beside the vanilla timer; avoid covering gameplay.
    if shield_count > 0 then
        local x, y = 152, 3
        draw_shield_icon(x, y, "cyan")
        state.notification_state.drawTextWithOutline(x + 11, y - 1,  tostring(shield_count), 10) -- "x" ..
    end
    if insurance_count > 0 then
        local x, y = 178, 3
        draw_insurance_icon(x, y, "green")
        state.notification_state.drawTextWithOutline(x + 11, y - 1,  tostring(insurance_count), 10) -- "x" ..
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
    local x1, y1, x2, y2 = 106, 20, 250, 49
    gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)
    gui.drawBox(x1, y1, x1 + 2, y2, color, color)
    gui.drawText(x1 + 4, y1 + 2, title, "white", "clear", 10)
    gui.drawText(x1 + 4, y1 + 12, subtitle, color, "clear", 9)

    local bar_x1 = x1 + 4
    local bar_x2 = x2 - 3
    -- Keep the timer clear of the subtitle baseline.
    local bar_y = y2 - 3
    local fill_width = math.floor(
        (bar_x2 - bar_x1)
        * state.notification_state.remaining_frames
        / state.notification_state.duration_frames
    )
    gui.drawBox(bar_x1, bar_y, bar_x2, bar_y, "gray", "gray")
    if fill_width > 0 then
        gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y, color, color)
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

function state.notification_state.drawTextWithOutline(x, y, text, size)
    local white = "white"
    local black = "black"

    gui.drawText(x - 1, y,     text, black, "clear", size)
    gui.drawText(x + 1, y,     text, black, "clear", size)
    gui.drawText(x,     y - 1, text, black, "clear", size)
    gui.drawText(x,     y + 1, text, black, "clear", size)

    gui.drawText(x, y, text, white, "clear", size)
end

draw_shield_icon = function(x, y, color)
    local offsets = { {-1, 0}, {1, 0}, {0, -1}, {0, 1} }

    for _, o in ipairs(offsets) do
        local ox, oy = x + o[1], y + o[2]
        gui.drawBox(ox,     oy,     ox + 8, oy + 4, "black", "black")
        gui.drawBox(ox + 1, oy + 5, ox + 7, oy + 6, "black", "black")
        gui.drawBox(ox + 2, oy + 7, ox + 6, oy + 8, "black", "black")
        gui.drawBox(ox + 4, oy + 9, ox + 4, oy + 9, "black", "black")
    end

    gui.drawBox(x,     y,     x + 8, y + 4, color, color)
    gui.drawBox(x + 1, y + 5, x + 7, y + 6, color, color)
    gui.drawBox(x + 2, y + 7, x + 6, y + 8, color, color)
    gui.drawBox(x + 4, y + 9, x + 4, y + 9, color, color)
end

draw_insurance_icon = function(x, y, color)
    local offsets = { {-1, 0}, {1, 0}, {0, -1}, {0, 1} }

    for _, o in ipairs(offsets) do
        local ox, oy = x + o[1], y + o[2]
        gui.drawBox(ox + 1, oy,     ox + 3, oy + 2, "black", "black")
        gui.drawBox(ox + 5, oy,     ox + 7, oy + 2, "black", "black")
        gui.drawBox(ox,     oy + 2, ox + 8, oy + 4, "black", "black")
        gui.drawBox(ox + 1, oy + 5, ox + 7, oy + 6, "black", "black")
        gui.drawBox(ox + 2, oy + 7, ox + 6, oy + 8, "black", "black")
        gui.drawBox(ox + 4, oy + 9, ox + 4, oy + 9, "black", "black")
    end

    gui.drawBox(x + 1, y,     x + 3, y + 2, color, color)
    gui.drawBox(x + 5, y,     x + 7, y + 2, color, color)
    gui.drawBox(x,     y + 2, x + 8, y + 4, color, color)
    gui.drawBox(x + 1, y + 5, x + 7, y + 6, color, color)
    gui.drawBox(x + 2, y + 7, x + 6, y + 8, color, color)
    gui.drawBox(x + 4, y + 9, x + 4, y + 9, color, color)
end

return M
