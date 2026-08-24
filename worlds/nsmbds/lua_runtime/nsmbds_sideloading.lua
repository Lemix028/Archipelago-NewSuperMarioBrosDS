-- =============================================================================
-- NSMBDS Archipelago Sideloading
-- Orchestrator Module
-- =============================================================================

-- Reload modules when the script is loaded again.
for k in pairs(package.loaded) do
    if k:find("^nsmbds%.") then
        package.loaded[k] = nil
    end
end

-- Load the shared helpers and feature modules.
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local actors = require("nsmbds.actors")
local hooks = require("nsmbds.hooks")
local blocksanity = require("nsmbds.blocksanity")
local protection = require("nsmbds.protection")
local mini_castles = require("nsmbds.mini_castles")
local red_coins = require("nsmbds.red_coins")
require("nsmbds.notifications")
local hud = require("nsmbds.hud")
local emulator_feed = require("nsmbds.emulator_feed")
local traps = require("nsmbds.traps")
local runtime = require("nsmbds.runtime")
local context = state.context
local GROUND_POUND_HOOK_ARM_FRAMES = 60
local reported_ui_errors = {}

local function version_is_at_least(version, minimum)
    local major, minor, patch = version:match("^(%d+)%.(%d+)%.(%d+)$")
    local minimum_major, minimum_minor, minimum_patch = minimum:match("^(%d+)%.(%d+)%.(%d+)$")
    if not major or not minimum_major then return false end

    major, minor, patch = tonumber(major), tonumber(minor), tonumber(patch)
    minimum_major, minimum_minor, minimum_patch =
        tonumber(minimum_major), tonumber(minimum_minor), tonumber(minimum_patch)

    if major ~= minimum_major then return major > minimum_major end
    if minor ~= minimum_minor then return minor > minimum_minor end
    return patch >= minimum_patch
end

local function check_bizhawk_version()
    local detected_version = nil
    if client ~= nil then
        local ok, value = pcall(function()
            return client.getversion()
        end)
        if ok and value ~= nil then
            detected_version = tostring(value)
        end
    end

    local normalized_version = detected_version
        and detected_version:match("(%d+%.%d+%.%d+)")
        or nil
    if not normalized_version
        or not version_is_at_least(normalized_version, constants.MINIMUM_BIZHAWK_VERSION)
    then
        local warning = string.format(
            "NSMBDS WARNING: UNSUPPORTED BIZHAWK VERSION '%s' - MINIMUM REQUIRED: %s. "
                .. "CONTINUING, BUT THE RUNTIME MAY FAIL!",
            detected_version or "unknown",
            constants.MINIMUM_BIZHAWK_VERSION
        )
        local console_warning = "!!! " .. warning .. " !!!"
        for _ = 1, 10 do
            print(console_warning)
        end

        emulator_feed.push({
            segments = {
                {text = warning, color = "warning"},
            },
        })
    end
end

local function call_ui_safely(label, callback, ...)
    local ok, error_message = pcall(callback, ...)
    if not ok and not reported_ui_errors[label] then
        reported_ui_errors[label] = true
        print("NSMBDS " .. label .. " error: " .. tostring(error_message))
    end
end

emulator_feed.initialize()
check_bizhawk_version()
-- Remove any high-frequency input hooks left by an older loaded revision.
traps.disable_input_filter_hooks()

-- Remove hooks that are only needed during gameplay.
local function disable_gameplay_observer_hooks()
    hooks.disable_change_tile_execute_hook()
    hooks.disable_hit_block_execute_hook()
    if event and event.unregisterbyname then
        pcall(event.unregisterbyname, "NSMBDS Red Coin Counter 1")
        pcall(event.unregisterbyname, "NSMBDS Red Coin Counter 2")
    end
    context.red_coin_write_hook_initialized = false
    context.last_observed_lives = nil
    context.ground_pound_hook_armed_frames = 0
    context.ground_pound_down_held = false
end

-- Remove every hook owned by this script.
local function disable_all_hooks()
    traps.disable_input_filter_hooks()
    disable_gameplay_observer_hooks()
end

-- Main per-frame update called by BizHawk.
local function sideloading_tick()
    -- Stop gameplay features while no ROM is loaded.
    if not memory.is_rom_loaded() then
        disable_all_hooks()
        -- Remove visual traps immediately when leaving gameplay
        if gui and gui.clearGraphics then gui.clearGraphics() end
        context.is_initialized = false
        context.cached_player_object = nil
        return
    end

    if not runtime.ensure_initialized() then
        return
    end

    -- Clean up invalid mailbox events before reading new events.
    pcall(red_coins.clear_invalid_pending_red_coin_event)
    pcall(blocksanity.clear_invalid_pending_block_event)

    for index, counter_address in ipairs(addresses.ADDR_RED_COIN_COUNTERS) do
        local ok_red_coin, red_coin_count = pcall(_G.memory.readbyte, counter_address)
        if ok_red_coin and red_coin_count ~= nil then
            red_coins.observe_red_coin_counter(index, red_coin_count)
        end
    end
    pcall(red_coins.publish_pending_red_coin_completion)

    -- Check for a lost life before refreshing the player state.
    pcall(protection.poll_life_insurance)

    -- Read Mario and the current actor list.
    local frame = emu and emu.framecount and emu.framecount() or 0
    local had_player_last_frame = context.previous_frame_had_player
    local should_scan_actors = had_player_last_frame or frame % 4 == 0
    local objects = {}
    local player = nil
    if should_scan_actors then
        objects = actors.get_active_objects()
        player = actors.find_player_object(objects, context.cached_player_object)
    end
    local has_active_player = player ~= nil
    context.previous_frame_had_player = has_active_player
    context.cached_player_object = player
    state.input_trap_state.active_player = player

    if player ~= nil then
        state.input_trap_state.player_was_moving_up = _G.memory.read_s32_le(
            memory.to_domain_addr(player + constants.PLAYER_Y_VELOCITY_OFFSET)
        ) > 0
    else
        state.input_trap_state.player_was_moving_up = false
    end

    -- Reset observer state after a pause, rewind, or large frame jump.
    if context.last_observer_frame ~= nil
        and (frame <= context.last_observer_frame or frame > context.last_observer_frame + 5) then
        blocksanity.reset_block_observer_state()
    end
    context.last_observer_frame = frame

    -- Run observers and native hooks while Mario is in a level.
    if has_active_player then
        if context.active_mode == "crazy_pixels"
            and state.input_trap_state.crazy_pixels_suspended then
            state.input_trap_state.resume_crazy_pixels()
        end
        if context.active_mode == "screen_flip"
            and state.input_trap_state.screen_flip_suspended then
            state.input_trap_state.resume_screen_flip()
        end
        -- Arm the expensive native hooks only after a fresh Down press.  A
        -- Ground Pound cannot impact before that input, so this captures exact
        -- one- and two-block hits without paying callback cost throughout the
        -- rest of an actor-heavy level.
        local pad = joypad and joypad.get and joypad.get(1) or nil
        local down_held = pad ~= nil and pad.Down == true
        if down_held and not context.ground_pound_down_held then
            context.ground_pound_hook_armed_frames = GROUND_POUND_HOOK_ARM_FRAMES
            context.native_tile_changes = {}
            context.native_block_hits = {}
            context.native_tile_change_write_index = 1
            context.native_block_hit_write_index = 1
        end
        context.ground_pound_down_held = down_held

        local ground_pound_hooks_armed = context.ground_pound_hook_armed_frames > 0
        if ground_pound_hooks_armed then
            hooks.ensure_change_tile_execute_hook()
        else
            hooks.disable_change_tile_execute_hook()
        end
        if ground_pound_hooks_armed or context.active_mode == "head_bonk" then
            hooks.ensure_hit_block_execute_hook()
        else
            hooks.disable_hit_block_execute_hook()
        end
        red_coins.ensure_red_coin_write_hook()
        pcall(blocksanity.observe_ground_pound_blocks, player)
        pcall(blocksanity.observe_block_bumps, objects)
        pcall(blocksanity.finalize_ground_pound_capture)
        if context.ground_pound_hook_armed_frames > 0 then
            context.ground_pound_hook_armed_frames = context.ground_pound_hook_armed_frames - 1
        end
    elseif had_player_last_frame then
        -- Mario left the level: stop gameplay-only effects and hooks.
        if context.active_mode == "crazy_pixels" then
            state.input_trap_state.suspend_crazy_pixels()
        end
        if context.active_mode == "screen_flip" then
            state.input_trap_state.suspend_screen_flip()
        end
        disable_gameplay_observer_hooks()
        blocksanity.reset_block_observer_state()
        if gui and gui.clearGraphics then gui.clearGraphics() end
    end

    -- Castle completion flags can change after the player actor disappears
    -- during the exit transition. Keep the cached Mini state alive through
    -- that transition instead of observing only active gameplay frames.
    pcall(mini_castles.observe_mini_castle_completion, player)

    -- Publish one queued Blocksanity event to the mailbox.
    pcall(blocksanity.publish_next_block_event)

    -- Apply incoming traps and draw the in-game UI.
    traps.poll_and_update_traps(has_active_player, player)

    -- Clear once before redrawing the complete AP HUD to avoid components
    -- erasing each other during large item deliveries.
    if gui and gui.clearGraphics then gui.clearGraphics() end
    local notification_snapshot = state.notification_state.capture_snapshot(false)
    pcall(state.notification_state.receive, notification_snapshot)
    call_ui_safely("protection HUD", hud.draw_protection_hud, notification_snapshot)
    call_ui_safely("notification HUD", state.notification_state.draw)
    if has_active_player then
        call_ui_safely("visual Trap renderer", state.input_trap_state.draw_visual_trap)
        call_ui_safely("Trap status HUD", hud.draw_trap_status_hud)
    end
    call_ui_safely("emulator feed", emulator_feed.draw)
end

-- Forward the frame event to the main update function.
local function sideloading_frame_end()
    sideloading_tick()
end

-- Restore temporary effects and remove hooks when the script exits.
local function sideloading_exit()
    pcall(state.input_trap_state.restore_screen_rotation)
    pcall(state.input_trap_state.suspend_crazy_pixels)
    pcall(disable_all_hooks)
    pcall(emulator_feed.shutdown)
    if gui and gui.clearGraphics then gui.clearGraphics() end
end

event.onframeend(
    sideloading_frame_end,
    "nsmbds_sideloading_tick"
)
if event.onexit then
    event.onexit(
        sideloading_exit,
        "nsmbds_sideloading_exit"
    )
end
