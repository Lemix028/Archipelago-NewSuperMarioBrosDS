-- =============================================================================
-- lua/nsmbds/mini_castles.lua
-- Mini-Castle completion detection
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")
local state = require("nsmbds.state")

function M.observe_mini_castle_completion(trap_player)
    local perm_addr = memory.to_domain_addr(0x02002FF3)
    local flags_addr = memory.to_domain_addr(0x02088F40)
    local w2_clear_addr = memory.to_domain_addr(0x02088C6F)
    local w5_clear_addr = memory.to_domain_addr(0x02088CBB)

    local perm_flags = _G.memory.readbyte(perm_addr) or 0

    -- Permanente Flags immer in die Client-Mailbox spiegeln
    local volatile_flags = _G.memory.readbyte(flags_addr) or 0

    if perm_flags % 2 >= 1 and volatile_flags % 2 < 1 then
        volatile_flags = volatile_flags + 1
    end

    if math.floor(perm_flags / 2) % 2 >= 1
        and math.floor(volatile_flags / 2) % 2 < 1 then
        volatile_flags = volatile_flags + 2
    end

    _G.memory.writebyte(flags_addr, volatile_flags)

    local world = _G.memory.readbyte(addresses.ADDR_CURRENT_WORLD_MAP)
    local level = _G.memory.readbyte(addresses.ADDR_CURRENT_COURSE_LEVEL)

    local actor_powerup = nil
    if trap_player then
        actor_powerup = _G.memory.readbyte(
            memory.to_domain_addr(trap_player + constants.PLAYER_POWERUP_OFFSET)
        )
    end

    -- Letzten gültigen Actor-Power-up-Wert im jeweiligen Castle speichern
    if world == 1 and level == 14 then
        if actor_powerup ~= nil then
            state.input_trap_state.last_w2_castle_powerup = actor_powerup
        end
    elseif world == 4 and level == 14 then
        if actor_powerup ~= nil then
            state.input_trap_state.last_w5_castle_powerup = actor_powerup
        end
    end

    local w2_clear_byte = _G.memory.readbyte(w2_clear_addr) or 0
    local w5_clear_byte = _G.memory.readbyte(w5_clear_addr) or 0

    local w2_clear = math.floor(w2_clear_byte / 16) % 2 >= 1
    local w5_clear = math.floor(w5_clear_byte / 16) % 2 >= 1

    -- Beim ersten Aufruf nur den aktuellen Ausgangszustand übernehmen
    if state.input_trap_state.prev_w2_castle_clear == nil then
        state.input_trap_state.prev_w2_castle_clear = w2_clear
    end

    if state.input_trap_state.prev_w5_castle_clear == nil then
        state.input_trap_state.prev_w5_castle_clear = w5_clear
    end

    -- ========================================================
    -- World 2 Castle
    -- ========================================================

    local in_w2_castle = world == 1 and level == 14

    if in_w2_castle and not w2_clear then
        state.input_trap_state.prev_w2_castle_clear = false
    end

    if w2_clear and state.input_trap_state.prev_w2_castle_clear == false then
        local final_powerup = actor_powerup or state.input_trap_state.last_w2_castle_powerup

        if final_powerup == 4 then
            local current_perm = _G.memory.readbyte(perm_addr) or 0
            local new_flags = current_perm % 2 < 1 and current_perm + 1 or current_perm

            _G.memory.writebyte(perm_addr, new_flags)

            local current_volatile = _G.memory.readbyte(flags_addr) or 0
            if current_volatile % 2 < 1 then
                current_volatile = current_volatile + 1
            end

            _G.memory.writebyte(flags_addr, current_volatile)
        end
    end

    -- ========================================================
    -- World 5 Castle
    -- ========================================================

    local in_w5_castle = world == 4 and level == 14

    if in_w5_castle and not w5_clear then
        state.input_trap_state.prev_w5_castle_clear = false
    end

    if w5_clear and state.input_trap_state.prev_w5_castle_clear == false then
        local final_powerup = actor_powerup or state.input_trap_state.last_w5_castle_powerup

        if final_powerup == 4 then
            local current_perm = _G.memory.readbyte(perm_addr) or 0
            local new_flags = math.floor(current_perm / 2) % 2 < 1 and current_perm + 2 or current_perm

            _G.memory.writebyte(perm_addr, new_flags)

            local current_volatile = _G.memory.readbyte(flags_addr) or 0
            if math.floor(current_volatile / 2) % 2 < 1 then
                current_volatile = current_volatile + 2
            end

            _G.memory.writebyte(flags_addr, current_volatile)
        end
    end

    state.input_trap_state.prev_w2_castle_clear = w2_clear
    state.input_trap_state.prev_w5_castle_clear = w5_clear
end

return M
