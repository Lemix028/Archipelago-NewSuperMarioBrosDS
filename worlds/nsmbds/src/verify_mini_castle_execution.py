"""Execute the ROM's world-selection function with Unicorn (optional dev tool).

Requires ndspy and unicorn. Tests the shipped ARM bytes against the same
function with its hook removed. Cache maintenance is skipped: Unicorn has
coherent memory, so this does not validate the DS cache or live event timing.
"""
import argparse
import runpy
import struct
from pathlib import Path

import ndspy.rom
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_ARM_REG_CPSR,
)

REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
        UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
        UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
        UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_CPSR)


def verify(rom_path: Path) -> None:
    metadata = runpy.run_path(Path(__file__).parent / "native_hooks/mini_castle_hook.py")
    overlay = ndspy.rom.NintendoDSRom.fromFile(rom_path).loadArm9Overlays()[8]
    cave = metadata["HOOK_CAVE"] - overlay.ramAddress
    assert overlay.data[cave:cave + len(metadata["MINI_CASTLE_HOOK_BYTES"])] == metadata["MINI_CASTLE_HOOK_BYTES"]
    site = metadata["HOOK_SITE"] - overlay.ramAddress
    expected_branch = 0xEA000000 | (((metadata["HOOK_CAVE"] - metadata["HOOK_SITE"] - 8) // 4) & 0xFFFFFF)
    assert struct.unpack_from("<I", overlay.data, site)[0] == expected_branch
    original = bytearray(overlay.data)
    struct.pack_into("<I", original, site, metadata["ORIGINAL_HOOK_WORD"])
    mailbox = metadata["MINI_CASTLE_FLAGS"]

    def execute(data, world, powerup, flags, sequence):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.mem_map(0x02000000, 0x400000)
        cpu.mem_write(overlay.ramAddress, bytes(data))
        # Stub only the external power-up getter; execute the retail selector.
        cpu.mem_write(0x020201B8, struct.pack("<II", 0xE3A00000 | powerup, 0xE12FFF1E))
        cpu.mem_write(mailbox, bytes((flags, sequence, 0, 0)))
        for index, reg in enumerate(REGS[:-3]):
            cpu.reg_write(reg, 0x1000 + index)
        cpu.reg_write(UC_ARM_REG_CPSR, 0xA0000013)
        cpu.reg_write(UC_ARM_REG_SP, 0x023F0000)
        cpu.reg_write(UC_ARM_REG_LR, 0x02001000)
        cpu.reg_write(UC_ARM_REG_R0, world)

        def skip_cache(cpu, address, size, _):
            word = int.from_bytes(cpu.mem_read(address, 4), "little")
            if word in (0xEE073F3A, 0xEE073F9A):
                cpu.reg_write(UC_ARM_REG_PC, address + 4)

        cpu.hook_add(UC_HOOK_CODE, skip_cache)
        cpu.emu_start(0x020CE298, 0x02001000, count=250)
        assert cpu.reg_read(UC_ARM_REG_PC) == 0x02001000
        return tuple(cpu.reg_read(r) for r in REGS), bytes(cpu.mem_read(mailbox, 4))

    count = 0
    for world in range(8):
        for powerup in range(6):
            destination = (1, 3 if powerup == 4 else 2, 4, 4,
                           6 if powerup == 4 else 5, 7, 7, 7)[world]
            bit = 1 if (world, destination) == (1, 3) else 2 if (world, destination) == (4, 6) else 0
            for flags in range(4):
                for sequence in (0, 255):
                    baseline, _ = execute(original, world, powerup, flags, sequence)
                    actual, trace = execute(overlay.data, world, powerup, flags, sequence)
                    assert actual == baseline, (world, powerup, "register/flags mismatch")
                    assert actual[0] == destination
                    assert trace == bytes((flags | bit, (sequence + 1) & 255, world, destination))
                    count += 1
    print(f"Passed {count} ARM executions: routes, sticky flags, trace wrap, registers and CPSR.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    verify(parser.parse_args().rom)
