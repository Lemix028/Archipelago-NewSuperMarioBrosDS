@ USA/A2DE ARM9 input filter. Linked at 0x02000B84. The builder verifies the
@ two displaced instructions and all bytes in this code cave before patching.
@ Lua owns 0x02002C40..5F; native state owns 0x02002C60..7F.

general_entry:
    push    {r0-r12, lr}
    mrs     r12, cpsr
    push    {r12}
    mov     r0, #0
    bl      filter_input
    pop     {r12}
    msr     cpsr_f, r12
    pop     {r0-r12, lr}
    ldrh    r1, [sp, #12]            @ displaced 0x020100B0
    b       0x020100B4

buttons_entry:
    push    {r0-r12, lr}
    mrs     r12, cpsr
    push    {r12}
    mov     r0, #1
    bl      filter_input
    pop     {r12}
    msr     cpsr_f, r12
    pop     {r0-r12, lr}
    add     sp, sp, #4              @ displaced 0x0200A57C
    b       0x0200A580

filter_input:
    push    {lr}
    ldr     r8, =0x02002C40
    @ BizHawk Main RAM writes bypass the ARM946 cache.
    mcr     p15, 0, r8, c7, c6, 1
    ldrb    r7, [r8, #9]            @ enable; common inactive fast path
    cmp     r7, #0
    beq     filter_done
    ldrb    r7, [r8, #8]            @ mode
    cmp     r7, #0
    beq     filter_done
    ldr     r4, =0x020CA28C        @ stage freeze
    ldrb    r4, [r4]
    cmp     r4, #0
    bne     filter_done
    ldr     r4, =0x020CA870        @ pause menu
    ldrb    r4, [r4]
    cmp     r4, #0
    bne     filter_done

    ldr     r9, =0x02002C60        @ native-owned state cache line
    ldr     r4, [r8, #20]          @ Trap generation
    ldr     r5, [r9, #8]
    cmp     r4, r5
    beq     state_ready
    mov     r5, #0
    strb    r5, [r9]               @ sticky direction
    strb    r5, [r9, #1]           @ sticky frames
    strb    r5, [r9, #3]           @ no-turn direction
    mvn     r5, #0
    str     r5, [r9, #4]           @ sticky last frame = -1
    str     r4, [r9, #8]
state_ready:
    cmp     r0, #0
    bne     filter_buttons
    ldr     r0, =0x020888E2        @ general keys
    mov     r1, #0
    bl      filter_word
    b       filter_done
filter_buttons:
    ldr     r0, =0x02087650        @ held buttons
    mov     r1, #1
    bl      filter_word
    ldr     r0, =0x02087652        @ newly pressed buttons
    mov     r1, #2
    bl      filter_word
filter_done:
    pop     {pc}

@ r0 = word address, r1 = 0 general / 1 held / 2 pressed.
@ r2 is the modified word; r3 retains the original word.
filter_word:
    ldrh    r2, [r0]
    mov     r3, r2
    cmp     r7, #1
    beq     no_jump
    cmp     r7, #2
    beq     no_sprint
    cmp     r7, #3
    beq     button_swap
    cmp     r7, #4
    beq     sticky_buttons
    cmp     r7, #5
    beq     auto_run
    cmp     r7, #6
    beq     camera_drift
    cmp     r7, #7
    beq     camera_sway
    cmp     r7, #8
    beq     boo_curse
    cmp     r7, #9
    beq     no_turnaround
    cmp     r7, #10
    beq     im_stuck
    b       word_done

no_jump:
    bic     r2, r2, #1             @ A always jumps
    ldr     r4, =0x02088F24        @ control scheme
    ldrb    r4, [r4]
    cmp     r4, #1
    biceq   r2, r2, #2             @ default: B jumps
    bicne   r2, r2, #0x400         @ alternate: X jumps
    b       word_done

no_sprint:
    bic     r2, r2, #0x800         @ Y always dashes
    ldr     r4, =0x02088F24
    ldrb    r4, [r4]
    cmp     r4, #1
    biceq   r2, r2, #0x400         @ default: X dashes
    bicne   r2, r2, #2             @ alternate: B dashes
    b       word_done

button_swap:
    ldr     r4, =0x02088F24
    ldrb    r4, [r4]
    cmp     r4, #1
    bne     swap_alternate
    @ Swap A/X and B/Y in a single pair of bit differences.
    eor     r6, r2, r2, lsr #10
    and     r6, r6, #3
    eor     r2, r2, r6
    eor     r2, r2, r6, lsl #10
    b       word_done
swap_alternate:
    @ Swap A/B and X/Y.
    eor     r6, r2, r2, lsr #1
    mov     r5, #1
    orr     r5, r5, #0x400
    and     r6, r6, r5
    eor     r2, r2, r6
    eor     r2, r2, r6, lsl #1
    b       word_done

sticky_buttons:
    ldr     r4, [r8, #16]          @ emulator frame supplied by Lua
    ldr     r5, [r9, #4]
    cmp     r4, r5
    beq     sticky_apply
    str     r4, [r9, #4]
    and     r5, r2, #0x30
    cmp     r5, #0x10
    beq     sticky_right
    cmp     r5, #0x20
    beq     sticky_left
    ldrb    r5, [r9, #1]
    cmp     r5, #0
    subne   r5, r5, #1
    strbne  r5, [r9, #1]
    b       sticky_apply
sticky_right:
    mov     r5, #1
    strb    r5, [r9]
    b       sticky_refresh
sticky_left:
    mvn     r5, #0
    strb    r5, [r9]
sticky_refresh:
    ldrb    r5, [r8, #24]
    strb    r5, [r9, #1]
sticky_apply:
    cmp     r1, #2                 @ never synthesize a pressed edge
    beq     word_done
    tst     r2, #0x30             @ physical direction always wins
    bne     word_done
    ldrb    r5, [r9, #1]
    cmp     r5, #0
    beq     word_done
    ldrsb   r5, [r9]
    cmp     r5, #0
    orrgt   r2, r2, #0x10
    orrlt   r2, r2, #0x20
    b       word_done

auto_run:
    cmp     r1, #2                 @ pressed buttons are untouched
    beq     word_done
    @ Lua forces horizontal velocity once per frame. Keep the physical D-Pad
    @ untouched here so the player can freely choose and change direction.
    orr     r2, r2, #0x800         @ Y always dashes
    b       word_done

camera_drift:
    cmp     r1, #2
    ldrbeq  r4, [r8, #11]          @ pressed shoulder pulse
    ldrbne  r4, [r8, #10]
    b       camera_apply
camera_sway:
    cmp     r1, #2
    beq     word_done              @ do not touch pressed shoulders
    ldrb    r4, [r8, #10]
camera_apply:
    bic     r2, r2, #0x300
    orr     r2, r2, r4, lsl #8
    b       word_done

boo_curse:
    ldrb    r4, [r8, #12]
    cmp     r4, #0
    beq     word_done
    and     r4, r2, #0x30
    cmp     r4, #0x10
    cmpne   r4, #0x20
    eoreq   r2, r2, #0x30
    b       word_done

no_turnaround:
    and     r4, r2, #0x30
    cmp     r4, #0x10
    moveq   r5, #1
    beq     turn_direction
    cmp     r4, #0x20
    bne     word_done
    mvn     r5, #0
turn_direction:
    ldrsb   r6, [r9, #3]
    cmp     r6, #0
    strbeq  r5, [r9, #3]
    beq     word_done
    cmp     r5, r6
    bicne   r2, r2, r4             @ block only the opposite request
    b       word_done

im_stuck:
    and     r2, r2, #0x0C          @ preserve Select and Start
word_done:
    cmp     r2, r3
    strhne  r2, [r0]
    bx      lr
