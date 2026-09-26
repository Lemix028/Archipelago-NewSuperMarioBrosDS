"""Exercise Lua's native Red Coin queue and AP mailbox ownership with Lupa."""

from __future__ import annotations

from pathlib import Path

from lupa import LuaRuntime


ROOT = Path(__file__).resolve().parents[1] / "lua_runtime" / "nsmbds"


def verify() -> None:
    lua = LuaRuntime()
    lua.execute("""
        ram = {}
        memory = {}
        function memory.readbyte(a) return ram[a] or 0 end
        function memory.writebyte(a, v) ram[a] = v % 256 end
        function memory.read_u32_le(a)
            return memory.readbyte(a) + 256 * memory.readbyte(a + 1)
                + 65536 * memory.readbyte(a + 2) + 16777216 * memory.readbyte(a + 3)
        end
        function memory.read_s32_le(a)
            local v = memory.read_u32_le(a)
            return v >= 0x80000000 and v - 0x100000000 or v
        end
        function memory.write_u32_le(a, v)
            for i = 0, 3 do
                memory.writebyte(a + i, math.floor(v / (256 ^ i)))
            end
        end
        function memory.write_s32_le(a, v)
            memory.write_u32_le(a, v % 0x100000000)
        end
        package.preload["nsmbds.memory"] = function()
            return {to_domain_addr = function(a) return a end}
        end
        package.preload["nsmbds.version"] = function()
            return {VERSION = "test", VERSION_LABEL = "test"}
        end
    """)
    lua.execute(f"""
        package.preload["nsmbds.constants"] = function()
            return assert(loadfile([[{(ROOT / 'constants.lua').as_posix()}]]))()
        end
    """)
    lua.execute("""
        package.preload["nsmbds.addresses"] = function()
            local c = require("nsmbds.constants")
            return {
                ADDR_AP_RED_COIN_EVENT_SEQUENCE = c.SYS_AP_RED_COIN_EVENT_SEQUENCE,
                ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE = c.SYS_AP_RED_COIN_EVENT_ACK_SEQUENCE,
                ADDR_AP_RED_COIN_EVENT_TYPE = c.SYS_AP_RED_COIN_EVENT_TYPE,
                ADDR_AP_RED_COIN_EVENT_WORLD = c.SYS_AP_RED_COIN_EVENT_WORLD,
                ADDR_AP_RED_COIN_EVENT_LEVEL = c.SYS_AP_RED_COIN_EVENT_LEVEL,
                ADDR_AP_RED_COIN_EVENT_AREA = c.SYS_AP_RED_COIN_EVENT_AREA,
                ADDR_AP_RED_COIN_EVENT_PLAYER_X = c.SYS_AP_RED_COIN_EVENT_PLAYER_X,
                ADDR_AP_RED_COIN_EVENT_COUNTER = c.SYS_AP_RED_COIN_EVENT_COUNTER,
            }
        end
    """)
    lua.execute(f"""
        package.preload["nsmbds.red_coins"] = function()
            return assert(loadfile([[{(ROOT / 'red_coins.lua').as_posix()}]]))()
        end
    """)
    lua.execute("""
        local c = require("nsmbds.constants")
        local red = require("nsmbds.red_coins")
        local p, r = c.SYS_NATIVE_RED_COIN_PRODUCER, c.SYS_NATIVE_RED_COIN_RECORDS
        assert(not red.is_native_ready()) -- old patched ROM fails explicitly
        memory.write_u32_le(p, c.NATIVE_RED_COIN_MAGIC)
        memory.write_u32_le(p + 4, c.NATIVE_RED_COIN_VERSION)
        assert(red.is_native_ready())
        memory.writebyte(r, 2)
        memory.writebyte(r + 1, 1)
        memory.writebyte(r + 2, 45)
        memory.writebyte(r + 3, 2)
        memory.write_s32_le(r + 4, 219)
        memory.write_u32_le(r + 8, 0)
        memory.write_u32_le(p + 8, 1)
        -- Simulate death/exit/area change before Lua sees the native event.
        memory.writebyte(c.SYS_CURRENT_WORLD_MAP, 7)
        memory.writebyte(c.SYS_CURRENT_COURSE_LEVEL, 0x16)
        memory.writebyte(c.SYS_CURRENT_COURSE_AREA, 99)
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 1)
        assert(memory.readbyte(c.SYS_AP_RED_COIN_EVENT_SEQUENCE) == 1)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_WORLD) == 2)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_LEVEL) == 1)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_AREA) == 45)
        assert(memory.read_s32_le(c.SYS_AP_RED_COIN_EVENT_PLAYER_X) == 219)
        assert(memory.readbyte(c.SYS_AP_RED_COIN_EVENT_COUNTER) == 2)
        assert(memory.readbyte(0x020CA2D5) == 0) -- no frame polling of 8

        local r2 = r + c.NATIVE_RED_COIN_RECORD_SIZE
        memory.writebyte(r2, 0)
        memory.writebyte(r2 + 1, 2)
        memory.writebyte(r2 + 2, 0)
        memory.writebyte(r2 + 3, 1)
        memory.write_s32_le(r2 + 4, 41)
        memory.write_u32_le(r2 + 8, 1)
        memory.write_u32_le(p + 8, 2)
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 1)
        memory.writebyte(c.SYS_AP_RED_COIN_EVENT_ACK_SEQUENCE, 1)
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 2)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_WORLD) == 0)
        assert(memory.readbyte(c.SYS_AP_RED_COIN_EVENT_SEQUENCE) == 2)

        local r3 = r + 2 * c.NATIVE_RED_COIN_RECORD_SIZE
        memory.writebyte(r3, 4)
        memory.writebyte(r3 + 1, 3)
        memory.writebyte(r3 + 2, 0)
        memory.writebyte(r3 + 3, 1)
        memory.write_s32_le(r3 + 4, 88)
        memory.write_u32_le(r3 + 8, 2)
        memory.write_u32_le(p + 8, 3)
        -- Reload while one native event waits behind the AP mailbox.
        package.loaded["nsmbds.red_coins"] = nil
        red = require("nsmbds.red_coins")
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 2)
        memory.writebyte(c.SYS_AP_RED_COIN_EVENT_ACK_SEQUENCE, 2)
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 3)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_WORLD) == 4)
        -- Rewinding to before first delivery makes it deliver again.
        memory.writebyte(c.SYS_AP_RED_COIN_EVENT_ACK_SEQUENCE, 3)
        memory.write_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER, 0)
        memory.write_u32_le(p + 8, 1)
        assert(red.poll_native_red_coin_completion())
        assert(memory.read_u32_le(c.SYS_NATIVE_RED_COIN_CONSUMER) == 1)
        assert(memory.read_u32_le(c.SYS_AP_RED_COIN_EVENT_WORLD) == 2)
    """)
    print("Lua Red Coin queue: compatibility, course identity, backpressure, reload and rewind OK")


if __name__ == "__main__":
    verify()
