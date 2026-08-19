.syntax unified
.arm

@ Native guards for licensed world pickups and the touchscreen reserve slot.
.equ LICENSE_STATE,       0x02002FE8
.equ RESERVE_GETTER,      0x02020240
.equ PICKUP_CONTINUE,     0x020D482C
.equ PICKUP_CLEANUP,      0x020D4A14
.equ LICENSE_MODE_FULL,   3
.equ LICENSE_MODE_MAJOR,  2
.equ LICENSE_MODE_TYPES,  1
.equ MINI_LICENSE_BIT,    0x01
.equ SHELL_LICENSE_BIT,   0x02
.equ MEGA_LICENSE_BIT,    0x04
.equ RESERVE_LICENSE_BIT, 0x08
.equ MUSHROOM_LICENSE_BIT, 0x10
.equ FIRE_LICENSE_BIT,     0x20

.section .text
.global _start
.type _start, %function

_start:
reserve_availability_guard:
    ldr     r2, =LICENSE_STATE
    ldrb    r3, [r2]
    cmp     r3, #LICENSE_MODE_FULL
    bne     reserve_availability_vanilla
    ldrb    r3, [r2, #1]
    tst     r3, #RESERVE_LICENSE_BIT
    moveq   r0, #0
    bxeq    lr

reserve_availability_vanilla:
    b       RESERVE_GETTER
.ltorg

.org 0x40
.global pickup_license_guard
pickup_license_guard:
    ldr     r2, =LICENSE_STATE
    ldrb    r3, [r2]
    cmp     r3, #LICENSE_MODE_TYPES
    blo     pickup_allowed

    ldr     r1, [r8, #0x574]
    cmp     r1, #25
    beq     check_mini
    cmp     r1, #11
    beq     check_shell
    cmp     r1, #5
    beq     check_mega

    cmp     r3, #LICENSE_MODE_FULL
    bne     pickup_allowed
    add     r1, r8, #0x500
    ldrh    r1, [r1, #0xA0]
    cmp     r1, #0
    beq     check_mushroom
    cmp     r1, #1
    beq     check_fire
    b       pickup_allowed

check_mega:
    cmp     r3, #LICENSE_MODE_MAJOR
    blo     pickup_allowed
    ldrb    r3, [r2, #1]
    tst     r3, #MEGA_LICENSE_BIT
    b       finish_pickup_check

check_shell:
    ldrb    r3, [r2, #1]
    tst     r3, #SHELL_LICENSE_BIT
    b       finish_pickup_check

check_mini:
    ldrb    r3, [r2, #1]
    tst     r3, #MINI_LICENSE_BIT
    b       finish_pickup_check

check_mushroom:
    ldrb    r3, [r2, #1]
    tst     r3, #MUSHROOM_LICENSE_BIT
    b       finish_pickup_check

check_fire:
    ldrb    r3, [r2, #1]
    tst     r3, #FIRE_LICENSE_BIT

finish_pickup_check:
    bne     pickup_allowed
    mov     r5, #3
    b       PICKUP_CLEANUP

pickup_allowed:
    mov     r0, r6
    b       PICKUP_CONTINUE
.ltorg

.size _start, . - _start
