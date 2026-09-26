@ USA/A2DE Overlay 54 calls 02154208 at 02154024 after a Red Coin touches
@ a player. The callee increments counter[player] and clears it at eight before
@ returning 1. Wrap that call so a successful 7 -> 8 is captured even when
@ the counter has already returned to zero by the next Lua frame.
@
@ Linked in previously unreferenced, zero-filled main ARM9 padding.
@ Producer, consumer and records occupy separate data-cache lines.

red_coin_entry:
    push    {r4-r8, lr}
    mov     r4, r0                  @ Red Coin actor
    ldr     r5, [r4, #0x51c]       @ vanilla player/counter index, 0 or 1
    mov     r6, #0
    cmp     r5, #1
    bhi     call_vanilla
    ldr     r0, =0x020CA2D4
    ldrb    r6, [r0, r5]           @ count before vanilla can reset it
call_vanilla:
    mov     r0, r4
    bl      0x02154208
    mov     r7, r0                  @ preserve the vanilla return value
    cmp     r7, #1                 @ only an actual collection succeeds
    bne     done
    cmp     r6, #7
    bne     done
    cmp     r5, #1
    bhi     done

    ldr     r0, =0x02088BFC       @ runtime course identity (same as Lua)
    ldrb    r8, [r0]
    cmp     r8, #7
    bhi     done
    ldr     r0, =0x02085A9C
    ldrb    r6, [r0]
    cmp     r6, #0x16
    bhi     done
    ldr     r0, =0x02085A94
    ldrb    r2, [r0]
    cmp     r2, #0xff
    beq     done

    ldr     r0, =0x02002DE0       @ ROM-owned header: magic, version, seq, drops
    ldr     r1, [r0, #8]
    ldr     r2, =0x02002E00       @ Lua-owned consumer cursor
    mcr     p15, 0, r2, c7, c6, 1 @ invalidate only the consumer cache line
    ldr     r2, [r2]
    sub     r3, r1, r2
    cmp     r3, #8
    bhs     overflow

    and     r3, r1, #7
    ldr     r2, =0x02002E20
    add     r2, r2, r3, lsl #4
    ldr     r3, [r4, #0x60]        @ coin X if the player pointer vanished
    mov     r3, r3, asr #16
    mov     r4, r2
    strb    r8, [r4]
    mov     r8, r3
    strb    r6, [r4, #1]
    ldr     r2, =0x02085A94
    ldrb    r2, [r2]
    strb    r2, [r4, #2]
    add     r2, r5, #1             @ Lua/AP counter convention is 1..2
    strb    r2, [r4, #3]
    str     r1, [r4, #8]          @ record's own sequence for torn-read check

    mov     r0, r5
    bl      0x02020608            @ Game::getPlayer(player index)
    cmp     r0, #0
    moveq   r2, r8               @ coin and player meet at collection
    ldrne   r2, [r0, #0x60]
    movne   r2, r2, asr #16       @ Fx32 -> editor tile X
    str     r2, [r4, #4]

    mcr     p15, 0, r4, c7, c10, 1
    mcr     p15, 0, r4, c7, c10, 4
    ldr     r0, =0x02002DE0
    ldr     r1, [r0, #8]
    add     r1, r1, #1
    str     r1, [r0, #8]          @ publish only after the payload is in RAM
    b       flush_header
overflow:
    ldr     r2, [r0, #12]
    add     r2, r2, #1
    str     r2, [r0, #12]
flush_header:
    mcr     p15, 0, r0, c7, c10, 1
    mcr     p15, 0, r0, c7, c10, 4
done:
    mov     r0, r7
    pop     {r4-r8, pc}
