-- =============================================================================
-- lua/nsmbds/actors.lua
-- Actor and course helpers
-- =============================================================================

local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local addresses = require("nsmbds.addresses")

function M.is_valid_object_pointer(pointer)
    return pointer >= 0x02000000 and pointer < 0x02400000
end

function M.get_active_objects()
    local objects = {}
    local node = _G.memory.read_u32_le(addresses.ADDR_OBJECT_LIST_HEAD)
    local visited = {}
    local count = 0

    while node ~= 0 and count < 512 do
        local object = node - constants.OBJECT_NODE_OFFSET
        if not M.is_valid_object_pointer(object) or visited[object] then
            break
        end
        visited[object] = true
        objects[#objects + 1] = object
        count = count + 1
        node = _G.memory.read_u32_le(memory.to_domain_addr(object + constants.OBJECT_NODE_OFFSET + 4))
    end
    return objects
end

function M.object_type(object)
    return _G.memory.read_u16_le(memory.to_domain_addr(object + constants.OBJECT_TYPE_OFFSET))
end

function M.find_player_object(objects, cached_player)
    -- Reuse Mario's pointer while it is still part of the active list.  Merely
    -- checking the class at a stale address is not sufficient because actor
    -- storage can survive briefly across course transitions.
    if cached_player ~= nil and M.is_valid_object_pointer(cached_player) then
        for _, object in ipairs(objects) do
            if object == cached_player then
                local class_id = _G.memory.read_u16_le(
                    memory.to_domain_addr(object + constants.OBJECT_CLASS_ID_OFFSET)
                )
                if class_id == constants.PLAYER_CLASS_ID then
                    return object
                end
                break
            end
        end
    end

    for _, object in ipairs(objects) do
        if object ~= cached_player then
            local class_id = _G.memory.read_u16_le(
                memory.to_domain_addr(object + constants.OBJECT_CLASS_ID_OFFSET)
            )
            if class_id == constants.PLAYER_CLASS_ID then
                return object
            end
        end
    end
    return nil
end

function M.object_tile(object)
    local x = _G.memory.read_s32_le(memory.to_domain_addr(object + constants.OBJECT_X_OFFSET))
    local y = _G.memory.read_s32_le(memory.to_domain_addr(object + constants.OBJECT_Y_OFFSET))
    return math.floor(x / 0x10000), math.floor(y / 0x10000)
end

function M.current_course_identity()
    return _G.memory.readbyte(addresses.ADDR_CURRENT_WORLD_MAP),
        _G.memory.readbyte(addresses.ADDR_CURRENT_COURSE_LEVEL),
        _G.memory.readbyte(addresses.ADDR_CURRENT_COURSE_AREA)
end

return M
