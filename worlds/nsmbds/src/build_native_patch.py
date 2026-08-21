"""Build the complete native_hooks.bsdiff4 from a clean USA NSMBDS ROM."""

from __future__ import annotations

import argparse
import hashlib
import runpy
import struct
from pathlib import Path

try:
    import bsdiff4
    import ndspy.code
    import ndspy.codeCompression
    import ndspy.rom
except ImportError as error:
    raise SystemExit(
        "Missing build dependency. Install/import 'bsdiff4' and 'ndspy', "
        "then run this script again."
    ) from error


SOURCE_ROOT = Path(__file__).resolve().parent
WORLD_ROOT = SOURCE_ROOT.parent
METADATA_ROOT = SOURCE_ROOT / "native_hooks"
EXPECTED_BASE_SHA256 = "9f67fef1b4c73e966767f6153431ada3751dc1b0da2c70f386c14a5e3017f354"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def arm_branch(source: int, target: int, *, link: bool = False) -> int:
    displacement = target - (source + 8)
    if displacement % 4:
        raise ValueError(f"Unaligned ARM branch: {source:#010x} -> {target:#010x}")
    word_offset = displacement // 4
    if not -(1 << 23) <= word_offset < (1 << 23):
        raise ValueError(f"ARM branch is out of range: {source:#010x} -> {target:#010x}")
    return (0xEB000000 if link else 0xEA000000) | (word_offset & 0xFFFFFF)


def checked_write(data: bytearray, offset: int, expected: bytes, replacement: bytes, label: str) -> None:
    actual = bytes(data[offset : offset + len(expected)])
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex()} at offset {offset:#x}, got {actual.hex()}"
        )
    data[offset : offset + len(replacement)] = replacement


def word(value: int) -> bytes:
    return struct.pack("<I", value)


def patch_overlay_word(overlay: ndspy.code.Overlay, address: int, expected: int, replacement: int, label: str) -> None:
    offset = address - overlay.ramAddress
    checked_write(overlay.data, offset, word(expected), word(replacement), label)


def build_patched_rom(base_bytes: bytes) -> bytes:
    actual_base_hash = sha256(base_bytes)
    if actual_base_hash != EXPECTED_BASE_SHA256:
        raise ValueError(
            "Wrong base ROM. Expected clean USA/A2DE SHA-256 "
            f"{EXPECTED_BASE_SHA256}, got {actual_base_hash}."
        )

    star = runpy.run_path(METADATA_ROOT / "star_coin_gate_hook.py")
    powerup = runpy.run_path(METADATA_ROOT / "powerup_license_hook.py")
    save_menu = runpy.run_path(METADATA_ROOT / "native_save_menu.py")
    rom = ndspy.rom.NintendoDSRom(base_bytes)
    overlays = rom.loadArm9Overlays()

    arm9 = bytearray(ndspy.codeCompression.decompress(rom.arm9))
    for address, payload, label in (
        (star["CURRENCY_GETTER_CAVE"], star["STAR_COIN_CURRENCY_HOOK_BYTES"], "Star-Coin currency cave"),
        (powerup["POWERUP_HOOK_CAVE"], powerup["POWERUP_LICENSE_HOOK_BYTES"], "Power-Up License cave"),
    ):
        offset = address - rom.arm9RamAddress
        checked_write(arm9, offset, bytes(len(payload)), payload, label)
    currency_site_offset = star["CURRENCY_GETTER_SITE"] - rom.arm9RamAddress
    checked_write(
        arm9,
        currency_site_offset,
        word(star["CURRENCY_GETTER_ORIGINAL_WORD"]),
        word(arm_branch(star["CURRENCY_GETTER_SITE"], star["CURRENCY_GETTER_CAVE"])),
        "Star-Coin currency hook",
    )
    rom.arm9 = ndspy.codeCompression.compress(arm9, isArm9=True)

    overlay_0 = overlays[powerup["POWERUP_OVERLAY_ID"]]
    patch_overlay_word(
        overlay_0,
        powerup["POWERUP_HOOK_SITE"],
        powerup["POWERUP_ORIGINAL_WORD"],
        arm_branch(powerup["POWERUP_HOOK_SITE"], powerup["POWERUP_HOOK_CAVE"], link=True),
        "Power-Up use hook",
    )

    overlay_8 = overlays[star["OVERLAY_ID"]]
    gate_payload = star["STAR_COIN_GATE_HOOK_BYTES"]
    gate_offset = star["HOOK_CAVE"] - overlay_8.ramAddress
    checked_write(overlay_8.data, gate_offset, bytes(len(gate_payload)), gate_payload, "Star-Coin gate cave")
    for site, expected, target, label in (
        (star["HOOK_SITE"], star["ORIGINAL_HOOK_WORD"], star["HOOK_CAVE"], "Star-Coin gate hook"),
        (star["EARLY_GATE_HOOK_SITE"], star["EARLY_GATE_ORIGINAL_WORD"], star["EARLY_GATE_HOOK_ENTRY"], "Early gate hook"),
        (star["COUNTER_UPDATE_SITE"], star["COUNTER_UPDATE_ORIGINAL_WORD"], star["COUNTER_UPDATE_ENTRY"], "Star-Coin counter hook"),
    ):
        patch_overlay_word(overlay_8, site, expected, arm_branch(site, target), label)
    for address, expected, replacement in save_menu["PATCHES"]:
        patch_overlay_word(overlay_8, address, expected, replacement, "Native SAVE menu")

    overlay_10 = overlays[powerup["POWERUP_PICKUP_OVERLAY_ID"]]
    patch_overlay_word(
        overlay_10,
        powerup["POWERUP_PICKUP_HOOK_SITE"],
        powerup["POWERUP_PICKUP_ORIGINAL_WORD"],
        arm_branch(powerup["POWERUP_PICKUP_HOOK_SITE"], powerup["POWERUP_PICKUP_HOOK_ENTRY"]),
        "Power-Up pickup hook",
    )

    for overlay_id in (powerup["POWERUP_OVERLAY_ID"], star["OVERLAY_ID"], powerup["POWERUP_PICKUP_OVERLAY_ID"]):
        overlay = overlays[overlay_id]
        # Modified overlays no longer match the retail hash table. The runtime
        # patch has always cleared this verification flag for those overlays.
        overlay.verifyHash = False
        rom.files[overlay.fileID] = overlay.save(compress=overlay.compressed)
    rom.arm9OverlayTable = ndspy.code.saveOverlayTable(overlays)

    bmg_file_id = rom.filenames.idOf(star["COURSE_BMG"])
    course_bmg = bytearray(rom.files[bmg_file_id])
    # Message 15 is the final message. Its DAT1-relative offset is stored in
    # the last INF1 entry; keeping the file size fixed preserves all sections.
    inf1_offset = course_bmg.index(b"INF1")
    inf1_entry_size = struct.unpack_from("<H", course_bmg, inf1_offset + 10)[0]
    inf1_entries_offset = inf1_offset + 16
    message_offset = struct.unpack_from(
        "<I", course_bmg, inf1_entries_offset + star["PERMIT_MESSAGE_ID"] * inf1_entry_size
    )[0]
    dat1_offset = course_bmg.index(b"DAT1")
    dat1_payload_offset = dat1_offset + 8
    file_offset = dat1_payload_offset + message_offset
    encoded_message = star["PERMIT_MESSAGE"].encode("utf-16le") + b"\0\0"
    if len(encoded_message) > len(course_bmg) - file_offset:
        raise ValueError("Star-Coin gate message does not fit in course.bmg.")
    course_bmg[file_offset:] = encoded_message.ljust(len(course_bmg) - file_offset, b"\0")
    rom.files[bmg_file_id] = course_bmg

    return rom.save()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_rom", type=Path, help="Clean USA/A2DE NSMBDS ROM")
    parser.add_argument(
        "--output",
        type=Path,
        default=WORLD_ROOT / "rom" / "native_hooks.bsdiff4",
        help="Output .bsdiff4 path (default: checked-in runtime patch)",
    )
    parser.add_argument("--patched-rom", type=Path, help="Optionally also write the fully patched ROM")
    args = parser.parse_args()

    base_bytes = args.base_rom.read_bytes()
    patched_bytes = build_patched_rom(base_bytes)
    patch_bytes = bsdiff4.diff(base_bytes, patched_bytes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch_bytes)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(patched_bytes)

    print(f"Patched ROM SHA-256: {sha256(patched_bytes)}")
    print(f"Patch SHA-256:       {sha256(patch_bytes)}")
    print(f"Wrote: {args.output}")


if __name__ == "__main__":
    main()
