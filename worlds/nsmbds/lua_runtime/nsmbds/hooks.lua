-- Head Bonk is independent of the ROM-native Blocksanity producer.
local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local state = require("nsmbds.state")
local context = state.context
local HEAD_BONK_HOOK_NAME = "nsmbds_head_bonk_hit_block"

-- One-time migration cleanup on script reload. No block Execute hook is
-- registered by this runtime; old callbacks must not survive a hot reload.
function M.cleanup_previous_block_hooks()
    if not event or not event.unregisterbyname then return end
    pcall(event.unregisterbyname, "nsmbds_hit_block_change_tile")
    pcall(event.unregisterbyname, "nsmbds_hit_block_execute")
    for index = 1, 4 do
        pcall(event.unregisterbyname, "nsmbds_hit_block_tile_" .. index)
    end
    pcall(event.unregisterbyname, HEAD_BONK_HOOK_NAME)
end

function M.disable_head_bonk_execute_hook()
    if context.head_bonk_execute_hook_initialized or context.head_bonk_execute_hook_attempted then
        if event and event.unregisterbyname then
            pcall(event.unregisterbyname, HEAD_BONK_HOOK_NAME)
        end
    end
    context.head_bonk_execute_hook_initialized = false
    context.head_bonk_execute_hook_attempted = false
end

function M.record_head_bonk()
    local player = state.input_trap_state.active_player
    if context.active_mode == "head_bonk" and player ~= nil then
        local velocity = _G.memory.read_s32_le(memory.to_domain_addr(player + constants.PLAYER_Y_VELOCITY_OFFSET))
        local animation = _G.memory.readbyte(memory.to_domain_addr(player + constants.PLAYER_ANIMATION_OFFSET))
        if (velocity > 0 or state.input_trap_state.player_was_moving_up)
            and animation ~= constants.PLAYER_ANIMATION_GROUND_POUND_IMPACT then
            state.input_trap_state.player_was_moving_up = false
            state.input_trap_state.apply_action_damage(player)
        end
    end
end

function M.sync_head_bonk_execute_hook()
    local should_enable = context.active_mode == "head_bonk"
    if not should_enable then
        if context.head_bonk_execute_hook_initialized
            or context.head_bonk_execute_hook_attempted then
            if event and event.unregisterbyname then
                pcall(event.unregisterbyname, HEAD_BONK_HOOK_NAME)
            end
            context.head_bonk_execute_hook_initialized = false
            context.head_bonk_execute_hook_attempted = false
        end
        return
    end
    if context.head_bonk_execute_hook_initialized
        or context.head_bonk_execute_hook_attempted then
        return
    end
    context.head_bonk_execute_hook_attempted = true
    local on_execute = event and (event.on_bus_exec or event.onmemoryexecute)
    if not on_execute then
        return
    end
    local scope = memory.sys_bus_domain or memory.domain
    local hook_address = memory.sys_bus_domain and constants.SYS_HIT_BLOCK_FUNCTION
        or memory.to_domain_addr(constants.SYS_HIT_BLOCK_FUNCTION)
    local ok, hook_id = pcall(
        on_execute,
        M.record_head_bonk,
        hook_address,
        HEAD_BONK_HOOK_NAME,
        scope
    )
    context.head_bonk_execute_hook_initialized = ok and hook_id ~= nil
end

return M
