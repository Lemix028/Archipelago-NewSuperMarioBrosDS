-- Lua-owned control line for the ARM9 input filter and Head Bonk producer.
local M = {}
local memory = require("nsmbds.memory")
local constants = require("nsmbds.constants")
local state = require("nsmbds.state")
local context = state.context

local MODES = {
    no_jump = 1,
    no_sprint = 2,
    button_roulette = 3,
    sticky_buttons = 4,
    auto_run = 5,
    camera_drift = 6,
    camera_sway = 7,
    boo_curse = 8,
    no_turnaround = 9,
    im_stuck = 10,
}

local function control_address(offset)
    return memory.to_domain_addr(constants.SYS_NATIVE_INPUT_CONTROL + offset)
end

function M.is_ready()
    local ok, ready = pcall(function()
        return _G.memory.read_u32_le(control_address(0))
            == constants.NATIVE_INPUT_MAGIC
            and _G.memory.read_u32_le(control_address(4))
            == constants.NATIVE_INPUT_VERSION
    end)
    return ok and ready
end

function M.disable()
    if not M.is_ready() then return end
    -- Mode and enable are separate bytes so a hot reload cannot leave a Trap
    -- filtering input while the new Lua runtime is still initializing.
    _G.memory.writebyte(control_address(9), 0)
    _G.memory.writebyte(control_address(8), 0)
    _G.memory.writebyte(control_address(25), 0)
    _G.memory.write_u32_le(control_address(28), 0)
end

function M.head_bonk_sequence()
    if not M.is_ready() then return nil end
    local ok, sequence = pcall(
        _G.memory.read_u32_le,
        memory.to_domain_addr(constants.SYS_NATIVE_INPUT_CONTROL + 0x30)
    )
    return ok and sequence or nil
end

function M.sync(has_active_player, camera_held_flag, camera_pressed_flag)
    if not M.is_ready() then return false end

    local mode = has_active_player and context.trap_remaining_frames > 0
        and MODES[context.active_mode] or 0
    local elapsed = math.max(0, context.trap_total_frames - context.trap_remaining_frames)
    local boo_reverse = context.active_mode == "boo_curse"
        and elapsed % state.input_trap_state.boo_cycle_frames
            < state.input_trap_state.boo_reverse_frames
    local frame = emu and emu.framecount and emu.framecount() or 0

    -- The native routine checks the current freeze/menu flags itself. Leaving
    -- enable set through a pause lets the first resumed input write be filtered
    -- without waiting for another Lua frame-end tick.
    _G.memory.writebyte(control_address(8), mode)
    _G.memory.writebyte(control_address(10), camera_held_flag or 0)
    _G.memory.writebyte(control_address(11), camera_pressed_flag or 0)
    _G.memory.writebyte(control_address(12), boo_reverse and 1 or 0)
    _G.memory.write_u32_le(control_address(16), frame % 0x100000000)
    _G.memory.write_u32_le(control_address(20), context.native_trap_generation or 0)
    _G.memory.writebyte(control_address(24), state.input_trap_state.sticky_duration)
    _G.memory.writebyte(control_address(26),
        state.input_trap_state.player_was_moving_up and 1 or 0)
    _G.memory.write_u32_le(control_address(28),
        state.input_trap_state.active_player or 0)
    _G.memory.writebyte(control_address(25),
        has_active_player and context.trap_remaining_frames > 0
            and context.active_mode == "head_bonk" and 1 or 0)
    _G.memory.writebyte(control_address(9), mode ~= 0 and 1 or 0)
    return true
end

return M
