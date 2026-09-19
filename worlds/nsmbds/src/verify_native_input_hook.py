"""Exercise the ARM9 input filter in Unicorn before building a ROM delta.

Maintainer check: requires the same local Keystone, Capstone, and Unicorn
packages used for native hook development. No ROM is needed for this check.
"""

from __future__ import annotations

import struct

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR,
    UC_ARM_REG_LR,
    UC_ARM_REG_PC,
    UC_ARM_REG_R0,
    UC_ARM_REG_R1,
    UC_ARM_REG_R2,
    UC_ARM_REG_R3,
    UC_ARM_REG_R4,
    UC_ARM_REG_R5,
    UC_ARM_REG_R6,
    UC_ARM_REG_R7,
    UC_ARM_REG_R8,
    UC_ARM_REG_R9,
    UC_ARM_REG_R10,
    UC_ARM_REG_R11,
    UC_ARM_REG_R12,
    UC_ARM_REG_SP,
)

from assemble_input_trap_hook import HOOK_CAVE, assemble
from native_hooks.input_trap_hook import HOOK_BYTES


CONTROL = 0x02002C40
STATE = 0x02002C60
GENERAL = 0x020888E2
HELD = 0x02087650
PRESSED = 0x02087652
OPTIONS = 0x02088F24
FREEZE = 0x020CA28C
MENU = 0x020CA870
STACK = 0x023FF000
BUTTONS_ENTRY = HOOK_CAVE + 0x28
REGISTERS = (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_LR,
)


class Machine:
    def __init__(self) -> None:
        self.code = assemble()
        assert self.code == HOOK_BYTES, "Checked-in input binary differs from assembly"
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0x02000000, 0x00400000)
        self.uc.mem_write(HOOK_CAVE, self.code)
        self.uc.reg_write(UC_ARM_REG_CPSR, 0xA0000013)
        mcr_sites = {
            instruction.address
            for instruction in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(self.code, HOOK_CAVE)
            if instruction.mnemonic == "mcr"
        }

        def skip_cache_opcode(uc: Uc, address: int, _size: int, _data: object) -> None:
            # BizHawk memory writes are immediately visible in this flat test
            # memory; Unicorn does not need the ARM946 cache maintenance op.
            if address in mcr_sites:
                uc.reg_write(UC_ARM_REG_PC, address + 4)

        self.uc.hook_add(UC_HOOK_CODE, skip_cache_opcode)
        self.u32(CONTROL + 20, 1)
        self.u32(CONTROL + 16, 100)
        self.byte(CONTROL + 9, 1)
        self.byte(CONTROL + 24, 36)

    def byte(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, bytes((value & 0xFF,)))
        return self.uc.mem_read(address, 1)[0]

    def u16(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, struct.pack("<H", value))
        return struct.unpack("<H", self.uc.mem_read(address, 2))[0]

    def u32(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, struct.pack("<I", value))
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def call(self, *, buttons: bool = False) -> None:
        register_values = [0x11110000 + index for index in range(len(REGISTERS))]
        for register, value in zip(REGISTERS, register_values):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_ARM_REG_SP, STACK)
        self.u16(STACK + 12, 0xBEEF)
        start = BUTTONS_ENTRY if buttons else HOOK_CAVE
        end = 0x0200A580 if buttons else 0x020100B4
        self.uc.emu_start(start, end, count=1000)
        assert self.uc.reg_read(UC_ARM_REG_PC) == end
        assert self.uc.reg_read(UC_ARM_REG_SP) == STACK + (4 if buttons else 0)
        assert self.uc.reg_read(UC_ARM_REG_CPSR) & 0xF0000000 == 0xA0000000
        for index, register in enumerate(REGISTERS):
            expected = register_values[index]
            if not buttons and register == UC_ARM_REG_R1:
                expected = 0xBEEF  # displaced general instruction
            assert self.uc.reg_read(register) == expected, register


def verify() -> None:
    machine = Machine()
    machine.byte(CONTROL + 8, 1)
    machine.byte(OPTIONS, 1)
    machine.u16(GENERAL, 0x0403)
    machine.call()
    assert machine.u16(GENERAL) == 0x0400
    machine.byte(OPTIONS, 0)
    machine.u16(GENERAL, 0x0403)
    machine.call()
    assert machine.u16(GENERAL) == 0x0002

    machine.byte(CONTROL + 8, 2)
    machine.byte(OPTIONS, 1)
    machine.u16(HELD, 0x0C02)
    machine.call(buttons=True)
    assert machine.u16(HELD) == 0x0002
    machine.byte(OPTIONS, 0)
    machine.u16(HELD, 0x0C02)
    machine.call(buttons=True)
    assert machine.u16(HELD) == 0x0400

    machine.byte(CONTROL + 8, 3)
    machine.byte(OPTIONS, 1)
    machine.u16(GENERAL, 0x0003)
    machine.call()
    assert machine.u16(GENERAL) == 0x0C00
    machine.byte(OPTIONS, 0)
    machine.u16(GENERAL, 0x0401)
    machine.call()
    assert machine.u16(GENERAL) == 0x0802

    machine.byte(CONTROL + 8, 4)
    machine.u32(CONTROL + 20, 2)
    machine.u32(CONTROL + 16, 100)
    machine.u16(GENERAL, 0x10)
    machine.call()
    assert machine.byte(STATE + 1) == 36
    machine.u32(CONTROL + 16, 101)
    machine.u16(GENERAL, 0)
    machine.call()
    assert machine.u16(GENERAL) == 0x10
    assert machine.byte(STATE + 1) == 35
    machine.u16(PRESSED, 0)
    machine.call(buttons=True)
    assert machine.u16(PRESSED) == 0
    assert machine.byte(STATE + 1) == 35

    machine.byte(CONTROL + 8, 5)
    machine.u32(CONTROL + 20, 3)
    machine.u16(GENERAL, 0x20)
    machine.call()
    assert machine.u16(GENERAL) == 0x820
    machine.u16(GENERAL, 0)
    machine.call()
    assert machine.u16(GENERAL) == 0x800
    machine.u16(HELD, 0x20)
    machine.call(buttons=True)
    assert machine.u16(HELD) == 0x820
    machine.u16(GENERAL, 0x10)
    machine.call()
    assert machine.u16(GENERAL) == 0x810

    machine.byte(CONTROL + 8, 6)
    machine.byte(CONTROL + 10, 1)
    machine.byte(CONTROL + 11, 2)
    machine.u16(GENERAL, 0)
    machine.call()
    assert machine.u16(GENERAL) == 0x100
    machine.u16(HELD, 0)
    machine.u16(PRESSED, 0)
    machine.call(buttons=True)
    assert (machine.u16(HELD), machine.u16(PRESSED)) == (0x100, 0x200)
    machine.byte(CONTROL + 8, 7)
    machine.u16(PRESSED, 0x300)
    machine.call(buttons=True)
    assert machine.u16(PRESSED) == 0x300

    machine.byte(CONTROL + 8, 8)
    machine.byte(CONTROL + 12, 1)
    machine.u16(GENERAL, 0x10)
    machine.call()
    assert machine.u16(GENERAL) == 0x20
    machine.u16(GENERAL, 0x30)
    machine.call()
    assert machine.u16(GENERAL) == 0x30

    machine.byte(CONTROL + 8, 9)
    machine.u32(CONTROL + 20, 4)
    machine.u16(GENERAL, 0x10)
    machine.call()
    assert machine.u16(GENERAL) == 0x10
    machine.u16(GENERAL, 0x20)
    machine.call()
    assert machine.u16(GENERAL) == 0

    machine.byte(CONTROL + 8, 10)
    machine.u16(GENERAL, 0xFFFF)
    machine.call()
    assert machine.u16(GENERAL) == 0x000C
    machine.byte(MENU, 1)
    machine.u16(GENERAL, 0xFFFF)
    machine.call()
    assert machine.u16(GENERAL) == 0xFFFF
    machine.byte(MENU, 0)
    machine.byte(FREEZE, 1)
    machine.call()
    assert machine.u16(GENERAL) == 0xFFFF
    machine.byte(FREEZE, 0)
    machine.byte(CONTROL + 9, 0)
    machine.call()
    assert machine.u16(GENERAL) == 0xFFFF
    print("Native input filter: all ten modes, both control schemes, pause, and register restore OK")


if __name__ == "__main__":
    verify()
