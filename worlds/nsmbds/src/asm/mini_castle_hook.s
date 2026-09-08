.syntax unified
.arm

.equ MINI_CASTLE_FLAGS,    0x02002FF3
.equ CONTINUE,             0x020CE328

.section .text
.global _start
.type _start, %function

_start:
    @ func_020CE298 selected the next world using the saved power-up.
    @ r5 = source world, r4 = destination world (zero based).
    @ Its three callers are castle-clear/world-transition paths.
    @ Replay the displaced instruction and preserve registers and flags.
    mov     r0, r4
    stmdb   sp!, {r1-r3, ip}
    mrs     ip, cpsr
    ldr     r3, =MINI_CASTLE_FLAGS
    @ Trace: source, destination, and wrapping event sequence.
    strb    r5, [r3, #2]
    strb    r4, [r3, #3]
    ldrb    r1, [r3, #1]
    add     r1, r1, #1
    strb    r1, [r3, #1]
    cmp     r5, #1
    bne     check_w5
    cmp     r4, #3
    moveq   r2, #1
    beq     set_flag
    b       done

check_w5:
    cmp     r5, #4
    bne     done
    cmp     r4, #6
    moveq   r2, #2
    bne     done

set_flag:
    ldrb    r1, [r3]
    orr     r1, r1, r2
    strb    r1, [r3]

done:
    @ BizHawk reads Main RAM behind the emulated ARM9 cache. Publish the sticky
    @ flag immediately and drain the write buffer before returning to Vanilla.
    mcr     p15, 0, r3, c7, c10, 1
    mcr     p15, 0, r3, c7, c10, 4

    msr     cpsr_f, ip
    ldmia   sp!, {r1-r3, ip}
    b       CONTINUE

.ltorg

.size _start, . - _start
