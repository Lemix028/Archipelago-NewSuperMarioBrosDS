"""Check Lua native Trap control and Head Bonk event consumption.

Maintainer check using the local Lupa package; no emulator or ROM is needed.
"""

from __future__ import annotations

from pathlib import Path

from lupa import LuaRuntime


def verify() -> None:
    lua = LuaRuntime()
    lua.execute("""
        ram = {}
        calls = {damage = 0}
        memory = {
            read_u32_le = function(addr) return ram[addr] or 0 end,
            read_u16_le = function(addr) return ram[addr] or 0 end,
            write_u32_le = function(addr, value) ram[addr] = value end,
            writebyte = function(addr, value) ram[addr] = value end,
        }
        emu = {framecount = function() return 77 end}
        package.preload["nsmbds.memory"] = function()
            return {domain = "Main RAM", sys_bus_domain = nil,
                to_domain_addr = function(addr) return addr - 0x02000000 end}
        end
        package.preload["nsmbds.constants"] = function()
            return {SYS_NATIVE_INPUT_CONTROL = 0x02002C40,
                NATIVE_INPUT_MAGIC = 0x54495041, NATIVE_INPUT_VERSION = 1}
        end
        package.preload["nsmbds.addresses"] = function()
            return {ADDR_PRESSED_KEYS = 0x888E2}
        end
        package.preload["nsmbds.screen_geometry"] = function() return {} end
        package.preload["nsmbds.state"] = function()
            return {context = {active_mode = "no_jump", trap_remaining_frames = 90,
                trap_total_frames = 100, native_trap_generation = 4},
                input_trap_state = {boo_cycle_frames = 180, boo_reverse_frames = 54,
                    sticky_duration = 36, auto_direction = 1,
                    player_was_moving_up = true,
                    active_player = 0x02050000,
                    apply_action_damage = function(player)
                        calls.damage = calls.damage + 1
                    end}}
        end
    """)
    root = Path(__file__).resolve().parents[1] / "lua_runtime" / "nsmbds"
    native = lua.execute(f"return assert(loadfile([[{(root / 'native_input.lua').as_posix()}]]))()")
    lua.globals().package.loaded["nsmbds.native_input"] = native
    hooks = lua.execute(f"return assert(loadfile([[{(root / 'hooks.lua').as_posix()}]]))()")
    traps = lua.execute(f"return assert(loadfile([[{(root / 'traps.lua').as_posix()}]]))()")
    lua.execute('require("nsmbds.state").input_trap_state.apply_action_damage = '
                'function(player) calls.damage = calls.damage + 1 end')
    ram = lua.globals().ram
    calls = lua.globals().calls
    context = lua.eval('require("nsmbds.state").context')

    assert native.sync(True, 0, 0) is False
    ram[0x2C40], ram[0x2C44] = 0x54495041, 1
    assert native.sync(True, 0, 0) is True
    assert (ram[0x2C48], ram[0x2C49], ram[0x2C50], ram[0x2C54]) == (1, 1, 77, 4)
    traps.update_native_input(True)
    ram[0x888E2] = 0x20
    assert traps.update_auto_run_direction_from_input() is True
    assert lua.eval('require("nsmbds.state").input_trap_state.auto_direction') == -1
    ram[0x888E2] = 0x10
    assert traps.update_auto_run_direction_from_input() is True
    assert lua.eval('require("nsmbds.state").input_trap_state.auto_direction') == 1
    ram[0x888E2] = 0x30
    assert traps.update_auto_run_direction_from_input() is False

    context.active_mode = "head_bonk"
    native.sync(True, 0, 0)
    assert (ram[0x2C48], ram[0x2C59], ram[0x2C5A], ram[0x2C5C]) == (
        0, 1, 1, 0x02050000,
    )
    ram[0x2C70] = 0
    hooks.poll_native_head_bonk()
    ram[0x2C70] = 1
    hooks.poll_native_head_bonk()
    assert calls.damage == 1

    native.disable()
    assert (ram[0x2C48], ram[0x2C49], ram[0x2C59], ram[0x2C5C]) == (0, 0, 0, 0)
    print("Lua native protocol and Head Bonk event OK")


if __name__ == "__main__":
    verify()
