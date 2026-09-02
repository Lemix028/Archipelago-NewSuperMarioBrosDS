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
local context = state.context

local LONG_TRAP_FRAMES = constants.LONG_TRAP_FRAMES
local BONK_FEEDBACK_FRAMES = constants.BONK_FEEDBACK_FRAMES
local BASE_MAX_SPEED = constants.BASE_MAX_SPEED
local HYPER_TARGET = constants.HYPER_TARGET
local SLOW_TARGET = constants.SLOW_TARGET
local ICE_GRIP_COMPENSATION = constants.ICE_GRIP_COMPENSATION
local input_filter_hook_warning_printed = false
local memory_input_filter_hooks_initialized = false
local input_filter_hook_kind = nil
local camera_held_flag = 0
local camera_pressed_flag = 0
local camera_filters_pressed = false

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
    elseif mode == "no_turnaround" then
        state.input_trap_state.no_turnaround_direction = 0
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
    local low = clear_byte_flag(original_low, 0x01) -- A always jumps.
    local high = original_high

    -- B and X swap between jump and dash with the control option.
    if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
        low = clear_byte_flag(low, 0x02)
    else
        high = clear_byte_flag(high, 0x04)
    end

    if low ~= original_low then _G.memory.writebyte(address, low) end
    if high ~= original_high then _G.memory.writebyte(address + 1, high) end
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

local function camera_shoulder_flag(direction)
    if direction < 0 then return 0x02 end
    if direction > 0 then return 0x01 end
    return 0
end

local function set_camera_shoulder_flag_at(address, shoulder_flag)
    local original_high = _G.memory.readbyte(address + 1)
    -- DS keypad high byte: R=0x01 and L=0x02.
    local high = original_high - original_high % 4 + shoulder_flag
    if high ~= original_high then _G.memory.writebyte(address + 1, high) end
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
        camera_filters_pressed = true
    else
        direction = math.floor(elapsed / state.input_trap_state.camera_sway_period) % 2 == 0 and -1 or 1
        camera_held_flag = camera_shoulder_flag(direction)
        camera_pressed_flag = 0
        camera_filters_pressed = false
    end
end

local function apply_camera_trap_at(address)
    if address == addresses.ADDR_BUTTONS_PRESSED then
        if not camera_filters_pressed then return end
        set_camera_shoulder_flag_at(address, camera_pressed_flag)
        return
    end
    set_camera_shoulder_flag_at(address, camera_held_flag)
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

local function apply_no_turnaround_at(address)
    local original_low = _G.memory.readbyte(address)
    local right = has_byte_flag(original_low, 0x10)
    local left = has_byte_flag(original_low, 0x20)
    if right == left then return end

    local requested_direction = right and 1 or -1
    local locked_direction = state.input_trap_state.no_turnaround_direction
    if locked_direction == 0 then
        state.input_trap_state.no_turnaround_direction = requested_direction
        return
    end
    if requested_direction == locked_direction then return end

    local blocked_flag = requested_direction > 0 and 0x10 or 0x20
    local low = clear_byte_flag(original_low, blocked_flag)
    if low ~= original_low then _G.memory.writebyte(address, low) end
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
    elseif context.active_mode == "no_turnaround" then
        filter = apply_no_turnaround_at
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

-- Camera Traps keep the exact two execute-hook addresses used by the generic
-- input filter, but skip mode dispatch and per-callback pulse calculations.
local function apply_camera_general_input_filter()
    if context.trap_remaining_frames <= 0 then return end
    set_camera_shoulder_flag_at(addresses.ADDR_PRESSED_KEYS, camera_held_flag)
end

local function apply_camera_button_input_filter()
    if context.trap_remaining_frames <= 0 then return end
    set_camera_shoulder_flag_at(addresses.ADDR_BUTTONS_HELD, camera_held_flag)
    if camera_filters_pressed then
        set_camera_shoulder_flag_at(addresses.ADDR_BUTTONS_PRESSED, camera_pressed_flag)
    end
end

function M.ensure_input_filter_hooks()
    local hook_kind = "generic"
    if context.active_mode == "camera_drift" or context.active_mode == "camera_sway" then
        hook_kind = "camera"
    end
    if context.input_filter_hooks_initialized then
        if input_filter_hook_kind == hook_kind then return true end
        -- A new trap can replace an active one. Do not retain the previous
        -- trap's specialized callbacks; this runs only when the kind changes.
        M.disable_input_filter_hooks()
    end

    context.input_filter_hooks_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if on_execute then
        local scope = memory.sys_bus_domain or memory.domain
        local general_hook_address = memory.sys_bus_domain
            and constants.SYS_INPUT_GENERAL_AFTER_WRITE
            or memory.to_domain_addr(constants.SYS_INPUT_GENERAL_AFTER_WRITE)
        local buttons_hook_address = memory.sys_bus_domain
            and constants.SYS_INPUT_BUTTONS_AFTER_WRITE
            or memory.to_domain_addr(constants.SYS_INPUT_BUTTONS_AFTER_WRITE)
        local general_filter = apply_general_input_filter
        local button_filter = apply_button_input_filter
        if hook_kind == "camera" then
            general_filter = apply_camera_general_input_filter
            button_filter = apply_camera_button_input_filter
        end
        local general_ok, general_error = pcall(
            on_execute,
            general_filter,
            general_hook_address,
            "nsmbds_input_filter_general_after_write",
            scope
        )
        local buttons_ok, buttons_error = pcall(
            on_execute,
            button_filter,
            buttons_hook_address,
            "nsmbds_input_filter_buttons_after_write",
            scope
        )
        memory_input_filter_hooks_initialized = general_ok and buttons_ok
        if memory_input_filter_hooks_initialized then
            context.input_filter_hooks_initialized = true
            input_filter_hook_kind = hook_kind
            input_filter_hook_warning_printed = false
            return true
        end

        if event.unregisterbyname then
            pcall(event.unregisterbyname, "nsmbds_input_filter_general_after_write")
            pcall(event.unregisterbyname, "nsmbds_input_filter_buttons_after_write")
        end
        if not input_filter_hook_warning_printed then
            local hook_error = not general_ok and general_error or buttons_error
            print(
                "NSMBDS input Trap execute-hook registration failed: "
                .. tostring(hook_error)
                .. "; trying frame-start fallback."
            )
            input_filter_hook_warning_printed = true
        end
    end

    if event and event.onframestart then
        local ok, hook_error = pcall(
            event.onframestart,
            M.apply_frame_start_input_filter,
            "nsmbds_input_filter_frame_start"
        )
        context.input_filter_hooks_initialized = ok
        if ok then
            input_filter_hook_kind = hook_kind
            return true
        end
        if not input_filter_hook_warning_printed then
            print("NSMBDS input Trap fallback registration failed: " .. tostring(hook_error))
            input_filter_hook_warning_printed = true
        end
    end

    if not input_filter_hook_warning_printed then
        print("NSMBDS input Trap hooks unavailable in this BizHawk core.")
        input_filter_hook_warning_printed = true
    end
    context.input_filter_hooks_initialized = false
    return false
end

function M.disable_input_filter_hooks()
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, "nsmbds_input_filter_frame_start")
        pcall(event.unregisterbyname, "nsmbds_input_filter_general_after_write")
        pcall(event.unregisterbyname, "nsmbds_input_filter_buttons_after_write")
    end
    memory_input_filter_hooks_initialized = false
    input_filter_hook_kind = nil
    camera_held_flag = 0
    camera_pressed_flag = 0
    camera_filters_pressed = false
    context.input_filter_hooks_initialized = false
    context.input_filter_hooks_attempted = false
    input_filter_hook_warning_printed = false
end

function M.update_input_filter_hooks(has_active_player)
    local mode = context.active_mode
    local needs_input_filter = has_active_player
        and context.trap_remaining_frames > 0
        and (mode == "no_jump"
            or mode == "im_stuck"
            or mode == "no_sprint"
            or mode == "button_roulette"
            or mode == "auto_run"
            or mode == "sticky_buttons"
            or mode == "camera_drift"
            or mode == "camera_sway"
            or mode == "boo_curse"
            or mode == "no_turnaround")
    if needs_input_filter then
        M.ensure_input_filter_hooks()
        -- Installation can clear the previous trap's cached flags. Refresh
        -- afterwards, before emulation resumes and either input hook fires.
        if mode == "camera_drift" or mode == "camera_sway" then
            refresh_camera_filter_state()
        end
    elseif context.input_filter_hooks_initialized or context.input_filter_hooks_attempted then
        M.disable_input_filter_hooks()
    end
end

function M.apply_frame_start_input_filter()
    -- Fallback only: combining this with the RAM hook would reverse Boo twice.
    if memory_input_filter_hooks_initialized then return end
    local mode = context.active_mode
    if context.trap_remaining_frames <= 0
        or (mode ~= "no_jump"
            and mode ~= "camera_drift"
            and mode ~= "camera_sway"
            and mode ~= "boo_curse"
            and mode ~= "no_turnaround")
        or not joypad
        or not joypad.set then
        return
    end

    local filtered = {}
    if mode == "no_jump" then
        -- A is always jump. B and X swap between jump and dash.
        filtered.A = false
        if _G.memory.readbyte(addresses.ADDR_CONTROL_OPTIONS) == 1 then
            filtered.B = false
        else
            filtered.X = false
        end
    elseif mode == "camera_drift" or mode == "camera_sway" then
        local elapsed = math.max(
            0,
            context.trap_total_frames - context.trap_remaining_frames
        )
        local direction = state.input_trap_state.camera_direction
        local apply_direction = true

        if mode == "camera_drift" then
            local ramping = elapsed < state.input_trap_state.camera_drift_ramp_frames
            local pulse_frame = elapsed % state.input_trap_state.camera_drift_pulse_period
            apply_direction = not ramping
                or pulse_frame < state.input_trap_state.camera_drift_pulse_frames
        else
            direction = math.floor(
                elapsed / state.input_trap_state.camera_sway_period
            ) % 2 == 0 and -1 or 1
        end

        filtered.L = apply_direction and direction < 0
        filtered.R = apply_direction and direction > 0
    elseif mode == "boo_curse" then
        local elapsed = math.max(
            0,
            context.trap_total_frames - context.trap_remaining_frames
        )
        local pad = nil
        if joypad.getimmediate then
            local ok, immediate = pcall(joypad.getimmediate, 1)
            if ok and type(immediate) == "table" then pad = immediate end
        end
        if pad == nil and joypad.get then
            local ok, current = pcall(joypad.get, 1)
            if ok and type(current) == "table" then pad = current end
        end
        if pad == nil then return end

        local reversing = elapsed % state.input_trap_state.boo_cycle_frames
            < state.input_trap_state.boo_reverse_frames
        if reversing then
            filtered.Left = pad.Right == true
            filtered.Right = pad.Left == true
        else
            filtered.Left = pad.Left == true
            filtered.Right = pad.Right == true
        end
    elseif mode == "no_turnaround" then
        local pad = nil
        if joypad.getimmediate then
            local ok, immediate = pcall(joypad.getimmediate, 1)
            if ok and type(immediate) == "table" then pad = immediate end
        end
        if pad == nil and joypad.get then
            local ok, current = pcall(joypad.get, 1)
            if ok and type(current) == "table" then pad = current end
        end
        if pad == nil or pad.Right == pad.Left then return end

        local requested_direction = pad.Right and 1 or -1
        local locked_direction = state.input_trap_state.no_turnaround_direction
        if locked_direction == 0 then
            state.input_trap_state.no_turnaround_direction = requested_direction
        elseif requested_direction ~= locked_direction then
            filtered.Right = requested_direction < 0 and pad.Right == true
            filtered.Left = requested_direction > 0 and pad.Left == true
        end
    end

    local ok, error_message = pcall(joypad.set, filtered, 1)
    if not ok and not input_filter_hook_warning_printed then
        print("NSMBDS input Trap filter failed: " .. tostring(error_message))
        input_filter_hook_warning_printed = true
    end
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
        elseif trigger_code == 32 then
            M.begin_timed_trap("no_turnaround", LONG_TRAP_FRAMES)
        elseif trigger_code == 33 then
            M.begin_timed_trap("powerup_pickpocket_notice", BONK_FEEDBACK_FRAMES)
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
            if mode == "auto_run" or mode == "im_stuck" then
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
    state.input_trap_state.no_turnaround_direction = 0
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
         render_spotlight()
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
