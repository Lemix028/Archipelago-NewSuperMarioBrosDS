"""Exercise the exact hitBlock-entry Head Bonk replacement in Unicorn."""

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

from assemble_head_bonk_hook import assemble
from native_hooks.head_bonk_hook import CONTINUE, HOOK_BYTES, HOOK_CAVE


CONTROL = 0x02002C40
HEAD_SEQUENCE = 0x02002C70
PRODUCER = 0x02001C00
PLAYER = 0x02050000
STACK = 0x023FF000
REGISTERS = (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7,
    UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11,
    UC_ARM_REG_R12, UC_ARM_REG_LR,
)


class Machine:
    def __init__(self) -> None:
        assert assemble() == HOOK_BYTES, "Checked-in Head Bonk bytes differ from assembly"
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0x02000000, 0x00400000)
        self.uc.mem_write(HOOK_CAVE, HOOK_BYTES)
        self.uc.reg_write(UC_ARM_REG_CPSR, 0xA0000013)
        mcr_sites = {
            instruction.address
            for instruction in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(HOOK_BYTES, HOOK_CAVE)
            if instruction.mnemonic == "mcr"
        }

        def skip_cache_opcode(uc: Uc, address: int, _size: int, _data: object) -> None:
            # Unicorn's flat memory is coherent without ARM946 cache opcodes.
            if address in mcr_sites:
                uc.reg_write(UC_ARM_REG_PC, address + 4)

        self.uc.hook_add(UC_HOOK_CODE, skip_cache_opcode)
        self.byte(CONTROL + 25, 1)
        self.u32(CONTROL + 28, PLAYER)
        self.u32(PLAYER + 0xD4, 1)

    def byte(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, bytes((value & 0xFF,)))
        return self.uc.mem_read(address, 1)[0]

    def u32(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, struct.pack("<I", value))
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def call(self) -> None:
        values = [0x11110000 + i for i in range(len(REGISTERS))]
        for register, value in zip(REGISTERS, values):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_ARM_REG_SP, STACK)
        self.uc.emu_start(HOOK_CAVE, CONTINUE, count=1000)
        assert self.uc.reg_read(UC_ARM_REG_PC) == CONTINUE
        assert self.uc.reg_read(UC_ARM_REG_SP) == STACK - 36  # displaced push
        assert self.uc.reg_read(UC_ARM_REG_CPSR) & 0xF0000000 == 0xA0000000
        for register, expected in zip(REGISTERS, values):
            assert self.uc.reg_read(register) == expected, register
        assert self.u32(STACK - 36) == values[4]  # original r4 saved
        assert self.u32(STACK - 4) == values[-1]  # original lr saved


def verify() -> None:
    machine = Machine()
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 1
    assert machine.u32(PRODUCER + 8) == 0  # no Blocksanity dependency

    machine.u32(PLAYER + 0xD4, 0xFFFFFFFF)
    machine.byte(CONTROL + 26, 0)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 1
    machine.byte(CONTROL + 26, 1)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 2

    machine.byte(PLAYER + 0x76C, 0x10)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 2
    machine.byte(PLAYER + 0x76C, 0)
    machine.byte(0x020CA870, 1)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 2
    machine.byte(0x020CA870, 0)
    machine.byte(CONTROL + 25, 0)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 2
    machine.byte(CONTROL + 25, 1)
    machine.u32(CONTROL + 28, 0)
    machine.call()
    assert machine.u32(HEAD_SEQUENCE) == 2
    print("Native Head Bonk: exact function entry, motion, impact, pause, and prologue restore OK")


if __name__ == "__main__":
    verify()
