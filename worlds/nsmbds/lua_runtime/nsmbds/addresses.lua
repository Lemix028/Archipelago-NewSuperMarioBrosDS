-- =============================================================================
-- lua/nsmbds/addresses.lua
-- Dynamic address resolution based on memory domain
-- =============================================================================

local M = {}
local constants = require("nsmbds.constants")
local memory = require("nsmbds.memory")
local state = require("nsmbds.state")

function M.resolve()
    M.ADDR_POWERUP_MAP = memory.to_domain_addr(constants.SYS_POWERUP_MAP)
    M.ADDR_POWERUP_LEVEL = memory.to_domain_addr(constants.SYS_POWERUP_LEVEL)
    M.ADDR_CONTROL_OPTIONS = memory.to_domain_addr(constants.SYS_CONTROL_OPTIONS)
    M.ADDR_BUTTONS_HELD = memory.to_domain_addr(constants.SYS_BUTTONS_HELD)
    M.ADDR_BUTTONS_PRESSED = memory.to_domain_addr(constants.SYS_BUTTONS_PRESSED)
    M.ADDR_PRESSED_KEYS = memory.to_domain_addr(constants.SYS_PRESSED_KEYS)
    M.ADDR_TIMER = memory.to_domain_addr(constants.SYS_TIMER)
    M.ADDR_LIVES = memory.to_domain_addr(constants.SYS_LIVES)
    M.ADDR_AP_TRAP_TRIGGER = memory.to_domain_addr(constants.SYS_AP_TRAP_TRIGGER)
    M.ADDR_AP_TRAP_SHIELD_COUNT = memory.to_domain_addr(constants.SYS_AP_TRAP_SHIELD_COUNT)
    M.ADDR_AP_LIFE_INSURANCE_COUNT = memory.to_domain_addr(constants.SYS_AP_LIFE_INSURANCE_COUNT)
    M.ADDR_AP_INSURED_DEATH_SEQUENCE = memory.to_domain_addr(constants.SYS_AP_INSURED_DEATH_SEQUENCE)

    state.notification_state.addr.magic_1 = memory.to_domain_addr(state.notification_state.sys.magic_1)
    state.notification_state.addr.magic_2 = memory.to_domain_addr(state.notification_state.sys.magic_2)
    state.notification_state.addr.sequence = memory.to_domain_addr(state.notification_state.sys.sequence)
    state.notification_state.addr.kind = memory.to_domain_addr(state.notification_state.sys.kind)
    state.notification_state.addr.detail = memory.to_domain_addr(state.notification_state.sys.detail)
    state.notification_state.addr.acknowledged = memory.to_domain_addr(state.notification_state.sys.acknowledged)

    M.ADDR_RED_COIN_COUNTERS = {
        memory.to_domain_addr(constants.SYS_RED_COIN_COUNTERS[1]),
        memory.to_domain_addr(constants.SYS_RED_COIN_COUNTERS[2]),
    }
    M.ADDR_STAGE_EXIT_FLAGS = memory.to_domain_addr(constants.SYS_STAGE_EXIT_FLAGS)
    M.ADDR_CURRENT_WORLD_MAP = memory.to_domain_addr(constants.SYS_CURRENT_WORLD_MAP)
    M.ADDR_CURRENT_COURSE_LEVEL = memory.to_domain_addr(constants.SYS_CURRENT_COURSE_LEVEL)
    M.ADDR_CURRENT_COURSE_AREA = memory.to_domain_addr(constants.SYS_CURRENT_COURSE_AREA)
    M.ADDR_OBJECT_LIST_HEAD = memory.to_domain_addr(constants.SYS_OBJECT_LIST_HEAD)
    M.ADDR_AP_RED_COIN_EVENT_SEQUENCE = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_SEQUENCE)
    M.ADDR_AP_RED_COIN_EVENT_TYPE = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_TYPE)
    M.ADDR_AP_RED_COIN_EVENT_WORLD = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_WORLD)
    M.ADDR_AP_RED_COIN_EVENT_LEVEL = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_LEVEL)
    M.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_ACK_SEQUENCE)
    M.ADDR_AP_RED_COIN_EVENT_AREA = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_AREA)
    M.ADDR_AP_RED_COIN_EVENT_PLAYER_X = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_PLAYER_X)
    M.ADDR_AP_RED_COIN_EVENT_COUNTER = memory.to_domain_addr(constants.SYS_AP_RED_COIN_EVENT_COUNTER)
    M.ADDR_AP_BLOCK_EVENT_SEQUENCE = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_SEQUENCE)
    M.ADDR_AP_BLOCK_EVENT_TYPE = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_TYPE)
    M.ADDR_AP_BLOCK_EVENT_WORLD = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_WORLD)
    M.ADDR_AP_BLOCK_EVENT_LEVEL = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_LEVEL)
    M.ADDR_AP_BLOCK_EVENT_AREA = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_AREA)
    M.ADDR_AP_BLOCK_EVENT_TILE_X = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_TILE_X)
    M.ADDR_AP_BLOCK_EVENT_TILE_Y = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_TILE_Y)
    M.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE = memory.to_domain_addr(constants.SYS_AP_BLOCK_EVENT_ACK_SEQUENCE)
end

return M
