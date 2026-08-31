-- =============================================================================
-- lua/nsmbds/blocksanity.lua
-- Blocksanity and Ground-Pound detection
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")
local actors = require("nsmbds.actors")
local context = state.context


local block_event_queue = {}
local queued_block_events = {}
local MAX_QUEUED_BLOCK_EVENTS = 64

function M.block_event_key(event_type, world, level, area, tile_x, tile_y)
    -- Native and Actor fallback observations of the same static block must
    -- share one queue identity even if one classified the hit as a Ground
    -- Pound. Moving blocks retain their own namespace.
    local identity_type = event_type == constants.AP_EVENT_TYPE_MOVING_BLOCK_OPEN
        and event_type
        or 0
    return string.format("%d:%d:%d:%d:%d:%d", identity_type, world, level, area, tile_x, tile_y)
end

function M.clear_invalid_pending_block_event()
    local sequence = _G.memory.readbyte(addresses.ADDR_AP_BLOCK_EVENT_SEQUENCE)
    local acknowledged = _G.memory.readbyte(addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE)
    if sequence == acknowledged then
        return
    end

    local event_type = _G.memory.readbyte(addresses.ADDR_AP_BLOCK_EVENT_TYPE)
    local world = _G.memory.read_u32_le(addresses.ADDR_AP_BLOCK_EVENT_WORLD)
    if (event_type ~= constants.AP_EVENT_TYPE_BLOCK_BUMP
        and event_type ~= constants.AP_EVENT_TYPE_BLOCK_GROUND_POUND
        and event_type ~= constants.AP_EVENT_TYPE_MOVING_BLOCK_OPEN)
        or world > 7 then
        _G.memory.writebyte(addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, sequence)
    end
end

function M.queue_block_event(event_type, world, level, area, tile_x, tile_y)
    local key = M.block_event_key(event_type, world, level, area, tile_x, tile_y)
    if queued_block_events[key] then
        return
    end
    if #block_event_queue >= MAX_QUEUED_BLOCK_EVENTS then
        return
    end
    block_event_queue[#block_event_queue + 1] = {
        event_type = event_type,
        world = world,
        level = level,
        area = area,
        tile_x = tile_x,
        tile_y = tile_y,
        key = key,
    }
    queued_block_events[key] = true
end

function M.queue_block_object(object, known_tile_x, known_tile_y)
    local tile_x, tile_y = known_tile_x, known_tile_y
    if tile_x == nil or tile_y == nil then
        tile_x, tile_y = actors.object_tile(object)
    end
    local world, level, area = actors.current_course_identity()
    M.queue_block_event(
        constants.AP_EVENT_TYPE_BLOCK_BUMP,
        world,
        level,
        area,
        tile_x,
        tile_y
    )
end

-- Drain the exact coordinates captured inside the native Execute callback.
-- The callback also snapshots the course identity, so a transition after the
-- hit cannot relabel the event with the next area.
function M.observe_native_block_hits()
    if #context.native_block_hits == 0 then
        return
    end
    local hits = context.native_block_hits
    context.native_block_hits = {}
    context.native_block_hit_overflow_logged = false
    for _, hit in ipairs(hits) do
        M.queue_block_event(
            hit.event_type,
            hit.world,
            hit.level,
            hit.area,
            hit.tile_x,
            hit.tile_y
        )
    end
end

function M.publish_next_block_event()
    if #block_event_queue == 0 then
        return
    end

    local sequence = _G.memory.readbyte(addresses.ADDR_AP_BLOCK_EVENT_SEQUENCE)
    local acknowledged = _G.memory.readbyte(addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE)
    if sequence ~= acknowledged then
        return
    end

    local pending = block_event_queue[1]
    local next_sequence = (sequence + 1) % 256
    _G.memory.writebyte(addresses.ADDR_AP_BLOCK_EVENT_TYPE, pending.event_type)
    _G.memory.write_u32_le(addresses.ADDR_AP_BLOCK_EVENT_WORLD, pending.world)
    _G.memory.write_u32_le(addresses.ADDR_AP_BLOCK_EVENT_LEVEL, pending.level)
    _G.memory.write_u32_le(addresses.ADDR_AP_BLOCK_EVENT_AREA, pending.area)
    _G.memory.write_s32_le(addresses.ADDR_AP_BLOCK_EVENT_TILE_X, pending.tile_x)
    _G.memory.write_s32_le(addresses.ADDR_AP_BLOCK_EVENT_TILE_Y, pending.tile_y)
    _G.memory.writebyte(addresses.ADDR_AP_BLOCK_EVENT_SEQUENCE, next_sequence)
    queued_block_events[pending.key] = nil
    table.remove(block_event_queue, 1)
end




local known_actors = {
    object_types = {},
    object_tiles = {},
}
local known_object_classes = {}
local known_actor_seen_generation = {}
local actor_scan_generation = 0
local object_baseline_ready = false
local observed_course_key = nil
local previous_player_animation = nil
local ground_pound_capture = nil
local capture_actor_baseline_ready = false
local MOVING_BLOCK_ACTOR_TYPE = 0x0104
local MOVING_BLOCK_OPEN_STATE_OFFSET = 0x3E4
local known_moving_blocks = {}

function M.reset_block_observer_state()
    known_actors.object_types = {}
    known_actors.object_tiles = {}
    known_object_classes = {}
    known_actor_seen_generation = {}
    actor_scan_generation = 0
    object_baseline_ready = false
    observed_course_key = nil
    previous_player_animation = nil
    ground_pound_capture = nil
    capture_actor_baseline_ready = false
    known_moving_blocks = {}
end

local function tile_is_near_ground_pound(tile_x, tile_y)
    return ground_pound_capture ~= nil
        and math.abs(tile_x - ground_pound_capture.tile_x) <= 2
        and math.abs(tile_y - ground_pound_capture.tile_y) <= 2
end

local function moving_blocks_at_impact(tile_x, tile_y)
    local exact = {}
    local nearby = {}
    for _object, state in pairs(known_moving_blocks) do
        if state.current_x == tile_x and state.current_y == tile_y then
            exact[#exact + 1] = state
        elseif math.abs(state.current_x - tile_x) <= 1
            and math.abs(state.current_y - tile_y) <= 1 then
            nearby[#nearby + 1] = state
        end
    end
    if #exact > 0 then
        return exact
    end
    if #nearby == 1 then
        return nearby
    end
    return {}
end

local function capture_ground_pound_tile(tile_x, tile_y)
    if not tile_is_near_ground_pound(tile_x, tile_y) then
        return
    end
    local tile_key = string.format("%d:%d", tile_x, tile_y)
    if ground_pound_capture.captured_tiles[tile_key] then
        return
    end
    ground_pound_capture.captured_tiles[tile_key] = true

    -- A ground pound may open a moving block before its open-state transition
    -- is visible to the per-frame actor scan. Bind the native impact back to
    -- every exact moving actor and publish its immutable spawn coordinate.
    local moving_hits = moving_blocks_at_impact(tile_x, tile_y)
    if #moving_hits > 0 then
        for _, state in ipairs(moving_hits) do
            M.queue_block_event(
                constants.AP_EVENT_TYPE_MOVING_BLOCK_OPEN,
                ground_pound_capture.world,
                ground_pound_capture.level,
                ground_pound_capture.area,
                state.spawn_x,
                state.spawn_y
            )
        end
        return
    end

    M.queue_block_event(
        constants.AP_EVENT_TYPE_BLOCK_GROUND_POUND,
        ground_pound_capture.world,
        ground_pound_capture.level,
        ground_pound_capture.area,
        tile_x,
        tile_y
    )
end

-- Track ordinary bumps through the transient block actors.
function M.observe_block_bumps(objects)
    local world, level, area = actors.current_course_identity()
    if world > 7 or level > constants.MAX_RUNTIME_COURSE_LEVEL or area == 0xFF then
        return
    end
    local course_key = string.format("%d:%d:%d", world, level, area)
    if course_key ~= observed_course_key then
        known_actors.object_types = {}
        known_actors.object_tiles = {}
        known_object_classes = {}
        known_actor_seen_generation = {}
        actor_scan_generation = 0
        object_baseline_ready = false
        previous_player_animation = nil
        ground_pound_capture = nil
        capture_actor_baseline_ready = false
        known_moving_blocks = {}
        observed_course_key = course_key
    end

    -- Keep Actor sampling alive as a corroborating fallback. Native records
    -- are drained first, and block_event_key() deduplicates the same tile.
    local capture_actors = ground_pound_capture ~= nil
    if not capture_actors and capture_actor_baseline_ready then
        known_actors.object_tiles = {}
        known_object_classes = {}
        capture_actor_baseline_ready = false
    end
    actor_scan_generation = actor_scan_generation + 1
    local scan_generation = actor_scan_generation
    for _, object in ipairs(objects) do
        local type = actors.object_type(object)
        local previous_type = known_actors.object_types[object]
        known_actors.object_types[object] = type
        known_actor_seen_generation[object] = scan_generation

        -- Coordinates and class IDs used to be read for every enemy in every
        -- frame.  They are only needed for the short Ground-Pound capture
        -- window, for a newly changed block, or for a moving-block sample.
        local class_id = nil
        local tile_x, tile_y = nil, nil
        if capture_actors then
            local previous_class = known_object_classes[object]
            class_id = _G.memory.read_u16_le(
                memory.to_domain_addr(object + constants.OBJECT_CLASS_ID_OFFSET)
            )
            tile_x, tile_y = actors.object_tile(object)
            known_actors.object_tiles[object] = { tile_x, tile_y }
            known_object_classes[object] = class_id

            if object_baseline_ready
                and capture_actor_baseline_ready
                and class_id ~= constants.PLAYER_CLASS_ID
                and (previous_type ~= type or previous_class ~= class_id) then
                capture_ground_pound_tile(tile_x, tile_y)
            end
        end

        if object_baseline_ready
            and (type == constants.BUMPED_BLOCK_TYPE or type == constants.BROKEN_BRICK_TYPE)
            and previous_type ~= type then
            if tile_x == nil then
                tile_x, tile_y = actors.object_tile(object)
            end
            local player = state.input_trap_state.active_player
            local is_ground_pound_block = false
            if player ~= nil then
                local ground_pound_state = _G.memory.readbyte(memory.to_domain_addr(
                    player + constants.PLAYER_GROUND_POUND_STATE_OFFSET
                ))
                is_ground_pound_block = ground_pound_state
                    == constants.PLAYER_GROUND_POUND_ACTIVE_STATE
            end
            if is_ground_pound_block then
                -- These actors transition one frame before the impact animation
                M.queue_block_event(
                    constants.AP_EVENT_TYPE_BLOCK_GROUND_POUND, world, level, area, tile_x, tile_y + 1)
            else
                M.queue_block_object(object, tile_x, tile_y)
            end
        end

        -- Verify both fields when a Sprite 290 pointer first appears, then
        -- retain that classification until the pointer leaves the active
        -- list.  W6-2 Bonus alone contains 128 of these actors, so repeating
        -- the same class read every frame was significant overhead.
        if type == MOVING_BLOCK_ACTOR_TYPE then
            local moving_state = known_moving_blocks[object]
            local is_verified_moving_block = moving_state ~= nil
            if not is_verified_moving_block then
                if class_id == nil then
                    class_id = _G.memory.read_u16_le(
                        memory.to_domain_addr(object + constants.OBJECT_CLASS_ID_OFFSET)
                    )
                end
                is_verified_moving_block = class_id == MOVING_BLOCK_ACTOR_TYPE
            end

            if is_verified_moving_block then
                local open_state = _G.memory.read_u32_le(
                    memory.to_domain_addr(object + MOVING_BLOCK_OPEN_STATE_OFFSET)
                ) % 2
                if moving_state == nil then
                    if tile_x == nil then
                        tile_x, tile_y = actors.object_tile(object)
                    end
                    -- Bind the moving actor to its immutable ROM spawn position.
                    known_moving_blocks[object] = {
                        spawn_x = tile_x,
                        spawn_y = tile_y,
                        current_x = tile_x,
                        current_y = tile_y,
                        open_state = open_state,
                        seen_generation = scan_generation,
                    }
                    -- Blocks opened immediately after entering a course can reach
                    -- state 1 before the first stable observer baseline exists.
                    -- Publish their current tile; the client resolves the unique
                    -- nearby immutable spawn.
                    if open_state == 1 then
                        M.queue_block_event(
                            constants.AP_EVENT_TYPE_MOVING_BLOCK_OPEN,
                            world,
                            level,
                            area,
                            tile_x,
                            tile_y
                        )
                    end
                else
                    moving_state.seen_generation = scan_generation
                    if moving_state.open_state == 0 and open_state == 1 then
                        M.queue_block_event(
                            constants.AP_EVENT_TYPE_MOVING_BLOCK_OPEN,
                            world,
                            level,
                            area,
                            moving_state.spawn_x,
                            moving_state.spawn_y
                        )
                    end
                    -- Current coordinates are only consumed by the short
                    -- Ground-Pound correlation window.  Outside it, the immutable
                    -- spawn coordinate is sufficient for open-state events.
                    if capture_actors then
                        moving_state.current_x = tile_x
                        moving_state.current_y = tile_y
                    end
                    moving_state.open_state = open_state
                end
            end
        end
    end

    for object, moving_state in pairs(known_moving_blocks) do
        if moving_state.seen_generation ~= scan_generation then
            known_moving_blocks[object] = nil
        end
    end

    for object, _previous_type in pairs(known_actors.object_types) do
        if known_actor_seen_generation[object] ~= scan_generation then
            if object_baseline_ready
                and capture_actors
                and capture_actor_baseline_ready
                and known_object_classes[object] ~= constants.PLAYER_CLASS_ID then
                local previous_tile = known_actors.object_tiles[object]
                if previous_tile ~= nil then
                    capture_ground_pound_tile(previous_tile[1], previous_tile[2])
                end
            end
            known_actors.object_types[object] = nil
            known_actors.object_tiles[object] = nil
            known_object_classes[object] = nil
            known_actor_seen_generation[object] = nil
        end
    end

    capture_actor_baseline_ready = capture_actors
    object_baseline_ready = true
end

-- Start a short capture window when Mario enters the impact animation.
function M.observe_ground_pound_blocks(player)
    local animation = _G.memory.readbyte(memory.to_domain_addr(player + constants.PLAYER_ANIMATION_OFFSET))
    local is_new_impact = animation == constants.PLAYER_ANIMATION_GROUND_POUND_IMPACT
        and previous_player_animation ~= constants.PLAYER_ANIMATION_GROUND_POUND_IMPACT
    previous_player_animation = animation
    if not is_new_impact then
        return
    end

    if context.active_mode == "ground_clap" then
        state.input_trap_state.apply_action_damage(player)
    end

    local raw_x = _G.memory.read_s32_le(memory.to_domain_addr(player + constants.OBJECT_X_OFFSET))
    local tile_x = math.floor(raw_x / 0x10000)
    local tile_y = math.floor(_G.memory.read_s32_le(memory.to_domain_addr(player + constants.OBJECT_Y_OFFSET)) / 0x10000)
    local world, level, area = actors.current_course_identity()
    if world > 7 or level > constants.MAX_RUNTIME_COURSE_LEVEL or area == 0xFF then
        return
    end

    ground_pound_capture = {
        frames = constants.GROUND_POUND_CAPTURE_FRAME_COUNT,
        world = world,
        level = level,
        area = area,
        tile_x = tile_x,
        tile_y = tile_y,
        raw_x = raw_x,
        captured_tiles = {},
    }
    -- The orchestrator runs the actor observer immediately after this call.
    -- It supplies exact fallback tiles only while the native callback has not
    -- demonstrated usable register access.
    capture_actor_baseline_ready = false
end

-- Publish a legacy position fallback only if native hooks are unavailable.
function M.finalize_ground_pound_capture()
    if ground_pound_capture == nil then
        return
    end
    ground_pound_capture.frames = ground_pound_capture.frames - 1
    if ground_pound_capture.frames > 0 then
        return
    end

    if next(ground_pound_capture.captured_tiles) == nil
        and not context.hit_block_execute_hook_initialized then
        M.queue_block_event(
            constants.AP_EVENT_TYPE_BLOCK_GROUND_POUND,
            ground_pound_capture.world,
            ground_pound_capture.level,
            ground_pound_capture.area,
            ground_pound_capture.tile_x,
            ground_pound_capture.tile_y
        )
    end
    ground_pound_capture = nil
end


return M
