.syntax unified
.arm

.equ PERMIT_MASKS,       0x020EE100
.equ SELECTOR_TRACE,     0x020EE120
.equ CURRENT_WORLD,      0x02088BFC
.equ VANILLA_CONTINUE,   0x020D3BA8
.equ MESSAGE_ROUTINE,    0x020CDC30
.equ MESSAGE_FINISH,     0x020D3C0C
.equ MESSAGE_CONTEXT,    0x020EE3F4
.equ MESSAGE_STYLE,      0x020EE398
.equ GATE_CONNECTIONS,   0x020EE404
.equ EARLY_RETURN,       0x020D6D3C
.equ COUNTER_EQUAL,      0x020CF0CC
.equ COUNTER_DECREASE,   0x020CF09C

.section .text
.global _start
.type _start, %function

_start:
    stmdb   sp!, {r4}
    mov     r2, r0

    ldr     r1, [r2, #0x214]

    ldr     r0, =SELECTOR_TRACE
    ldrb    r3, [r2, #0x2F2]
    strb    r3, [r0]
    ldr     r3, =CURRENT_WORLD
    ldr     r3, [r3]
    strb    r3, [r0, #1]
    strb    r1, [r0, #2]
    cmp     r3, #7
    bhi     restore_vanilla

    adr     r4, gate_counts
    ldrb    ip, [r4, r3]
    cmp     r1, ip
    bhs     restore_vanilla

    ldr     r0, =PERMIT_MASKS
    mcr     p15, 0, r0, c7, c6, 1
    ldrb    r0, [r0, r3]
    mov     ip, #1
    tst     r0, ip, lsl r1
    ldmia   sp!, {r4}
    beq     missing_permit
    b       vanilla

restore_vanilla:
    ldmia   sp!, {r4}

vanilla:
    ldrb    r0, [r2, #0x2EE]
    b       VANILLA_CONTINUE

missing_permit:
    mov     r0, #0
    strb    r0, [r2, #0x2EE]
    ldr     r0, =MESSAGE_CONTEXT
    ldr     r3, =MESSAGE_STYLE
    ldr     r2, [r0]
    mov     r4, #4
    mov     r0, #15
    mov     r1, #0
    strb    r4, [r3]
    bl      MESSAGE_ROUTINE
    b       MESSAGE_FINISH

.align 2
gate_counts:
    .byte   4, 4, 3, 5, 5, 5, 3, 3

.ltorg

.org 0xBC
.global early_gate_identity
.type early_gate_identity, %function
early_gate_identity:
    ldrb    r1, [r1, #1]

    ldr     r0, =GATE_CONNECTIONS
    ldr     r0, [r0]
    mov     r3, #0

early_find:
    ldr     ip, [r0, r3, lsl #4]
    cmp     r7, ip
    beq     early_found
    add     r3, r3, #1
    cmp     r3, #5
    blt     early_find
    mvn     r3, #0

early_found:
    add     r2, sl, #0x2000
    str     r3, [r2, #0x214]
    str     r7, [r2, #0x218]
    b       EARLY_RETURN

.ltorg
.size _start, . - _start

.org 0xFC
.global ap_counter_update
.type ap_counter_update, %function
ap_counter_update:
    beq     COUNTER_EQUAL
    bgt     COUNTER_DECREASE
    str     r0, [r4, #0x86C]
    mov     r1, #0
    str     r1, [r4, #0x870]
    b       COUNTER_EQUAL
