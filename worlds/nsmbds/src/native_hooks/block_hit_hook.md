# Native static block capture (USA/A2DE)

The four verified Overlay 0 calls at `0209E910`, `0209E9F0`, `0209EB20`, and
`0209EB50` now call `02001A00` instead of `changeTile` at `020AF30C`. These are
exactly the call sites accepted by the previous Lua LR filter. All arguments,
registers and incoming condition flags are restored before tail-calling the
unmodified function; its stack argument and original return address remain
unchanged. The player pointer at hitBlock's stack offset `28` is read at `58`
after the hook saves 48 bytes. Player `+77E == 2` identifies a ground pound.
`changeTile` receives 16-pixel coordinates. The hook stores catalog coordinates
as `X = pixel_x / 16` and `Y = -(pixel_y / 16) - 1`, matching the runtime
catalog's inverted editor-row convention.

## Allocation and protocol

The clean ARM9 has zero-filled linker padding at `020019C0..02002FFF`.
The payload uses `02001A00..02002C3F`, below the existing currency hook at
`02002EC0` and license/protection state at `02002F00..02002FFF`. It is not
overlay or heap memory. The builder requires the entire allocation to be zero
in the verified base ROM and verifies all original BL instructions.

| Address | Owner | Contents |
|---|---|---|
| `02001A00..02001BFF` | ROM | ARM hook and literal pool |
| `02001C00` | ROM/CPU | `APBH`, u32 version 1, u32 write sequence, u32 overflow count |
| `02001C20` | Lua/client | u32 read sequence, u32 enabled (initially 1) |
| `02001C40..02002C3F` | CPU | 256 records of 16 bytes |

Each record contains u8 type/world/level/area, u32 X, s32 Y, and u32 sequence.
Unsigned sequence subtraction handles wraparound. The producer never writes
the consumer's 32-byte cache line: it invalidates that line before reading
the latest Lua acknowledgement/configuration. Record lines are cleaned and
the write buffer drained before the producer sequence is published and
cleaned. This is necessary because BizHawk Main RAM accesses bypass ARM9 cache.

Lua acknowledges each ring entry only after retaining it in its deduplicated
delivery queue. The queue has no 64-event drop limit and survives module hot
reload for the same ROM hash. Existing mailbox payload-before-sequence and
client ACK handling remain in place. Area exits and observer resets do not
clear pending deliveries. A full Lua VM/emulator shutdown does not preserve
the Lua delivery queue: keep the script running and finish synchronization.
Ring overflow never overwrites unread entries and produces an explicit
warning; the ring is not a replacement for a running Lua consumer.

Moving-block open/switch state and ground-pound actor correlation remain in
Lua. Static actor/position fallbacks and the static block Execute callback
are removed. Ground Clap, Head Bonk and input traps remain independent.
With both Blocksanity and 1-Up checks disabled, the client disables the ROM
producer through its guarded consumer configuration word.

## Building and migration

Use `build_native_hooks.ps1` with devkitARM, or the optional local
`assemble_block_hit_hook.py --output <path>` with `keystone-engine`. Rebuild
`native_hooks.bsdiff4` with `build_native_patch.py` and a clean USA ROM, then
update/check `native_hooks_manifest.json`. No online assembler is used.

Patch protocol 2 reserves the last 32 bytes of the 32-MiB ROM for the marker
at `01FFFFE0`. The old `013A57A8` location is unsafe after NitroFS repacking.
The builder pads the ROM to this size; the seed procedure validates the marker
again after asset patching. Old ROMs/patch files and old savestates must not
be used with this runtime. Regenerate the patch and cold-boot the new ROM.

Live gameplay and FPS still require manual confirmation, particularly static
1-Ups, multi-coin blocks, ground pounds, area exits, flying/switch blocks and
the World 6-2 bonus room. No claim of a fixed FPS gain is made by the build.
