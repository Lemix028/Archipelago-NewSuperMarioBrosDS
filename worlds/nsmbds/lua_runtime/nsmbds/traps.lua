-- =============================================================================
-- lua/nsmbds/traps.lua
-- Trap logic and state updates
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local screen_geometry = require("nsmbds.screen_geometry")
local native_input = require("nsmbds.native_input")
local context = state.context

local LONG_TRAP_FRAMES = constants.LONG_TRAP_FRAMES
local BONK_FEEDBACK_FRAMES = constants.BONK_FEEDBACK_FRAMES
local BASE_MAX_SPEED = constants.BASE_MAX_SPEED
local HYPER_TARGET = constants.HYPER_TARGET
local SLOW_TARGET = constants.SLOW_TARGET
local ICE_GRIP_COMPENSATION = constants.ICE_GRIP_COMPENSATION
local camera_held_flag = 0
local camera_pressed_flag = 0

function M.can_apply_gameplay_traps()
    local frame = emu and emu.framecount and emu.framecount() or nil
    if frame ~= nil and context.gameplay_gate_frame == frame
        and context.gameplay_gate_player_active == context.gameplay_player_active then
        context.gameplay_trap_effects_enabled = context.gameplay_gate_result
        return context.gameplay_gate_result
    end

    local enabled = false
    if not context.gameplay_player_active then
        enabled = false
    else
        local freeze_ok, freeze_flag = pcall(
            _G.memory.readbyte,
            addresses.ADDR_STAGE_FREEZE_FLAG
        )
        local menu_ok, menu_open = pcall(
            _G.memory.readbyte,
            addresses.ADDR_STAGE_MENU_OPEN
        )
        enabled = freeze_ok
            and menu_ok
            and freeze_flag == 0
            and menu_open == 0
    end
    context.gameplay_gate_frame = frame
    context.gameplay_gate_player_active = context.gameplay_player_active
    context.gameplay_gate_result = enabled
    context.gameplay_trap_effects_enabled = enabled
    return enabled
end

function M.update_gameplay_state(has_active_player)
    context.gameplay_player_active = has_active_player == true
    local enabled = M.can_apply_gameplay_traps()

    -- These two Traps modify emulator/video state persistently, so merely
    -- skipping their per-frame update is insufficient while gameplay is frozen.
    if context.active_mode == "crazy_pixels" then
        if enabled then
            state.input_trap_state.resume_crazy_pixels()
        else
            state.input_trap_state.suspend_crazy_pixels()
        end
    elseif context.active_mode == "screen_flip" then
        if enabled then
            state.input_trap_state.resume_screen_flip()
        else
            state.input_trap_state.suspend_screen_flip()
        end
    end

    return enabled
end

function M.begin_timed_trap(mode, duration)
    _G.memory.writebyte(addresses.ADDR_AP_TRAP_TRIGGER, 0)
    context.native_trap_generation = ((context.native_trap_generation or 0) + 1)
        % 0x100000000
    context.trap_remaining_frames = duration
    context.trap_total_frames = duration
    context.active_mode = mode
    if mode == "auto_run" then
        state.input_trap_state.auto_direction = 1
    elseif mode == "im_stuck" then
        state.input_trap_state.im_stuck_player = nil
        state.input_trap_state.im_stuck_x = nil
        state.input_trap_state.im_stuck_y = nil
    elseif mode == "camera_drift" then
        local frame = emu and emu.framecount and emu.framecount() or 0
        state.input_trap_state.camera_direction = frame % 2 == 0 and 1 or -1
    elseif mode == "screen_tint" then
        local frame = emu and emu.framecount and emu.framecount() or 0
        state.input_trap_state.tint_index = frame % #state.input_trap_state.tint_colors + 1
    elseif mode == "screen_flip" and nds and nds.getscreenrotation
        and nds.setscreenrotation then
        local ok, rotation = pcall(nds.getscreenrotation)
        if ok and type(rotation) == "string" then
            state.input_trap_state.original_rotation = rotation
            local opposite = {
                Rotate0 = "Rotate180",
                Rotate90 = "Rotate270",
                Rotate180 = "Rotate0",
                Rotate270 = "Rotate90",
            }
            pcall(nds.setscreenrotation, opposite[rotation] or "Rotate180")
        end
    elseif mode == "crazy_pixels" then
        state.input_trap_state.resume_crazy_pixels()
    end
end

local function camera_shoulder_flag(direction)
    if direction < 0 then return 0x02 end
    if direction > 0 then return 0x01 end
    return 0
end

function M.update_auto_run_direction_from_input()
    -- The native filter leaves D-Pad bits unchanged for this Trap. Read the
    -- direction accepted by the game instead of joypad.get*, whose table can
    -- reflect an older input phase in BizHawk's frame-end callback.
    local input_ok, input_word = pcall(
        _G.memory.read_u16_le,
        addresses.ADDR_PRESSED_KEYS
    )
    if not input_ok or type(input_word) ~= "number" then return false end

    local right = math.floor(input_word / 0x10) % 2 == 1
    local left = math.floor(input_word / 0x20) % 2 == 1
    if right == left then return false end
    state.input_trap_state.auto_direction = right and 1 or -1
    return true
end

local function refresh_camera_filter_state()
    local elapsed = math.max(0, context.trap_total_frames - context.trap_remaining_frames)
    local direction = state.input_trap_state.camera_direction
    if context.active_mode == "camera_drift" then
        local ramping = elapsed < state.input_trap_state.camera_drift_ramp_frames
        local pulse_frame = elapsed % state.input_trap_state.camera_drift_pulse_period
        local held_direction = direction
        if ramping and pulse_frame >= state.input_trap_state.camera_drift_pulse_frames then
            held_direction = 0
        end
        local pressed_direction = ramping and pulse_frame == 0 and direction or 0
        camera_held_flag = camera_shoulder_flag(held_direction)
        camera_pressed_flag = camera_shoulder_flag(pressed_direction)
    else
        direction = math.floor(elapsed / state.input_trap_state.camera_sway_period) % 2 == 0 and -1 or 1
        camera_held_flag = camera_shoulder_flag(direction)
        camera_pressed_flag = 0
    end
end

function M.disable_native_input()
    native_input.disable()
    camera_held_flag = 0
    camera_pressed_flag = 0
end

function M.update_native_input(has_active_player)
    local mode = context.active_mode
    if mode == "camera_drift" or mode == "camera_sway" then
        refresh_camera_filter_state()
    end
    native_input.sync(has_active_player, camera_held_flag, camera_pressed_flag)
end

function M.poll_and_update_traps(has_active_player, trap_player)
    local gameplay_trap_effects_enabled = M.update_gameplay_state(has_active_player)
    if context.trap_remaining_frames == 0 and gameplay_trap_effects_enabled then
        local trigger_code = _G.memory.readbyte(addresses.ADDR_AP_TRAP_TRIGGER)

        if trigger_code == 1 then
            M.begin_timed_trap("hyper", LONG_TRAP_FRAMES)
        elseif trigger_code == 2 then
            M.begin_timed_trap("slow", LONG_TRAP_FRAMES)
        elseif trigger_code == 3 then
            M.begin_timed_trap("walljump_lock", LONG_TRAP_FRAMES)
        elseif trigger_code == 4 then
            _G.memory.writebyte(addresses.ADDR_AP_TRAP_TRIGGER, 0)
        elseif trigger_code == 5 then
            M.begin_timed_trap("no_jump", LONG_TRAP_FRAMES)
        elseif trigger_code == 6 then
            M.begin_timed_trap("reverse_controls", LONG_TRAP_FRAMES)
        elseif trigger_code == 9 then
            M.begin_timed_trap("no_sprint", LONG_TRAP_FRAMES)
        elseif trigger_code == 10 then
            M.begin_timed_trap("button_roulette", LONG_TRAP_FRAMES)
        elseif trigger_code == 11 then
            M.begin_timed_trap("ice_shoes", LONG_TRAP_FRAMES)
        elseif trigger_code == 12 then
            M.begin_timed_trap("heavy_mario", LONG_TRAP_FRAMES)
        elseif trigger_code == 13 then
            M.begin_timed_trap("auto_run", LONG_TRAP_FRAMES)
        elseif trigger_code == 14 then
            M.begin_timed_trap("sticky_buttons", LONG_TRAP_FRAMES)
        elseif trigger_code == 15 then
            M.begin_timed_trap("coin_tax_notice", BONK_FEEDBACK_FRAMES)
        elseif trigger_code == 16 then
            M.begin_timed_trap("timer_drain_notice", BONK_FEEDBACK_FRAMES)
        elseif trigger_code == 17 then
            M.begin_timed_trap("coin_thief_notice", BONK_FEEDBACK_FRAMES)
        elseif trigger_code == 18 then
            -- Retired Camera Shake command
            _G.memory.writebyte(addresses.ADDR_AP_TRAP_TRIGGER, 0)
        elseif trigger_code == 19 then
            M.begin_timed_trap("camera_drift", LONG_TRAP_FRAMES)
        elseif trigger_code == 20 then
            M.begin_timed_trap("screen_flip", LONG_TRAP_FRAMES)
        elseif trigger_code == 21 then
            M.begin_timed_trap("camera_sway", LONG_TRAP_FRAMES)
        elseif trigger_code == 22 then
            M.begin_timed_trap("boo_curse", LONG_TRAP_FRAMES)
        elseif trigger_code == 23 then
            M.begin_timed_trap("im_stuck", state.input_trap_state.im_stuck_frames)
        elseif trigger_code == 24 then
            M.begin_timed_trap("screen_tint", LONG_TRAP_FRAMES)
        elseif trigger_code == 25 then
            M.begin_timed_trap("retro_filter", LONG_TRAP_FRAMES)
        elseif trigger_code == 26 then
            M.begin_timed_trap("spotlight", state.input_trap_state.spotlight_frames)
        elseif trigger_code == 27 or trigger_code == 28 then
            state.input_trap_state.action_damage_can_kill = trigger_code == 27
            state.input_trap_state.last_action_damage_frame = -1000
            M.begin_timed_trap("ground_clap", LONG_TRAP_FRAMES)
        elseif trigger_code == 29 or trigger_code == 30 then
            state.input_trap_state.action_damage_can_kill = trigger_code == 29
            state.input_trap_state.last_action_damage_frame = -1000
            M.begin_timed_trap("head_bonk", LONG_TRAP_FRAMES)
        elseif trigger_code == 31 then
            M.begin_timed_trap("crazy_pixels", LONG_TRAP_FRAMES)
        elseif trigger_code == 32 then
            M.begin_timed_trap("no_turnaround", LONG_TRAP_FRAMES)
        elseif trigger_code == 33 then
            M.begin_timed_trap("powerup_pickpocket_notice", BONK_FEEDBACK_FRAMES)
        elseif trigger_code == 35 then
            M.begin_timed_trap("death_link_notice", BONK_FEEDBACK_FRAMES)
        elseif trigger_code == 7 or trigger_code == 8 or trigger_code == 34 then
            _G.memory.writebyte(addresses.ADDR_AP_TRAP_TRIGGER, 0)
            if trap_player then
                local current_powerup = _G.memory.readbyte(memory.to_domain_addr(trap_player + constants.PLAYER_POWERUP_OFFSET))
                if current_powerup > 0 then
                    local next_powerup = 0
                    if current_powerup == 2 or current_powerup == 3 or current_powerup == 5 then
                        next_powerup = 1
                    end
                    _G.memory.writebyte(memory.to_domain_addr(trap_player + constants.PLAYER_POWERUP_OFFSET), next_powerup)
                    _G.memory.writebyte(addresses.ADDR_POWERUP_MAP, next_powerup)
                    _G.memory.writebyte(memory.to_domain_addr(trap_player + constants.PLAYER_IFRAME_TIMER_OFFSET), BONK_FEEDBACK_FRAMES)
                    context.trap_remaining_frames = BONK_FEEDBACK_FRAMES
                    context.trap_total_frames = BONK_FEEDBACK_FRAMES
                    context.active_mode = trigger_code == 34 and "death_link_damage" or "bonk_hit"
                else
                    if trigger_code == 7 or trigger_code == 34 then
                        _G.memory.write_u32_le(addresses.ADDR_TIMER, 0)
                        context.trap_remaining_frames = BONK_FEEDBACK_FRAMES
                        context.trap_total_frames = BONK_FEEDBACK_FRAMES
                        context.active_mode = trigger_code == 34 and "death_link_damage" or "bonk_fatal"
                    else
                        _G.memory.writebyte(memory.to_domain_addr(trap_player + constants.PLAYER_IFRAME_TIMER_OFFSET), BONK_FEEDBACK_FRAMES)
                        context.trap_remaining_frames = BONK_FEEDBACK_FRAMES
                        context.trap_total_frames = BONK_FEEDBACK_FRAMES
                        context.active_mode = "bonk_protected"
                    end
                end
            end
        end
    end

    if context.trap_remaining_frames > 0 and gameplay_trap_effects_enabled then
        context.trap_remaining_frames = context.trap_remaining_frames - 1
        if trap_player then
            local mode = context.active_mode
            if mode == "auto_run" or mode == "im_stuck" then
                if mode == "auto_run" then
                    M.update_auto_run_direction_from_input()
                    _G.memory.write_s32_le(
                        memory.to_domain_addr(trap_player + constants.PLAYER_X_VELOCITY_OFFSET),
                        state.input_trap_state.auto_direction < 0
                            and -BASE_MAX_SPEED or BASE_MAX_SPEED
                    )
                elseif mode == "im_stuck" then
                    local x_address = memory.to_domain_addr(
                        trap_player + constants.OBJECT_X_OFFSET
                    )
                    local y_address = memory.to_domain_addr(
                        trap_player + constants.OBJECT_Y_OFFSET
                    )
                    if state.input_trap_state.im_stuck_player ~= trap_player then
                        state.input_trap_state.im_stuck_player = trap_player
                        state.input_trap_state.im_stuck_x = _G.memory.read_s32_le(x_address)
                        state.input_trap_state.im_stuck_y = _G.memory.read_s32_le(y_address)
                    end
                    _G.memory.write_s32_le(x_address, state.input_trap_state.im_stuck_x)
                    _G.memory.write_s32_le(y_address, state.input_trap_state.im_stuck_y)
                    _G.memory.write_s32_le(
                        memory.to_domain_addr(trap_player + constants.PLAYER_X_VELOCITY_OFFSET),
                        0
                    )
                    _G.memory.write_s32_le(
                        memory.to_domain_addr(trap_player + constants.PLAYER_Y_VELOCITY_OFFSET),
                        0
                    )
                end
            elseif mode == "crazy_pixels" then
                -- Refresh only the eight BG control words and two hardware
                -- mosaic registers. Sprite-table scans caused audio crackle.
                state.input_trap_state.apply_crazy_pixels()
            elseif mode == "hyper"
                or mode == "slow"
                or mode == "walljump_lock"
                or mode == "ice_shoes"
                or mode == "heavy_mario"
                or mode == "reverse_controls" then
                local addr_x_velocity = memory.to_domain_addr(
                    trap_player + constants.PLAYER_X_VELOCITY_OFFSET
                )
                local current_x = _G.memory.read_s32_le(addr_x_velocity)
                local pad = nil
                if mode == "hyper" or mode == "ice_shoes" or mode == "reverse_controls" then
                    pad = joypad and joypad.get and joypad.get(1)
                    if not pad or next(pad) == nil then
                        pad = joypad and joypad.getimmediate and joypad.getimmediate()
                    end
                end

            if mode == "hyper" then
                if pad and pad.Right and current_x > 2000 then
                    _G.memory.write_s32_le(addr_x_velocity, HYPER_TARGET)
                elseif pad and pad.Left and current_x < -2000 then
                    _G.memory.write_s32_le(addr_x_velocity, -HYPER_TARGET)
                end
            elseif mode == "slow" then
                if current_x > SLOW_TARGET then
                    _G.memory.write_s32_le(addr_x_velocity, SLOW_TARGET)
                elseif current_x < -SLOW_TARGET then
                    _G.memory.write_s32_le(addr_x_velocity, -SLOW_TARGET)
                end
            elseif mode == "walljump_lock" then
                local addr_left_wall = memory.to_domain_addr(trap_player + constants.PLAYER_LEFT_WALL_TIMER_OFFSET)
                local addr_right_wall = memory.to_domain_addr(trap_player + constants.PLAYER_RIGHT_WALL_TIMER_OFFSET)
                local left_wall = _G.memory.readbyte(addr_left_wall)
                local right_wall = _G.memory.readbyte(addr_right_wall)
                _G.memory.writebyte(memory.to_domain_addr(trap_player + constants.PLAYER_WALLJUMP_TIMER_OFFSET), 0)
                _G.memory.writebyte(addr_left_wall, 0)
                _G.memory.writebyte(addr_right_wall, 0)

                if left_wall > 0 then
                    _G.memory.write_s32_le(addr_x_velocity, 2048)
                elseif right_wall > 0 then
                    _G.memory.write_s32_le(addr_x_velocity, -2048)
                end
            elseif mode == "ice_shoes" then
                local left = pad and pad.Left
                local right = pad and pad.Right
                local is_braking = (left and current_x > 0) or (right and current_x < 0)
                if (not left and not right) or is_braking then
                    local slippery_x = math.floor(current_x * ICE_GRIP_COMPENSATION)
                    slippery_x = math.max(-BASE_MAX_SPEED, math.min(BASE_MAX_SPEED, slippery_x))
                    _G.memory.write_s32_le(addr_x_velocity, slippery_x)
                end
            elseif mode == "heavy_mario" then
                local addr_y_velocity = memory.to_domain_addr(trap_player + constants.PLAYER_Y_VELOCITY_OFFSET)
                local current_y = _G.memory.read_s32_le(addr_y_velocity)
                if current_y ~= 0 then
                    local accelerated_y = current_y - state.input_trap_state.heavy_gravity_boost
                    local heavy_y = accelerated_y
                    if current_y < 0 then
                        heavy_y = math.min(current_y, math.max(-state.input_trap_state.heavy_max_fall_speed, accelerated_y))
                    end
                    _G.memory.write_s32_le(addr_y_velocity, heavy_y)
                end
            elseif mode == "reverse_controls" then
                local is_dashing = pad and (pad.Y or pad.X or pad.B)
                local spd = is_dashing and HYPER_TARGET or BASE_MAX_SPEED
                if pad and pad.Left then
                    _G.memory.write_s32_le(addr_x_velocity, spd)
                elseif pad and pad.Right then
                    _G.memory.write_s32_le(addr_x_velocity, -spd)
                end
            end
            end
        end

        if context.trap_remaining_frames == 0 then
            state.input_trap_state.finish_timed_trap()
        end
    end

    M.update_native_input(has_active_player)
end

function state.input_trap_state.restore_screen_rotation()
    local rotation = state.input_trap_state.original_rotation
    state.input_trap_state.original_rotation = nil
    if rotation ~= nil and nds and nds.setscreenrotation then
        pcall(nds.setscreenrotation, rotation)
    end
end

function state.input_trap_state.apply_crazy_pixels()
    local domain = memory.sys_bus_domain
    if domain == nil then return end
    _G.memory.write_u16_le(0x0400004C, 0x7777, domain)
    _G.memory.write_u16_le(0x0400104C, 0x7777, domain)

    for engine = 0, 1 do
        local base = engine == 0 and 0x04000008 or 0x04001008
        for bg = 0, 3 do
            local address = base + bg * 2
            local value = _G.memory.read_u16_le(address, domain)
            if math.floor(value / 0x40) % 2 == 0 then
                _G.memory.write_u16_le(address, value + 0x40, domain)
            end
        end
    end

end

function state.input_trap_state.resume_crazy_pixels()
    if not state.input_trap_state.crazy_pixels_suspended or memory.sys_bus_domain == nil then return end
    local domain = memory.sys_bus_domain
    state.input_trap_state.crazy_pixels_original_mosaic = {
        _G.memory.read_u16_le(0x0400004C, domain),
        _G.memory.read_u16_le(0x0400104C, domain),
    }
    state.input_trap_state.crazy_pixels_original_bg = {}
    for engine = 0, 1 do
        local base = engine == 0 and 0x04000008 or 0x04001008
        for bg = 0, 3 do
            state.input_trap_state.crazy_pixels_original_bg[engine * 4 + bg + 1]
                = _G.memory.read_u16_le(base + bg * 2, domain)
        end
    end
    state.input_trap_state.crazy_pixels_suspended = false
    state.input_trap_state.apply_crazy_pixels()
end

function state.input_trap_state.suspend_crazy_pixels()
    if state.input_trap_state.crazy_pixels_suspended or memory.sys_bus_domain == nil then return end
    local domain = memory.sys_bus_domain
    local mosaic = state.input_trap_state.crazy_pixels_original_mosaic
    if #mosaic == 2 then
        _G.memory.write_u16_le(0x0400004C, mosaic[1], domain)
        _G.memory.write_u16_le(0x0400104C, mosaic[2], domain)
    end
    for engine = 0, 1 do
        local base = engine == 0 and 0x04000008 or 0x04001008
        for bg = 0, 3 do
            local original = state.input_trap_state.crazy_pixels_original_bg[engine * 4 + bg + 1]
            if original ~= nil then _G.memory.write_u16_le(base + bg * 2, original, domain) end
        end
    end
    state.input_trap_state.crazy_pixels_suspended = true
    state.input_trap_state.crazy_pixels_original_mosaic = {}
    state.input_trap_state.crazy_pixels_original_bg = {}
end

function state.input_trap_state.resume_screen_flip()
    if not state.input_trap_state.screen_flip_suspended then return end
    if nds and nds.getscreenrotation and nds.setscreenrotation then
        local ok, rotation = pcall(nds.getscreenrotation)
        if ok and type(rotation) == "string" then
            state.input_trap_state.original_rotation = rotation
            local opposite = {
                Rotate0 = "Rotate180", Rotate90 = "Rotate270",
                Rotate180 = "Rotate0", Rotate270 = "Rotate90",
            }
            pcall(nds.setscreenrotation, opposite[rotation] or "Rotate180")
        end
    end
    state.input_trap_state.screen_flip_suspended = false
end

function state.input_trap_state.suspend_screen_flip()
    state.input_trap_state.restore_screen_rotation()
    state.input_trap_state.screen_flip_suspended = true
end

function state.input_trap_state.finish_timed_trap()
    if context.active_mode == "screen_flip" then
        state.input_trap_state.screen_flip_suspended = false
        state.input_trap_state.restore_screen_rotation()
    elseif context.active_mode == "crazy_pixels" then
        state.input_trap_state.suspend_crazy_pixels()
    end
    context.active_mode = "none"
    context.trap_remaining_frames = 0
    context.trap_total_frames = 0
    state.input_trap_state.im_stuck_player = nil
    state.input_trap_state.im_stuck_x = nil
    state.input_trap_state.im_stuck_y = nil
    if gui and gui.clearGraphics then gui.clearGraphics() end
end


local function render_spotlight()
    local shade = 0xFA000000
    local spot_w, spot_h = 60, 65
    local cx, cy = 128, 150

    local player = state.input_trap_state.active_player
    if player then
        local raw_x = _G.memory.read_s32_le(memory.to_domain_addr(player + constants.OBJECT_X_OFFSET))
        local raw_y = _G.memory.read_s32_le(memory.to_domain_addr(player + constants.OBJECT_Y_OFFSET))
        local camera_object = _G.memory.read_u32_le(memory.to_domain_addr(0x020CAA38))

        if camera_object >= 0x02000000 and camera_object < 0x02400000 then
            local camera_x = _G.memory.read_s32_le(memory.to_domain_addr(camera_object + 0xC0))
            local camera_y = _G.memory.read_s32_le(memory.to_domain_addr(camera_object + 0xC4))
            local stage_zoom = _G.memory.read_u16_le(memory.to_domain_addr(0x020CADB4))
            if stage_zoom == 0 then stage_zoom = 4096 end

            cx = math.floor((raw_x + camera_x) / stage_zoom)
            cy = 180 - math.floor((raw_y + camera_y) / stage_zoom)
        end
    end

    cx = math.max(0, math.min(255, cx))
    cy = math.max(0, math.min(191, cy))

    local native_x1 = math.max(0, math.floor(cx - spot_w / 2))
    local native_x2 = math.min(255, math.floor(cx + spot_w / 2))
    local native_y1 = math.max(0, math.floor(cy - spot_h / 2))
    local native_y2 = math.min(191, math.floor(cy + spot_h / 2))

    local gameplay_kind = screen_geometry.get_gameplay_kind(memory.sys_bus_domain)
    local screens = screen_geometry.get_screens()

    for _, screen in ipairs(screens) do
        if screen.kind == gameplay_kind then
            local x1, y1, x2, y2 = screen_geometry.transform_rect(
                screen, native_x1, native_y1, native_x2, native_y2
            )

            local left, top = screen.x, screen.y
            local right = screen.x + screen.width - 1
            local bottom = screen.y + screen.height - 1

            x1 = math.max(left, math.min(right, x1))
            x2 = math.max(left, math.min(right, x2))
            y1 = math.max(top, math.min(bottom, y1))
            y2 = math.max(top, math.min(bottom, y2))

            if y1 > top then gui.drawBox(left, top, right, y1 - 1, shade, shade) end
            if y2 < bottom then gui.drawBox(left, y2 + 1, right, bottom, shade, shade) end
            if x1 > left then gui.drawBox(left, y1, x1 - 1, y2, shade, shade) end
            if x2 < right then gui.drawBox(x2 + 1, y1, right, y2, shade, shade) end
        end
    end
end

function state.input_trap_state.draw_visual_trap()
    if not gui or not gui.drawBox or not M.can_apply_gameplay_traps() then return end

    if context.active_mode == "screen_tint" then
        local color = state.input_trap_state.tint_colors[state.input_trap_state.tint_index]
        if color then
            local w = client.bufferwidth()
            local h = client.bufferheight()
            gui.drawBox(0, 0, w - 1, h - 1, color, color)
        end
    elseif context.active_mode == "retro_filter" then
        local w = client.bufferwidth()
        local h = client.bufferheight()

        gui.drawBox(0, 0, w - 1, h - 1, 0x708B956D, 0x708B956D)

        for y = 0, h - 1, 2 do
            gui.drawBox(0, y, w - 1, y, 0x202B3A22, 0x202B3A22)
        end
    elseif context.active_mode == "spotlight" then
         render_spotlight()
    end
       
end

function state.input_trap_state.apply_action_damage(player)
    if not M.can_apply_gameplay_traps() then return false end
    local frame = emu and emu.framecount and emu.framecount() or 0
    if frame - state.input_trap_state.last_action_damage_frame
        < state.input_trap_state.action_damage_cooldown then
        return false
    end

    local iframe_address = memory.to_domain_addr(player + constants.PLAYER_IFRAME_TIMER_OFFSET)
    state.input_trap_state.last_action_damage_frame = frame

    local current_powerup = _G.memory.readbyte(memory.to_domain_addr(player + constants.PLAYER_POWERUP_OFFSET))
    if current_powerup > 0 then
        local next_powerup = 0
        if current_powerup == 2 or current_powerup == 3 or current_powerup == 5 then
            next_powerup = 1
        end
        _G.memory.writebyte(memory.to_domain_addr(player + constants.PLAYER_POWERUP_OFFSET), next_powerup)
        _G.memory.writebyte(addresses.ADDR_POWERUP_MAP, next_powerup)
        _G.memory.writebyte(iframe_address, BONK_FEEDBACK_FRAMES)
    elseif state.input_trap_state.action_damage_can_kill then
        _G.memory.write_u32_le(addresses.ADDR_TIMER, 0)
    else
        _G.memory.writebyte(iframe_address, BONK_FEEDBACK_FRAMES)
    end
    return true
end

return M
