"""Exercise the A2DE Red Coin collection wrapper without BizHawk callbacks."""

from __future__ import annotations

import struct

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
    UC_ARM_REG_SP,
)

from assemble_red_coin_hook import assemble
from native_hooks.red_coin_hook import (
    CAPACITY, CONSUMER, DEFAULT_QUEUE, HOOK_BYTES, HOOK_CAVE,
    PRODUCER, RECORDS,
)


ACTOR = 0x02050000
PLAYER = 0x02060000
RETURN = 0x02001000
STACK = 0x023FF000
COUNTER = 0x020CA2D4
VANILLA = 0x02154208
GET_PLAYER = 0x02020608


class Machine:
    def __init__(self) -> None:
        assert assemble() == HOOK_BYTES, "Hook bytes differ from the source assembly"
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.mem_map(0x02000000, 0x00400000)
        self.uc.mem_write(HOOK_CAVE, HOOK_BYTES)
        self.uc.mem_write(PRODUCER, DEFAULT_QUEUE)
        self.u32(ACTOR + 0x51C, 0)
        self.u32(ACTOR + 0x60, 40 << 16)
        self.u32(PLAYER + 0x60, 41 << 16)
        self.byte(0x02088BFC, 2)
        self.byte(0x02085A9C, 1)
        self.byte(0x02085A94, 45)
        self.collects = True
        self.player_present = True
        cache_sites = {
            i.address for i in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(HOOK_BYTES, HOOK_CAVE)
            if i.mnemonic == "mcr"
        }

        def intercept(uc: Uc, address: int, _size: int, _data: object) -> None:
            if address in cache_sites:
                uc.reg_write(UC_ARM_REG_PC, address + 4)
            elif address == VANILLA:
                if self.collects:
                    index = self.u32(ACTOR + 0x51C)
                    if index <= 1:
                        count = self.byte(COUNTER + index) + 1
                        self.byte(COUNTER + index, 0 if count >= 8 else count)
                    uc.reg_write(UC_ARM_REG_R0, 1)
                else:
                    uc.reg_write(UC_ARM_REG_R0, 0)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
            elif address == GET_PLAYER:
                uc.reg_write(UC_ARM_REG_R0, PLAYER if self.player_present else 0)
                uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))

        self.uc.hook_add(UC_HOOK_CODE, intercept)

    def byte(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, bytes((value & 0xFF,)))
        return self.uc.mem_read(address, 1)[0]

    def u32(self, address: int, value: int | None = None) -> int:
        if value is not None:
            self.uc.mem_write(address, struct.pack("<I", value & 0xFFFFFFFF))
        return struct.unpack("<I", self.uc.mem_read(address, 4))[0]

    def call(self) -> int:
        saved = (0x44444444, 0x55555555, 0x66666666, 0x77777777, 0x88888888)
        for register, value in zip((UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                                    UC_ARM_REG_R7, UC_ARM_REG_R8), saved):
            self.uc.reg_write(register, value)
        self.uc.reg_write(UC_ARM_REG_R0, ACTOR)
        self.uc.reg_write(UC_ARM_REG_LR, RETURN)
        self.uc.reg_write(UC_ARM_REG_SP, STACK)
        self.uc.emu_start(HOOK_CAVE, RETURN, count=500)
        assert self.uc.reg_read(UC_ARM_REG_PC) == RETURN
        assert self.uc.reg_read(UC_ARM_REG_SP) == STACK
        for register, value in zip((UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                                    UC_ARM_REG_R7, UC_ARM_REG_R8), saved):
            assert self.uc.reg_read(register) == value, register
        return self.uc.reg_read(UC_ARM_REG_R0)


def verify() -> None:
    m = Machine()
    m.byte(COUNTER, 6)
    assert m.call() == 1
    assert m.byte(COUNTER) == 7 and m.u32(PRODUCER + 8) == 0
    assert m.call() == 1
    assert m.byte(COUNTER) == 0  # vanilla reset within the very same call
    assert m.u32(PRODUCER + 8) == 1
    assert tuple(m.byte(RECORDS + i) for i in range(4)) == (2, 1, 45, 1)
    assert m.u32(RECORDS + 4) == 41 and m.u32(RECORDS + 8) == 0

    m.u32(ACTOR + 0x51C, 1)
    m.byte(COUNTER + 1, 7)
    m.u32(PLAYER + 0x60, 219 << 16)
    assert m.call() == 1
    assert m.byte(COUNTER + 1) == 0 and m.u32(PRODUCER + 8) == 2
    assert tuple(m.byte(RECORDS + 16 + i) for i in range(4)) == (2, 1, 45, 2)
    assert m.u32(RECORDS + 20) == 219

    m.player_present = False
    m.u32(ACTOR + 0x60, 88 << 16)
    m.byte(COUNTER + 1, 7)
    m.call()
    assert m.u32(RECORDS + 32 + 4) == 88
    assert m.u32(PRODUCER + 8) == 3

    m.byte(COUNTER, 7)
    m.u32(ACTOR + 0x51C, 0)
    m.collects = False
    assert m.call() == 0 and m.u32(PRODUCER + 8) == 3
    m.collects = True
    m.byte(0x02085A94, 0xFF)
    m.call()
    assert m.u32(PRODUCER + 8) == 3  # invalid area cannot create a check

    m.byte(0x02085A94, 0)
    m.byte(COUNTER, 7)
    m.u32(PRODUCER + 8, CAPACITY)
    m.u32(CONSUMER, 0)
    m.call()
    assert m.u32(PRODUCER + 8) == CAPACITY
    assert m.u32(PRODUCER + 12) == 1  # overflow is visible, not silent
    print("Native Red Coin hook: same-call reset, both slots, payload, no false event, overflow OK")


if __name__ == "__main__":
    verify()
