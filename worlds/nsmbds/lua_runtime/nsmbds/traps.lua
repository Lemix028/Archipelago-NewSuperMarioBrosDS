-- =============================================================================
-- lua/nsmbds/traps.lua
-- Trap logic and state updates
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local context = state.context

local LONG_TRAP_FRAMES = constants.LONG_TRAP_FRAMES
local BONK_FEEDBACK_FRAMES = constants.BONK_FEEDBACK_FRAMES
local BASE_MAX_SPEED = constants.BASE_MAX_SPEED
local HYPER_TARGET = constants.HYPER_TARGET
local SLOW_TARGET = constants.SLOW_TARGET
local ICE_GRIP_COMPENSATION = constants.ICE_GRIP_COMPENSATION

local function clear_byte_flag(value, flag)
    if math.floor(value / flag) % 2 == 1 then
        return value - flag
    end
    return value
end

local function set_byte_flag(value, flag)
    if math.floor(value / flag) % 2 == 0 then
        return value + flag
    end
    return value
end

local function has_byte_flag(value, flag)
    return math.floor(value / flag) % 2 == 1
end

function M.begin_timed_trap(mode, duration)
    _G.memory.writebyte(addresses.ADDR_AP_TRAP_TRIGGER, 0)
    context.trap_remaining_frames = duration
    context.trap_total_frames = duration
    context.active_mode = mode
    if mode == "auto_run" then
        state.input_trap_state.auto_direction = 1
    elseif mode == "im_stuck" then
        state.input_trap_state.im_stuck_player = nil
        state.input_trap_state.im_stuck_x = nil
        state.input_trap_state.im_stuck_y = nil
    elseif mode == "sticky_buttons" then
        state.input_trap_state.sticky_direction = 0
        state.input_trap_state.sticky_frames = 0
        state.input_trap_state.sticky_last_frame = -1
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

local function clear_jump_buttons_at(address)
    local original_low = _G.memory.readbyte(address)
    local original_high = _G.memory.readbyte(address + 1)
    local low = original_low
    local high = original_high

    -- A is always jump. B and X swap between jump and dash.
    low = clear_byte_flag(low, 0x01)
    if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
        low = clear_byte_flag(low, 0x02)
    else
        high = clear_byte_flag(high, 0x04)
    end

    if low ~= original_low then
        _G.memory.writebyte(address, low)
    end
    if high ~= original_high then
        _G.memory.writebyte(address + 1, high)
    end
end

local function clear_sprint_buttons_at(address)
    local original_low = _G.memory.readbyte(address)
    local original_high = _G.memory.readbyte(address + 1)
    local low = original_low
    local high = clear_byte_flag(original_high, 0x08) -- Y always dashes.

    -- B and X swap between jump and dash with the control option.
    if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
        high = clear_byte_flag(high, 0x04)
    else
        low = clear_byte_flag(low, 0x02)
    end

    if low ~= original_low then
        _G.memory.writebyte(address, low)
    end
    if high ~= original_high then
        _G.memory.writebyte(address + 1, high)
    end
end

local function swap_word_flags(value, first_flag, second_flag)
    local first_set = math.floor(value / first_flag) % 2 == 1
    local second_set = math.floor(value / second_flag) % 2 == 1
    if first_set == second_set then return value end
    if first_set then
        return value - first_flag + second_flag
    end
    return value - second_flag + first_flag
end

local function remap_button_roulette_at(address)
    local original_low = _G.memory.readbyte(address)
    local original_high = _G.memory.readbyte(address + 1)
    local buttons = original_low + original_high * 0x100

    if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
        -- Default: A/B jump and X/Y dash.
        buttons = swap_word_flags(buttons, 0x0001, 0x0400)
        buttons = swap_word_flags(buttons, 0x0002, 0x0800)
    else
        -- Alternate: A/X jump and B/Y dash.
        buttons = swap_word_flags(buttons, 0x0001, 0x0002)
        buttons = swap_word_flags(buttons, 0x0400, 0x0800)
    end

    local low = buttons % 0x100
    local high = math.floor(buttons / 0x100)
    if low ~= original_low then _G.memory.writebyte(address, low) end
    if high ~= original_high then _G.memory.writebyte(address + 1, high) end
end

function state.input_trap_state.clear_im_stuck_at(address)
    local original_low = _G.memory.readbyte(address)
    local original_high = _G.memory.readbyte(address + 1)
    -- Preserve Select and Start so the player can still pause safely.
    local low = 0
    if has_byte_flag(original_low, 0x04) then low = low + 0x04 end
    if has_byte_flag(original_low, 0x08) then low = low + 0x08 end
    if low ~= original_low then _G.memory.writebyte(address, low) end
    if original_high ~= 0 then _G.memory.writebyte(address + 1, 0) end
end

local function apply_auto_run_at(address)
    if address == addresses.ADDR_BUTTONS_PRESSED then return end

    local original_low = _G.memory.readbyte(address)
    local original_high = _G.memory.readbyte(address + 1)
    local right = has_byte_flag(original_low, 0x10)
    local left = has_byte_flag(original_low, 0x20)
    if right ~= left then
        state.input_trap_state.auto_direction = right and 1 or -1
    end

    local low = clear_byte_flag(clear_byte_flag(original_low, 0x10), 0x20)
    if state.input_trap_state.auto_direction < 0 then
        low = set_byte_flag(low, 0x20)
    else
        low = set_byte_flag(low, 0x10)
    end
    local high = set_byte_flag(original_high, 0x08) -- Y always dashes.

    if low ~= original_low then _G.memory.writebyte(address, low) end
    if high ~= original_high then _G.memory.writebyte(address + 1, high) end
end

local function apply_sticky_buttons_at(address)
    local original_low = _G.memory.readbyte(address)
    local right = has_byte_flag(original_low, 0x10)
    local left = has_byte_flag(original_low, 0x20)
    local frame = emu and emu.framecount and emu.framecount() or 0

    if frame ~= state.input_trap_state.sticky_last_frame then
        state.input_trap_state.sticky_last_frame = frame
        if right ~= left then
            state.input_trap_state.sticky_direction = right and 1 or -1
            state.input_trap_state.sticky_frames = state.input_trap_state.sticky_duration
        elseif state.input_trap_state.sticky_frames > 0 then
            state.input_trap_state.sticky_frames = state.input_trap_state.sticky_frames - 1
        end
    end

    -- Never synthesize a newly-pressed edge; only latch held movement.
    if address == addresses.ADDR_BUTTONS_PRESSED
        or right or left
        or state.input_trap_state.sticky_frames <= 0 then
        return
    end

    local low = original_low
    if state.input_trap_state.sticky_direction < 0 then
        low = set_byte_flag(low, 0x20)
    elseif state.input_trap_state.sticky_direction > 0 then
        low = set_byte_flag(low, 0x10)
    end
    if low ~= original_low then _G.memory.writebyte(address, low) end
end

local function set_camera_shoulder_at(address, direction)
    local original_high = _G.memory.readbyte(address + 1)
    -- DS keypad high byte: R=0x01 and L=0x02.
    local high = clear_byte_flag(clear_byte_flag(original_high, 0x01), 0x02)
    if direction < 0 then
        high = set_byte_flag(high, 0x02)
    elseif direction > 0 then
        high = set_byte_flag(high, 0x01)
    end
    if high ~= original_high then _G.memory.writebyte(address + 1, high) end
end

local function apply_camera_trap_at(address)
    local elapsed = math.max(0, context.trap_total_frames - context.trap_remaining_frames)
    local direction = state.input_trap_state.camera_direction
    if context.active_mode == "camera_drift" then
        local ramping = elapsed < state.input_trap_state.camera_drift_ramp_frames
        local pulse_frame = elapsed % state.input_trap_state.camera_drift_pulse_period
        if address == addresses.ADDR_BUTTONS_PRESSED then
            direction = ramping and pulse_frame == 0 and direction or 0
        elseif ramping and pulse_frame >= state.input_trap_state.camera_drift_pulse_frames then
            direction = 0
        end
    elseif context.active_mode == "camera_sway" then
        if address == addresses.ADDR_BUTTONS_PRESSED then return end
        direction = math.floor(elapsed / state.input_trap_state.camera_sway_period) % 2 == 0 and -1 or 1
    end
    set_camera_shoulder_at(address, direction)
end

local function apply_boo_curse_at(address)
    local elapsed = math.max(0, context.trap_total_frames - context.trap_remaining_frames)
    if elapsed % state.input_trap_state.boo_cycle_frames >= state.input_trap_state.boo_reverse_frames then
        return
    end

    local original_low = _G.memory.readbyte(address)
    local right = has_byte_flag(original_low, 0x10)
    local left = has_byte_flag(original_low, 0x20)
    if right == left then return end
    local low = clear_byte_flag(clear_byte_flag(original_low, 0x10), 0x20)
    low = set_byte_flag(low, right and 0x20 or 0x10)
    _G.memory.writebyte(address, low)
end

local function apply_input_filter_at(address)
    if context.trap_remaining_frames <= 0 then
        return
    end

    local filter = nil
    if context.active_mode == "no_jump" then
        filter = clear_jump_buttons_at
    elseif context.active_mode == "im_stuck" then
        filter = state.input_trap_state.clear_im_stuck_at
    elseif context.active_mode == "no_sprint" then
        filter = clear_sprint_buttons_at
    elseif context.active_mode == "button_roulette" then
        filter = remap_button_roulette_at
    elseif context.active_mode == "auto_run" then
        filter = apply_auto_run_at
    elseif context.active_mode == "sticky_buttons" then
        filter = apply_sticky_buttons_at
    elseif context.active_mode == "camera_drift"
        or context.active_mode == "camera_sway" then
        filter = apply_camera_trap_at
    elseif context.active_mode == "boo_curse" then
        filter = apply_boo_curse_at
    end
    if filter == nil then return end

    filter(address)
end

local function apply_general_input_filter()
    apply_input_filter_at(addresses.ADDR_PRESSED_KEYS)
end

local function apply_button_input_filter()
    apply_input_filter_at(addresses.ADDR_BUTTONS_HELD)
    apply_input_filter_at(addresses.ADDR_BUTTONS_PRESSED)
end

function M.ensure_input_filter_hooks()
    if context.input_filter_hooks_initialized or context.input_filter_hooks_attempted then
        return
    end
    context.input_filter_hooks_attempted = true
    if not event or not event.onframestart then
        return
    end
    local ok, hook_id = pcall(
        event.onframestart,
        M.apply_frame_start_input_filter,
        "nsmbds_input_filter_frame_start"
    )
    context.input_filter_hooks_initialized = ok and hook_id ~= nil
end

function M.disable_input_filter_hooks()
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, "nsmbds_input_filter_frame_start")
        pcall(event.unregisterbyname, "nsmbds_input_filter_general_after_write")
        pcall(event.unregisterbyname, "nsmbds_input_filter_buttons_after_write")
    end
    context.input_filter_hooks_initialized = false
    context.input_filter_hooks_attempted = false
end

function M.update_input_filter_hooks(has_active_player)
    local needs_frame_start_filter = has_active_player
        and context.trap_remaining_frames > 0
        and context.active_mode == "no_jump"
    if needs_frame_start_filter then
        M.ensure_input_filter_hooks()
    elseif context.input_filter_hooks_initialized or context.input_filter_hooks_attempted then
        M.disable_input_filter_hooks()
    end
end

function M.apply_frame_start_input_filter()
    if context.active_mode ~= "no_jump"
        or context.trap_remaining_frames <= 0
        or not joypad
        or not joypad.set then
        return
    end

    -- Override controller input before NSMBDS copies it into game RAM.  The
    -- previous frame-end RAM filter ran after the game had already accepted a
    -- jump. A always jumps; B/X depends on the in-game control option.
    local blocked = { A = false }
    if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
        blocked.B = false
    else
        blocked.X = false
    end
    joypad.set(blocked, 1)
end

function M.apply_trap_input_filter()
    apply_general_input_filter()
    apply_button_input_filter()
end

function M.poll_and_update_traps(has_active_player, trap_player)
    if context.trap_remaining_frames == 0 and has_active_player then
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
        elseif trigger_code == 7 or trigger_code == 8 then
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
                    context.active_mode = "bonk_hit"
                else
                    if trigger_code == 7 then
                        _G.memory.write_u32_le(addresses.ADDR_TIMER, 0)
                        context.trap_remaining_frames = BONK_FEEDBACK_FRAMES
                        context.trap_total_frames = BONK_FEEDBACK_FRAMES
                        context.active_mode = "bonk_fatal"
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

    if context.trap_remaining_frames > 0 and has_active_player then
        context.trap_remaining_frames = context.trap_remaining_frames - 1
        if trap_player then
            local mode = context.active_mode
            if mode == "no_jump"
                or mode == "no_sprint"
                or mode == "button_roulette"
                or mode == "auto_run"
                or mode == "sticky_buttons"
                or mode == "camera_drift"
                or mode == "camera_sway"
                or mode == "boo_curse"
                or mode == "im_stuck" then
                -- Camera effects are intentionally polled once per frame.
                -- Memory-execute callbacks caused audio underruns on BizHawk.
                M.apply_trap_input_filter()
                if mode == "auto_run" then
                    local pad = joypad and joypad.getimmediate and joypad.getimmediate(1)
                    if not pad or next(pad) == nil then
                        pad = joypad and joypad.get and joypad.get(1)
                    end
                    if pad and pad.Right ~= pad.Left then
                        state.input_trap_state.auto_direction = pad.Right and 1 or -1
                    end
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
            else
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

    M.update_input_filter_hooks(has_active_player)
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

function state.input_trap_state.finish_timed_trap()
    if context.active_mode == "screen_flip" then
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

function state.input_trap_state.draw_visual_trap()
    if not gui or not gui.drawBox then return end

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
        local shade = 0xFA000000

        local screen_w, screen_h = 256, 192
        local screen_x, screen_y = 0, 0

        local layout = nds.getscreenlayout()
        local gap = nds.getscreengap()
        local inverted = nds.getscreeninvert()
        local powcnt1 = _G.memory.read_u16_le(0x04000304, memory.sys_bus_domain)
        local main_on_top = (powcnt1 & 0x8000) ~= 0
        local main_is_first = main_on_top ~= inverted
        if layout == "Vertical" and not main_is_first then
            screen_y = screen_h + gap
        elseif layout == "Horizontal" and not main_is_first then
            screen_x = screen_w + gap
        end

        local spot_w = 60
        local spot_h = 65

        local offset_x = 0
        local offset_y = 0

        local cx = 128
        local cy = 150

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

                cx = math.floor((raw_x + camera_x) / stage_zoom) + offset_x
                local camera_term = (raw_y + camera_y) / stage_zoom
                cy = 180 - math.floor(camera_term) + offset_y
            end
            cx = math.max(0, math.min(screen_w - 1, cx))
            cy = math.max(0, math.min(screen_h - 1, cy))
        end

        local x1 = math.max(0, math.min(screen_w - 1, math.floor(cx - spot_w / 2)))
        local x2 = math.max(0, math.min(screen_w - 1, math.floor(cx + spot_w / 2)))
        local y1 = math.max(0, math.min(screen_h - 1, math.floor(cy - spot_h / 2)))
        local y2 = math.max(0, math.min(screen_h - 1, math.floor(cy + spot_h / 2)))

        if y1 > 0 then
            gui.drawBox(screen_x, screen_y, screen_x + screen_w - 1, screen_y + y1 - 1, shade, shade)
        end
        if y2 < screen_h - 1 then
            gui.drawBox(screen_x, screen_y + y2 + 1, screen_x + screen_w - 1, screen_y + screen_h - 1, shade, shade)
        end
        if x1 > 0 then
            gui.drawBox(screen_x, screen_y + y1, screen_x + x1 - 1, screen_y + y2, shade, shade)
        end
        if x2 < screen_w - 1 then
            gui.drawBox(screen_x + x2 + 1, screen_y + y1, screen_x + screen_w - 1, screen_y + screen_h - 1, shade, shade)
        end
    end
end


function M.draw_trap_status_hud()
    if not gui or not gui.drawBox or not gui.drawText then return end
    if context.trap_remaining_frames <= 0 then return end
    if state.notification_state.active ~= nil
        and state.notification_state.active.kind == state.notification_state.kind.trap_blocked then
        return
    end

    local title = "TRAP ACTIVE"
    local color = "red"

    if context.active_mode == "hyper" then
        title = "SUPER SPEED"
        color = "red"
    elseif context.active_mode == "slow" then
        title = "SLOWNESS"
        color = "cyan"
    elseif context.active_mode == "walljump_lock" then
        title = "SLIPPERY GLOVES"
        color = "yellow"
    elseif context.active_mode == "no_jump" then
        title = "GROUND BOUND"
        color = "orange"
    elseif context.active_mode == "reverse_controls" then
        title = "HYPER CONFUSION"
        color = "purple"
    elseif context.active_mode == "no_sprint" then
        title = "NO SPRINT"
        color = "orange"
    elseif context.active_mode == "button_roulette" then
        title = "BUTTON SWAP"
        color = "purple"
    elseif context.active_mode == "ice_shoes" then
        title = "ICE SHOES"
        color = "cyan"
    elseif context.active_mode == "heavy_mario" then
        title = "HEAVY MARIO"
        color = "orange"
    elseif context.active_mode == "auto_run" then
        title = "CAN'T STOP"
        color = "red"
    elseif context.active_mode == "sticky_buttons" then
        title = "STICKY BUTTONS"
        color = "yellow"
    elseif context.active_mode == "camera_drift" then
        title = "CAMERA DRIFT"
        color = "purple"
    elseif context.active_mode == "screen_flip" then
        title = "SCREEN FLIP"
        color = "purple"
    elseif context.active_mode == "camera_sway" then
        title = "DRUNK CAMERA"
        color = "purple"
    elseif context.active_mode == "boo_curse" then
        title = "BOO CURSE"
        color = "purple"
    elseif context.active_mode == "im_stuck" then
        title = "I'M STUCK"
        color = "yellow"
    elseif context.active_mode == "screen_tint" then
        title = "SCREEN TINT"
        color = "purple"
    elseif context.active_mode == "retro_filter" then
        title = "RETRO FILTER"
        color = "orange"
    elseif context.active_mode == "spotlight" then
        title = "SPOTLIGHT"
        color = "yellow"
    elseif context.active_mode == "ground_clap" then
        title = "GROUND CLAP"
        color = "red"
    elseif context.active_mode == "head_bonk" then
        title = "HEAD BONK"
        color = "red"
    elseif context.active_mode == "crazy_pixels" then
        title = "PIXELATION"
        color = "purple"
    elseif context.active_mode == "coin_tax_notice" then
        title = "COIN TAX -10"
        color = "red"
    elseif context.active_mode == "timer_drain_notice" then
        title = "TIME DRAIN"
        color = "red"
    elseif context.active_mode == "coin_thief_notice" then
        title = "COIN THIEF"
        color = "red"
    elseif context.active_mode == "bonk_hit" or context.active_mode == "bonk_fatal" or context.active_mode == "bonk_protected" then
        title = "BONK TRAP"
        color = "red"
    end

    local x1, y1, x2, y2 = 158, 20, 250, 37
    gui.drawBox(x1, y1, x2, y2, "black", 0xD011111B)
    gui.drawBox(x1, y1, x1 + 2, y2, color, color)
    gui.drawText(x1 + 4, y1 + 2, title, "white", "clear", 10)

    if context.trap_total_frames > 0 then
        local bar_x1 = x1 + 4
        local bar_x2_max = x2 - 3
        local bar_y = y2 - 3
        local bar_width = bar_x2_max - bar_x1
        local fill_width = math.max(
            0,
            math.floor(bar_width * (context.trap_remaining_frames / context.trap_total_frames))
        )
        gui.drawBox(bar_x1, bar_y, bar_x2_max, bar_y, "gray", "gray")
        if fill_width > 0 then
            gui.drawBox(bar_x1, bar_y, bar_x1 + fill_width, bar_y, color, color)
        end
    end
end

function state.input_trap_state.apply_action_damage(player)
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
