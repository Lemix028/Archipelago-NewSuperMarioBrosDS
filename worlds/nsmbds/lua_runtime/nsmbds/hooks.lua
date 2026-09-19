-- Head Bonk events are produced by the ROM-native hitBlock entry hook.
local M = {}
local state = require("nsmbds.state")
local native_input = require("nsmbds.native_input")
local context = state.context

function M.poll_native_head_bonk()
    local sequence = native_input.head_bonk_sequence()
    if sequence == nil then
        context.native_head_bonk_last_sequence = nil
        return
    end
    local previous = context.native_head_bonk_last_sequence
    context.native_head_bonk_last_sequence = sequence
    if previous == nil or previous == sequence
        or context.active_mode ~= "head_bonk" then return end

    local player = state.input_trap_state.active_player
    if player ~= nil then
        -- The native producer already checked upward motion, ground-pound
        -- animation, and the live pause flags at the exact block-hit time.
        state.input_trap_state.apply_action_damage(player)
    end
end

return M
