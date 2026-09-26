-- =============================================================================
-- lua/nsmbds/hud.lua
-- HUD drawing routines
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local state = require("nsmbds.state")
local screen_geometry = require("nsmbds.screen_geometry")
local notification_popup_sprites = require("nsmbds.notification_popup_sprites")
local trap_status_sprites = require("nsmbds.trap_status_sprites")
local RENDER_HUD_ON_BOTH_HYBRID_SCREENS = false
local context = state.context
local hud_screens_frame = nil
local cached_hud_screens = nil
local cached_hud_geometry = nil
local hud_directory = debug.getinfo(1, "S").source:sub(2):match("^(.*[/\\])") or ""
local PROTECTION_ATLAS_1X = hud_directory .. "assets/protection_hud_1x.png"
local PROTECTION_ATLAS_2X = hud_directory .. "assets/protection_hud_2x.png"
local PROTECTION_TILE_WIDTH = 27
local PROTECTION_TILE_HEIGHT = 13
local HUD_ATLAS_COLUMNS = 6
local HUD_ATLAS_GUTTER = 2
local NOTIFICATION_POPUP_ATLASES = {
    normal = hud_directory .. "assets/notification_popup_normal.png",
    horizontal = hud_directory .. "assets/notification_popup_horizontal.png",
    hybrid = hud_directory .. "assets/notification_popup_hybrid.png",
}
local NOTIFICATION_POPUP_ATLASES_2X = {
    normal = hud_directory .. "assets/notification_popup_normal_2x.png",
    horizontal = hud_directory .. "assets/notification_popup_horizontal_2x.png",
    hybrid = hud_directory .. "assets/notification_popup_hybrid_2x.png",
}
local NOTIFICATION_POPUP_ATLASES_3X = {
    normal = hud_directory .. "assets/notification_popup_normal_3x.png",
    horizontal = hud_directory .. "assets/notification_popup_horizontal_3x.png",
    hybrid = hud_directory .. "assets/notification_popup_hybrid_3x.png",
}
local TRAP_STATUS_ATLASES = {
    normal = hud_directory .. "assets/trap_status_normal.png",
    hybrid = hud_directory .. "assets/trap_status_hybrid.png",
}
local TRAP_STATUS_ATLASES_2X = {
    normal = hud_directory .. "assets/trap_status_normal_2x.png",
    hybrid = hud_directory .. "assets/trap_status_hybrid_2x.png",
}
local TRAP_STATUS_ATLASES_3X = {
    normal = hud_directory .. "assets/trap_status_normal_3x.png",
    hybrid = hud_directory .. "assets/trap_status_hybrid_3x.png",
}
local NOTIFICATION_POPUP_BAR_COLORS = {
    cyan = 0xFF44DEF0,
    green = 0xFF4AD78B,
    yellow = 0xFFFFD35C,
    red = 0xFFFF6971,
    orange = 0xFFFFA659,
    purple = 0xFFB393FF,
}
local popup_cached_active = nil
local popup_cached_title = nil
local popup_cached_subtitle = nil
local popup_cached_color = nil
local popup_cached_sprite = nil
local popup_client_surface_used = false
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
    [0x29] = "SMALL COIN BUNDLE",
    [0x2A] = "LARGE COIN BUNDLE",
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
    local gameplay_kind = screen_geometry.get_gameplay_kind(memory.sys_bus_domain)
    local screens, geometry = screen_geometry.get_screens()
    local result = {}

    for _, screen in ipairs(screens) do
        if screen.kind == gameplay_kind then
            result[#result + 1] = screen
        end
    end

    return result, geometry
end

local function get_hud_screens()
    local frame = emu and emu.framecount and emu.framecount() or nil
    if frame ~= nil and frame == hud_screens_frame and cached_hud_screens ~= nil then
        return cached_hud_screens, cached_hud_geometry
    end
    local screens, geometry = get_gameplay_screens()

    if RENDER_HUD_ON_BOTH_HYBRID_SCREENS or #screens <= 1 then
        hud_screens_frame = frame
        cached_hud_screens = screens
        cached_hud_geometry = geometry
        return screens, geometry
    end

    -- In Hybrid prefer the enlarged gameplay instance.
    for _, screen in ipairs(screens) do
        if screen.duplicate then
            cached_hud_screens = { screen }
            cached_hud_geometry = geometry
            hud_screens_frame = frame
            return cached_hud_screens, geometry
        end
    end

    cached_hud_screens = { screens[1] }
    cached_hud_geometry = geometry
    hud_screens_frame = frame
    return cached_hud_screens, geometry
end

function M.draw_protection_hud(snapshot)
    if not gui or not gui.drawImageRegion then return end
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

    -- No status to draw: avoid querying the NDS layout and building screen
    -- geometry every frame while still updating mailbox readiness above.
    if shield_count <= 0 and insurance_count <= 0 then return end

    -- Each atlas tile contains the original pixel icon and its count. BizHawk
    -- caches the PNG, so each visible status takes one GUI call per frame.
    for _, screen in ipairs(get_hud_screens()) do
        local scale = screen.duplicate and 2 or 1
        local atlas = screen.duplicate and PROTECTION_ATLAS_2X or PROTECTION_ATLAS_1X
        local tile_width = PROTECTION_TILE_WIDTH * scale
        local tile_height = PROTECTION_TILE_HEIGHT * scale
        local y = screen.y + (screen.duplicate and 6 or 3) - 2 * scale
        if shield_count > 0 then
            local index = shield_count - 1
            gui.drawImageRegion(atlas,
                (index % 10) * tile_width, math.floor(index / 10) * tile_height,
                tile_width, tile_height,
                screen.x + 145 * scale - scale, y)
        end

        if insurance_count > 0 then
            local index = insurance_count - 1
            gui.drawImageRegion(atlas,
                (10 + index % 10) * tile_width, math.floor(index / 10) * tile_height,
                tile_width, tile_height,
                screen.x + 172 * scale - scale, y)
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
        if notification.detail == 0x29 then
            return "SMALL COIN BUNDLE", "+10 COINS", "green"
        elseif notification.detail == 0x22 then
            return "COIN BUNDLE", "+25 COINS", "green"
        elseif notification.detail == 0x2A then
            return "LARGE COIN BUNDLE", "+50 COINS", "green"
        end
        local item_name = RECEIVED_ITEM_NAMES[notification.detail]
        if item_name == nil and notification.detail >= 0x51
            and notification.detail <= 0x70 then
            item_name = "STAR COIN GATE PASS"
        end
        return "ITEM RECEIVED", item_name or "PROGRESSION ITEM", "green"
    elseif notification.kind == state.notification_state.kind.death_link then
        local death_link_names = {
            [0] = "DEATH",
            [1] = "DAMAGE",
            [2] = "TIMER",
            [3] = "COINS",
            [4] = "GRACE",
        }
        local name = death_link_names[notification.detail] or "DEATH"
        local color = notification.detail == 4 and "green" or "red"
        return "DEATH LINK", name, color
    end
    return "BONUS RECEIVED", "", "green"
end

local function notification_client_scale()
    if not client or not client.screenwidth or not client.screenheight
        or not client.bufferwidth or not client.bufferheight then return nil end
    local ok_width, screen_width = pcall(client.screenwidth)
    local ok_height, screen_height = pcall(client.screenheight)
    local ok_buffer_width, buffer_width = pcall(client.bufferwidth)
    local ok_buffer_height, buffer_height = pcall(client.bufferheight)
    if not ok_width or not ok_height or not ok_buffer_width or not ok_buffer_height
        or type(screen_width) ~= "number" or type(screen_height) ~= "number"
        or type(buffer_width) ~= "number" or type(buffer_height) ~= "number"
        or buffer_width <= 0 or buffer_height <= 0 then return nil end

    local scale_x = screen_width / buffer_width
    local scale_y = screen_height / buffer_height
    -- Letterboxing and aspect correction need offsets that these APIs do not
    -- expose; use the emucore atlas when scaling is not uniform.
    if scale_x < 1.5 or math.abs(scale_x - scale_y)
        > math.max(scale_x, scale_y) * 0.04 then return nil end
    return scale_x, scale_y
end

function state.notification_state.draw()
    if not gui or not gui.drawBox or not gui.drawText then return end
    if popup_client_surface_used and gui.clearGraphics then
        gui.clearGraphics("client")
        popup_client_surface_used = false
    end

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

    -- A notification's text and sprite stay fixed for its entire duration.
    if popup_cached_active ~= state.notification_state.active then
        popup_cached_active = state.notification_state.active
        popup_cached_title, popup_cached_subtitle, popup_cached_color =
            state.notification_state.text(popup_cached_active)
        popup_cached_sprite = notification_popup_sprites[
            popup_cached_title .. "\t" .. popup_cached_subtitle .. "\t" .. popup_cached_color
        ]
    end
    local title, subtitle, color =
        popup_cached_title, popup_cached_subtitle, popup_cached_color

    -- Filler details need more room than the compact Trap status.
    local hud_screens, geometry = get_hud_screens()
    local layout = geometry and geometry.layout or "Natural"
    local client_scale_x, client_scale_y = nil, nil
    if popup_cached_sprite ~= nil and gui.drawImageRegion and gui.clearGraphics then
        client_scale_x, client_scale_y = notification_client_scale()
    end
    for _, screen in ipairs(hud_screens) do
        local scale = screen.duplicate and 1.20 or (layout == "Horizontal" and 0.85 or 1)

        local width = math.floor(145 * scale + 0.5)
        local height = math.floor(30 * scale + 0.5)
        local right_margin = screen.duplicate and 10 or 5
        local top_offset = screen.duplicate and 34 or 20

        local x1 = screen.x + screen.width - width - right_margin
        local y1 = screen.y + top_offset
        local x2 = x1 + width - 1
        local y2 = y1 + height - 1

        local sprite_drawn = popup_cached_sprite ~= nil and gui.drawImageRegion ~= nil
        if sprite_drawn then
            local layout_name = screen.duplicate and "hybrid"
                or (layout == "Horizontal" and "horizontal" or "normal")
            local column = popup_cached_sprite % HUD_ATLAS_COLUMNS
            local row = math.floor(popup_cached_sprite / HUD_ATLAS_COLUMNS)
            if client_scale_x then
                local source_scale = client_scale_x < 2.5 and 2 or 3
                local client_atlases = source_scale == 2
                    and NOTIFICATION_POPUP_ATLASES_2X or NOTIFICATION_POPUP_ATLASES_3X
                local source_gutter = HUD_ATLAS_GUTTER * source_scale
                local source_width = width * source_scale
                local source_height = height * source_scale
                gui.drawImageRegion(client_atlases[layout_name],
                    column * (source_width + 2 * source_gutter) + source_gutter,
                    row * (source_height + 2 * source_gutter) + source_gutter,
                    source_width, source_height,
                    math.floor(x1 * client_scale_x + 0.5),
                    math.floor(y1 * client_scale_y + 0.5),
                    math.floor(width * client_scale_x + 0.5),
                    math.floor(height * client_scale_y + 0.5), "client")
                popup_client_surface_used = true
            else
                gui.drawImageRegion(NOTIFICATION_POPUP_ATLASES[layout_name],
                    column * (width + 2 * HUD_ATLAS_GUTTER)
                        + HUD_ATLAS_GUTTER,
                    row * (height + 2 * HUD_ATLAS_GUTTER)
                        + HUD_ATLAS_GUTTER,
                    width, height, x1, y1)
            end
        else
            -- Preserve the old renderer for a notification missing from the
            -- generated atlas or a BizHawk build without image-region support.
            gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)
            local accent_width = math.max(3, math.floor(3 * scale + 0.5))
            gui.drawBox(x1, y1, x1 + accent_width - 1, y2, color, color)
            local title_size = screen.duplicate and 12 or 10
            local subtitle_size = screen.duplicate and 10 or 9
            gui.drawText(x1 + math.floor(4 * scale), y1 + math.floor(2 * scale),
                title, "white", "clear", title_size)
            gui.drawText(x1 + math.floor(4 * scale), y1 + math.floor(12 * scale),
                subtitle, color, "clear", subtitle_size)
        end

        local bar_x1 = x1 + math.floor(4 * scale)
        local bar_x2 = x2 - math.floor(3 * scale)
        local bar_y = y2 - math.floor(3 * scale)

        local fill_width = math.floor(
            (bar_x2 - bar_x1)
            * state.notification_state.remaining_frames
            / state.notification_state.duration_frames
        )

        if not sprite_drawn then
            gui.drawBox(bar_x1, bar_y, bar_x2, bar_y, "gray", "gray")
        end

        if fill_width > 0 then
            local fill_color = sprite_drawn and NOTIFICATION_POPUP_BAR_COLORS[color]
                or color
            if client_scale_x then
                gui.drawBox(
                    math.floor(bar_x1 * client_scale_x + 0.5),
                    math.floor(bar_y * client_scale_y + 0.5),
                    math.floor((bar_x1 + fill_width + 1) * client_scale_x + 0.5) - 1,
                    math.floor((bar_y + 1) * client_scale_y + 0.5) - 1,
                    fill_color, fill_color, "client")
            else
                gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y,
                    fill_color, fill_color)
            end
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
    -- Death Link uses the common notification mailbox for one consistent popup.
    if context.active_mode == "death_link_damage" then return end

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
    elseif context.active_mode == "no_turnaround" then
        title, color = "NO TURNAROUND", "orange"
    elseif context.active_mode == "powerup_pickpocket_notice" then
        title, color = "POWER-UP STOLEN", "orange"
    elseif context.active_mode == "coin_tax_notice" then
        title, color = "COIN TAX -10", "red"
    elseif context.active_mode == "timer_drain_notice" then
        title, color = "TIME DRAIN", "red"
    elseif context.active_mode == "coin_thief_notice" then
        title, color = "COIN THIEF", "red"
    elseif context.active_mode == "death_link_notice" then
        title, color = "DL: DEATH", "red"
    elseif context.active_mode == "death_link_damage" then
        title, color = "DL: DAMAGE", "red"
    elseif context.active_mode == "bonk_hit"
        or context.active_mode == "bonk_fatal"
        or context.active_mode == "bonk_protected" then
        title, color = "BONK TRAP", "red"
    end

    local sprite_index = trap_status_sprites[title .. "\t" .. color]
    local sprite_drawn = sprite_index ~= nil and gui.drawImageRegion ~= nil
    local client_scale_x, client_scale_y = nil, nil
    if sprite_drawn and gui.clearGraphics then
        client_scale_x, client_scale_y = notification_client_scale()
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

        if sprite_drawn then
            local layout_name = screen.duplicate and "hybrid" or "normal"
            local column = sprite_index % HUD_ATLAS_COLUMNS
            local row = math.floor(sprite_index / HUD_ATLAS_COLUMNS)
            if client_scale_x then
                local source_scale = client_scale_x < 2.5 and 2 or 3
                local atlases = source_scale == 2
                    and TRAP_STATUS_ATLASES_2X or TRAP_STATUS_ATLASES_3X
                local gutter = HUD_ATLAS_GUTTER * source_scale
                local source_width = width * source_scale
                local source_height = height * source_scale
                gui.drawImageRegion(atlases[layout_name],
                    column * (source_width + 2 * gutter) + gutter,
                    row * (source_height + 2 * gutter) + gutter,
                    source_width, source_height,
                    math.floor(x1 * client_scale_x + 0.5),
                    math.floor(y1 * client_scale_y + 0.5),
                    math.floor(width * client_scale_x + 0.5),
                    math.floor(height * client_scale_y + 0.5), "client")
                popup_client_surface_used = true
            else
                gui.drawImageRegion(TRAP_STATUS_ATLASES[layout_name],
                    column * (width + 2 * HUD_ATLAS_GUTTER)
                        + HUD_ATLAS_GUTTER,
                    row * (height + 2 * HUD_ATLAS_GUTTER)
                        + HUD_ATLAS_GUTTER,
                    width, height, x1, y1)
            end
        else
            gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)
            local accent_width = math.max(3, math.floor(3 * scale + 0.5))
            gui.drawBox(x1, y1, x1 + accent_width - 1, y2, color, color)
            gui.drawText(x1 + math.floor(4 * scale), y1 + math.floor(2 * scale),
                title, "white", "clear", screen.duplicate and 11 or 10)
        end

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

            local bar_color = sprite_drawn and NOTIFICATION_POPUP_BAR_COLORS[color]
                or color
            if client_scale_x then
                local client_x1 = math.floor(bar_x1 * client_scale_x + 0.5)
                local client_y1 = math.floor(bar_y * client_scale_y + 0.5)
                local client_y2 = math.floor((bar_y + 1) * client_scale_y + 0.5) - 1
                if fill_width > 0 then
                    gui.drawBox(client_x1, client_y1,
                        math.floor((bar_x1 + fill_width + 1) * client_scale_x + 0.5) - 1,
                        client_y2, bar_color, bar_color, "client")
                end
            else
                if not sprite_drawn then
                    gui.drawBox(bar_x1, bar_y, bar_x2, bar_y, "gray", "gray")
                end
                if fill_width > 0 then
                    gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y,
                        bar_color, bar_color)
                end
            end
        end
    end
end


return M
