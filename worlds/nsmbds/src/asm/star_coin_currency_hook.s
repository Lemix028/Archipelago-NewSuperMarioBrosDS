.syntax unified
.arm

.equ CURRENCY_MAILBOX,   0x020EDC18
.equ CURRENCY_MAGIC,     0x43535041
.equ STAR_COIN_STATE,    0x02088BDC
.equ CURRENCY_CONTINUE,  0x02012A24

.section .text
.global _start
.type _start, %function

_start:
    ldr     r0, =CURRENCY_MAILBOX
    mcr     p15, 0, r0, c7, c6, 1
    ldr     r1, [r0]
    ldr     r2, =CURRENCY_MAGIC
    cmp     r1, r2
    ldreq   r0, [r0, #4]
    bxeq    lr

    ldr     r0, =STAR_COIN_STATE
    b       CURRENCY_CONTINUE

.ltorg
.size _start, . - _start
