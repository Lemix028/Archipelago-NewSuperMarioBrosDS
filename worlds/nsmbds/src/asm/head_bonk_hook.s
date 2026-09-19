@ Native replacement for the old Lua Execute hook at hitBlock entry 0209E7D0.
@ Linked at 02001B40 in the unused tail of the block-hook code cave.
@ Lua supplies the same last-observed player pointer used by the old callback.

head_bonk_entry:
    push    {r4, r5, r12, lr}
    mrs     r12, cpsr
    push    {r12}
    ldr     r4, =0x02002C40
    mcr     p15, 0, r4, c7, c6, 1
    ldrb    r5, [r4, #25]          @ active Head Bonk Trap
    cmp     r5, #0
    beq     head_bonk_done
    ldr     r5, =0x020CA28C       @ stage freeze
    ldrb    r5, [r5]
    cmp     r5, #0
    bne     head_bonk_done
    ldr     r5, =0x020CA870       @ pause menu
    ldrb    r5, [r5]
    cmp     r5, #0
    bne     head_bonk_done
    ldr     r12, [r4, #28]        @ Lua's last active player
    cmp     r12, #0x02000000
    blo     head_bonk_done
    ldr     r5, =0x023FF880
    cmp     r12, r5
    bhi     head_bonk_done
    ldrb    r5, [r12, #0x76C]     @ animation
    cmp     r5, #0x10             @ ground-pound impact
    beq     head_bonk_done
    ldr     r5, [r12, #0x0D4]     @ signed Y velocity
    cmp     r5, #0
    bgt     publish_head_bonk
    ldrb    r5, [r4, #26]         @ was moving up at Lua frame end
    cmp     r5, #0
    beq     head_bonk_done
publish_head_bonk:
    ldr     r4, =0x02002C70       @ native-owned event sequence
    ldr     r5, [r4]
    add     r5, r5, #1
    str     r5, [r4]
    mcr     p15, 0, r4, c7, c10, 1
    mcr     p15, 0, r4, c7, c10, 4
head_bonk_done:
    pop     {r12}
    msr     cpsr_f, r12
    pop     {r4, r5, r12, lr}
    push    {r4-r11, lr}          @ displaced hitBlock prologue
    b       0x0209E7D4
