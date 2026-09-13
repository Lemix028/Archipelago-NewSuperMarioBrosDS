-- =============================================================================
-- lua/nsmbds/star_coins.lua
-- Commit Star-Coin pickups to the vanilla per-level save byte immediately.
-- =============================================================================

local M = {}
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")

local STAR_COIN_BITS = { 0x01, 0x02, 0x04 }

local function has_flag(value, flag)
    return math.floor(value / flag) % 2 >= 1
end

local function merge_star_coin_flags(saved, active)
    local merged = saved
    for _, flag in ipairs(STAR_COIN_BITS) do
        if has_flag(active, flag) and not has_flag(saved, flag) then
            merged = merged + flag
        end
    end
    return merged
end

function M.commit_active_pickups()
    local ok_active, active = pcall(
        _G.memory.readbyte,
        addresses.ADDR_ACTIVE_STAR_COIN_FLAGS
    )
    if not ok_active or active == nil then return false end
    active = active % (constants.STAR_COIN_FLAGS_MASK + 1)
    if active == 0 then return false end

    -- Use the identity selected by Vanilla's own goal-time commit routine,
    -- rather than the content-course byte. This writes into the destination
    -- slot and therefore remains correct when levels are randomized.
    local ok_world, world = pcall(
        _G.memory.read_u32_le,
        addresses.ADDR_STAR_COIN_STATE + constants.STAR_COIN_STATE_WORLD_OFFSET
    )
    local ok_level, level = pcall(
        _G.memory.read_u32_le,
        addresses.ADDR_STAR_COIN_STATE + constants.STAR_COIN_STATE_LEVEL_OFFSET
    )
    if not ok_world or not ok_level or world == nil or level == nil then
        return false
    end
    level = level % 0x100
    if world < 0 or world > 7 or level < 1 or level >= constants.LEVEL_DATA_WORLD_STRIDE then
        return false
    end

    local target = addresses.ADDR_LEVEL_DATA_BASE
        + world * constants.LEVEL_DATA_WORLD_STRIDE
        + level
    local ok_saved, saved = pcall(_G.memory.readbyte, target)
    if not ok_saved or saved == nil then return false end

    local merged = merge_star_coin_flags(saved, active)
    if merged == saved then return false end
    local ok_write = pcall(_G.memory.writebyte, target, merged)
    return ok_write
end

M.merge_star_coin_flags = merge_star_coin_flags

return M
