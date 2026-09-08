"""Build the complete native_hooks.bsdiff4 from a clean USA NSMBDS ROM."""

from __future__ import annotations

import argparse
import hashlib
import runpy
import struct
from pathlib import Path

try:
    import bsdiff4
    import ndspy.bmg
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
BASE_ROM_SIZE = 0x02000000
PATCH_MARKER_ROM_OFFSET = runpy.run_path(WORLD_ROOT / "data" / "patch_protocol.py")["PATCH_MARKER_ROM_OFFSET"]


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
    mini_castle = runpy.run_path(METADATA_ROOT / "mini_castle_hook.py")
    powerup = runpy.run_path(METADATA_ROOT / "powerup_license_hook.py")
    block = runpy.run_path(METADATA_ROOT / "block_hit_hook.py")
    save_menu = runpy.run_path(METADATA_ROOT / "native_save_menu.py")
    rom = ndspy.rom.NintendoDSRom(base_bytes)
    overlays = rom.loadArm9Overlays()

    arm9 = bytearray(ndspy.codeCompression.decompress(rom.arm9))
    block_payload = block["BLOCK_HIT_HOOK_BYTES"]
    if (len(block["BLOCK_HIT_CODE"]) > 0x200
            or len(block_payload) != block["BLOCK_HIT_END"] - block["BLOCK_HIT_HOOK_CAVE"]
            or block["BLOCK_HIT_END"] > star["CURRENCY_GETTER_CAVE"]):
        raise ValueError("Native block code/ring overlaps another reserved region.")
    for address, payload, label in (
        (block["BLOCK_HIT_HOOK_CAVE"], block_payload, "Block-hit code and ring cave"),
        (star["CURRENCY_GETTER_CAVE"], star["STAR_COIN_CURRENCY_HOOK_BYTES"], "Star-Coin currency cave"),
        (powerup["POWERUP_HOOK_CAVE"], powerup["POWERUP_LICENSE_HOOK_BYTES"], "Power-Up License cave"),
    ):
        offset = address - rom.arm9RamAddress
        checked_write(arm9, offset, bytes(len(payload)), payload, label)
    if powerup["POWERUP_LICENSE_STATE"] + powerup["POWERUP_STATE_SIZE"] > mini_castle["MINI_CASTLE_FLAGS"]:
        raise ValueError("Power-Up License state overlaps the Mini-Castle flags.")
    mini_castle_flags_offset = mini_castle["MINI_CASTLE_FLAGS"] - rom.arm9RamAddress
    checked_write(
        arm9,
        mini_castle_flags_offset,
        bytes(4),
        bytes(4),
        "Mini-Castle persistent flags and route trace",
    )
    currency_mailbox_offset = star["CURRENCY_MAILBOX"] - rom.arm9RamAddress
    checked_write(
        arm9,
        currency_mailbox_offset,
        bytes(star["CURRENCY_MAILBOX_SIZE"]),
        star["DEFAULT_CURRENCY_MAILBOX"],
        "Star-Coin persistent currency mailbox",
    )
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
    block_overlay = overlays[block["BLOCK_HIT_OVERLAY_ID"]]
    for address, expected in block["BLOCK_HIT_CALL_SITES"]:
        if expected != arm_branch(address, block["BLOCK_HIT_CHANGE_TILE"], link=True):
            raise ValueError(f"Unexpected original block call target at {address:#x}")
        patch_overlay_word(
            block_overlay, address, expected,
            arm_branch(address, block["BLOCK_HIT_HOOK_CAVE"], link=True),
            "Native block-hit call",
        )
    patch_overlay_word(
        overlay_0,
        powerup["POWERUP_HOOK_SITE"],
        powerup["POWERUP_ORIGINAL_WORD"],
        arm_branch(powerup["POWERUP_HOOK_SITE"], powerup["POWERUP_HOOK_CAVE"], link=True),
        "Power-Up use hook",
    )

    overlay_8 = overlays[star["OVERLAY_ID"]]
    if mini_castle["OVERLAY_ID"] != star["OVERLAY_ID"]:
        raise ValueError("Mini-Castle hook must share the world-map overlay.")
    mini_castle_payload = mini_castle["MINI_CASTLE_HOOK_BYTES"]
    mini_castle_end = mini_castle["HOOK_CAVE"] + len(mini_castle_payload)
    tier_mailbox_end = star["TIER_MAILBOX"] + star["TIER_MAILBOX_SIZE"]
    if not tier_mailbox_end <= mini_castle["HOOK_CAVE"] < mini_castle_end <= star["DATA_CAVE_END"]:
        raise ValueError("Mini-Castle hook overlaps an Overlay 8 mailbox or leaves the data cave.")
    mini_castle_offset = mini_castle["HOOK_CAVE"] - overlay_8.ramAddress
    checked_write(
        overlay_8.data,
        mini_castle_offset,
        bytes(len(mini_castle_payload)),
        mini_castle_payload,
        "Mini-Castle completion cave",
    )
    patch_overlay_word(
        overlay_8,
        mini_castle["HOOK_SITE"],
        mini_castle["ORIGINAL_HOOK_WORD"],
        arm_branch(mini_castle["HOOK_SITE"], mini_castle["HOOK_CAVE"]),
        "Mini-Castle completion hook",
    )
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
    course_bmg = ndspy.bmg.BMG(rom.files[bmg_file_id])
    if len(course_bmg.messages) != star["INVALID_TIER_MESSAGE_ID"] + 1:
        raise ValueError(
            "Unexpected course.bmg message count before adding Star-Coin Gate text."
        )
    course_bmg.messages[star["INVALID_TIER_MESSAGE_ID"]] = ndspy.bmg.Message(
        b"", star["INVALID_TIER_MESSAGE"]
    )
    for message in star["TIER_MESSAGES"]:
        course_bmg.messages.append(ndspy.bmg.Message(b"", message))
    expected_message_count = star["INDIVIDUAL_TIER_MESSAGE_BASE"] + 32
    if len(course_bmg.messages) != expected_message_count:
        raise ValueError("Unexpected course.bmg message count after adding gate text.")
    rom.files[bmg_file_id] = course_bmg.save()

    packed = rom.save()
    # Repacking shifts NitroFS files: the old fixed marker at 0x013A57A8 can
    # now be inside an asset. Reserve the last 32 bytes of the 32-MiB cart;
    # seed tokens and palette/background patches must not overlap this tail.
    if len(packed) > PATCH_MARKER_ROM_OFFSET:
        raise ValueError("Packed ROM overlaps the reserved patch-marker tail.")
    return packed.ljust(BASE_ROM_SIZE, b"\xFF")


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
