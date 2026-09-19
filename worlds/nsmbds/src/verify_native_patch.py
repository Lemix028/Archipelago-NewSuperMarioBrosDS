"""Verify the checked-in native patch against a clean USA/A2DE ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import struct
from pathlib import Path

import bsdiff4
import ndspy.codeCompression
import ndspy.rom

SOURCE = Path(__file__).resolve().parent
WORLD = SOURCE.parent
HOOKS = SOURCE / "native_hooks"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def arm_branch(source: int, target: int) -> bytes:
    displacement = target - (source + 8)
    assert displacement % 4 == 0
    return struct.pack("<I", 0xEA000000 | ((displacement // 4) & 0xFFFFFF))


def check(data: bytes, base: int, address: int, expected: bytes, label: str) -> None:
    offset = address - base
    actual = data[offset:offset + len(expected)]
    if actual != expected:
        first = next(i for i, (a, b) in enumerate(zip(actual, expected)) if a != b)
        raise AssertionError(f"{label} differs at {address + first:#010x}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path)
    args = parser.parse_args()

    manifest = json.loads((HOOKS / "native_hooks_manifest.json").read_text(encoding="utf-8"))
    base = args.base_rom.read_bytes()
    assert sha256(base) == "9f67fef1b4c73e966767f6153431ada3751dc1b0da2c70f386c14a5e3017f354"
    patch = (WORLD / "rom" / "native_hooks.bsdiff4").read_bytes()
    assert sha256(patch) == manifest["native_hooks_bsdiff4_sha256"]
    patched = bsdiff4.patch(base, patch)
    assert sha256(patched) == manifest["patched_rom_sha256"]

    rom = ndspy.rom.NintendoDSRom(patched)
    compressed_end = struct.unpack_from("<I", rom.arm9, 0xB5C)[0]
    assert compressed_end == rom.arm9RamAddress + len(rom.arm9), (
        f"ARM9 compressed end pointer {compressed_end:#010x} does not match "
        f"the loaded length {rom.arm9RamAddress + len(rom.arm9):#010x}"
    )
    arm9 = ndspy.codeCompression.decompress(rom.arm9)
    head = runpy.run_path(HOOKS / "head_bonk_hook.py")
    inputs = runpy.run_path(HOOKS / "input_trap_hook.py")
    block = runpy.run_path(HOOKS / "block_hit_hook.py")
    block_payload = bytearray(block["BLOCK_HIT_HOOK_BYTES"])
    head_offset = head["HOOK_CAVE"] - block["BLOCK_HIT_HOOK_CAVE"]
    block_payload[head_offset:head_offset + len(head["HOOK_BYTES"])] = head["HOOK_BYTES"]
    check(arm9, rom.arm9RamAddress, block["BLOCK_HIT_HOOK_CAVE"], block_payload, "block payload")
    check(arm9, rom.arm9RamAddress, head["HOOK_CAVE"], head["HOOK_BYTES"], "Head Bonk payload")
    check(arm9, rom.arm9RamAddress, inputs["CONTROL"], inputs["DEFAULT_CONTROL_AND_STATE"], "APIT mailbox")
    check(arm9, rom.arm9RamAddress, inputs["HOOK_CAVE"], inputs["HOOK_BYTES"], "input payload")
    for site, entry, label in (
        (inputs["GENERAL_SITE"], inputs["GENERAL_ENTRY"], "general input branch"),
        (inputs["BUTTONS_SITE"], inputs["BUTTONS_ENTRY"], "button input branch"),
    ):
        check(arm9, rom.arm9RamAddress, site, arm_branch(site, entry), label)

    overlay = rom.loadArm9Overlays()[block["BLOCK_HIT_OVERLAY_ID"]]
    check(overlay.data, overlay.ramAddress, head["HOOK_SITE"],
          arm_branch(head["HOOK_SITE"], head["HOOK_CAVE"]), "Head Bonk entry branch")
    print("Native patch: bsdiff round-trip, ROM hash, hook bytes, APIT mailbox, and branches OK")


if __name__ == "__main__":
    main()
