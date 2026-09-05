.syntax unified
.arm

@ Called ONLY by the four verified hitBlock -> changeTile BL instructions in
@ A2DE Overlay 0. Preserve all arguments, the stack argument, LR and flags,
@ then tail-call the unmodified changeTile. No emulator execution callbacks.
.equ CHANGE_TILE,        0x020AF30C
.equ PRODUCER,           0x02001C00
.equ CONSUMER,           0x02001C20
.equ RECORDS,            0x02001C40
.equ CURRENT_WORLD,      0x02088BFC
.equ CURRENT_LEVEL,      0x02085A9C
.equ CURRENT_AREA,       0x02085A94
.equ CAPACITY,           256

.section .text
.global _start
.type _start, %function
_start:
    push    {r0-r8, r12, lr}
    mrs     r12, cpsr
    push    {r12}

    @ Lua owns this entire cache line. Discard stale CPU copies before reads;
    @ never clean it back over a newer Lua acknowledgement/configuration.
    ldr     r4, =CONSUMER
    mcr     p15, 0, r4, c7, c6, 1
    ldr     r5, [r4, #4]
    cmp     r5, #0
    beq     resume_change_tile

    ldr     r6, =CURRENT_WORLD
    ldrb    r6, [r6]
    cmp     r6, #7
    bhi     resume_change_tile
    ldr     r7, =CURRENT_LEVEL
    ldrb    r7, [r7]
    cmp     r7, #0x16
    bhi     resume_change_tile
    ldr     r8, =CURRENT_AREA
    ldrb    r8, [r8]
    cmp     r8, #0xFF
    beq     resume_change_tile

    ldr     r0, =PRODUCER
    ldr     r3, [r0, #8]
    ldr     r5, [r4]
    sub     r5, r3, r5
    cmp     r5, #CAPACITY
    bhs     buffer_full

    and     r5, r3, #0xFF
    ldr     r4, =RECORDS
    add     r4, r4, r5, lsl #4
    mov     r5, #0x11
    @ hitBlock already resolved its player at its stack offset +0x28.
    @ Our saved registers/flags add 0x30. This is the hit-time player, not a
    @ potentially stale Lua player pointer from the previous frame.
    ldr     r12, [sp, #0x58]
    cmp     r12, #0x02000000
    blo     write_record
    ldr     r5, =0x023FF880
    cmp     r12, r5
    mov     r5, #0x11
    bhi     write_record
    ldrb    r12, [r12, #0x77E]
    cmp     r12, #2
    moveq   r5, #0x12
write_record:
    strb    r5, [r4]
    strb    r6, [r4, #1]
    strb    r7, [r4, #2]
    strb    r8, [r4, #3]
    @ changeTile receives 16-pixel coordinates. The location catalog uses
    @ horizontal cells and the inverted editor row convention.
    mov     r1, r1, lsr #4
    mov     r2, r2, lsr #4
    mvn     r2, r2                  @ -(pixel_y / 16) - 1
    str     r1, [r4, #4]
    str     r2, [r4, #8]
    str     r3, [r4, #12]
    @ Publish data to physical RAM BEFORE exposing its sequence to Lua.
    mcr     p15, 0, r4, c7, c10, 1
    mcr     p15, 0, r4, c7, c10, 4
    add     r3, r3, #1
    str     r3, [r0, #8]
    b       publish_header
buffer_full:
    @ Never overwrite unread records or stall the game. Lua reports overflow
    @ explicitly; with the script running it drains the ring every frame.
    ldr     r3, [r0, #12]
    add     r3, r3, #1
    str     r3, [r0, #12]
publish_header:
    mcr     p15, 0, r0, c7, c10, 1
    mcr     p15, 0, r0, c7, c10, 4
resume_change_tile:
    pop     {r12}
    msr     cpsr_f, r12
    pop     {r0-r8, r12, lr}
    b       CHANGE_TILE
.ltorg
.size _start, . - _start

@ Permanent, zero-filled main-ARM9 linker padding, not an overlay or heap.
@ Producer and consumer have separate 32-byte ARM946 data-cache lines.
.org 0x200
    .ascii "APBH"
    .word 1
    .word 0                          @ producer sequence (CPU only)
    .word 0                          @ overflow count (CPU only)
.org 0x220
    .word 0                          @ consumer sequence (Lua only)
    .word 1                          @ capture enabled until configured
.org 0x240
    .space 4096                      @ 256 records, 16 bytes each
