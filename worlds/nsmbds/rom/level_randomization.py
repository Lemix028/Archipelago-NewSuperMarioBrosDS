"""ROM patching for the alpha overworld level randomizer."""

from __future__ import annotations

import json
import struct
from typing import Any, Mapping

from ..data.level_randomization import (
    LEVEL_AREA_ID_BY_NAME,
    LEVEL_NODE_OFFSET_BY_NAME,
    LEVEL_RANDOMIZATION_OFF,
    mapping_from_slot_data,
)
from ..data.patch_protocol import PATCH_MARKER_ROM_OFFSET


OVERLAY_ID = 8
OVERLAY_FILE_ID = 18
OVERLAY_RAM_ADDRESS = 0x020CC2E0
OVERLAY_RAM_SIZE = 139_360


def _detect_appended_data(data: bytes) -> int | None:
    for appended_size in range(0, 0x20, 4):
        header_end = len(data) - appended_size
        if header_end < 8:
            return None
        packed, _extra_size = struct.unpack_from("<II", data, header_end - 8)
        header_size = packed >> 24
        compressed_size = packed & 0xFFFFFF
        if header_size < 8 or compressed_size > header_end:
            continue
        if all(value == 0xFF for value in data[header_end - header_size:header_end - 8]):
            return appended_size
    return None


def decompress_code_overlay(data: bytes) -> bytes:
    """Decode Nintendo DS backwards-LZ executable compression."""
    appended_size = _detect_appended_data(data)
    if appended_size is None:
        return data
    appended = data[len(data) - appended_size:] if appended_size else b""
    compressed_file = data[:len(data) - appended_size] if appended_size else data
    if compressed_file[-4:] == b"\0\0\0\0":
        return compressed_file + appended

    packed, extra_size = struct.unpack_from("<II", compressed_file, len(compressed_file) - 8)
    header_size = packed >> 24
    compressed_size = min(packed & 0xFFFFFF, len(compressed_file))
    passthrough_size = len(compressed_file) - compressed_size
    compressed = compressed_file[
        passthrough_size:len(compressed_file) - header_size
    ]
    output = bytearray(len(compressed_file) + extra_size - passthrough_size)

    written = 0
    read = 0
    mask = 1
    flags = 0
    while written < len(output):
        if mask == 1:
            if read >= len(compressed):
                raise ValueError("Overlay compression stream ended before its declared size.")
            flags = compressed[-1 - read]
            read += 1
            mask = 0x80
        else:
            mask >>= 1

        if flags & mask:
            if read + 1 >= len(compressed):
                raise ValueError("Overlay compression stream has a truncated back-reference.")
            first = compressed[-1 - read]
            second = compressed[-2 - read]
            read += 2
            length = (first >> 4) + 3
            displacement = (((first & 0x0F) << 8) | second) + 3
            if displacement > written:
                if written < 2:
                    raise ValueError("Overlay compression stream has an invalid displacement.")
                displacement = 2
            source = written - displacement
            for _ in range(length):
                if written >= len(output):
                    break
                output[-1 - written] = output[-1 - source]
                source += 1
                written += 1
        else:
            if read >= len(compressed):
                raise ValueError("Overlay compression stream has a truncated literal.")
            output[-1 - written] = compressed[-1 - read]
            read += 1
            written += 1

    return compressed_file[:passthrough_size] + bytes(output) + appended


def _overlay_entry_offset(rom: bytes, overlay_id: int) -> int:
    table_offset, table_size = struct.unpack_from("<II", rom, 0x50)
    if table_size % 32 or table_offset + table_size > len(rom):
        raise ValueError("Seed ROM has an invalid ARM9 overlay table.")
    for entry_offset in range(table_offset, table_offset + table_size, 32):
        if struct.unpack_from("<I", rom, entry_offset)[0] == overlay_id:
            return entry_offset
    raise ValueError(f"Seed ROM has no ARM9 overlay {overlay_id}.")


def patch_level_randomization(
    rom: bytes,
    slot_data: Mapping[str, Any],
) -> bytes:
    """Write the slot-to-course mapping into the decompressed world-map overlay."""
    mode = int(slot_data.get("level_randomization", LEVEL_RANDOMIZATION_OFF))
    if mode == LEVEL_RANDOMIZATION_OFF:
        return rom
    mapping = mapping_from_slot_data(slot_data)

    overlay_entry = _overlay_entry_offset(rom, OVERLAY_ID)
    ram_address, ram_size = struct.unpack_from("<II", rom, overlay_entry + 4)
    file_id = struct.unpack_from("<I", rom, overlay_entry + 0x18)[0]
    if (ram_address, ram_size, file_id) != (
        OVERLAY_RAM_ADDRESS,
        OVERLAY_RAM_SIZE,
        OVERLAY_FILE_ID,
    ):
        raise ValueError(
            "Seed ROM Overlay 8 metadata does not match the supported USA A2DE revision."
        )

    fat_offset, fat_size = struct.unpack_from("<II", rom, 0x48)
    if (
        fat_size % 8
        or fat_offset + fat_size > len(rom)
        or file_id * 8 + 8 > fat_size
    ):
        raise ValueError("Seed ROM has an invalid NitroFS allocation table.")
    fat_entry = fat_offset + file_id * 8
    file_start, file_end = struct.unpack_from("<II", rom, fat_entry)
    if not (0 <= file_start <= file_end <= len(rom)):
        raise ValueError("Seed ROM Overlay 8 has an invalid FAT allocation.")
    overlay = bytearray(decompress_code_overlay(rom[file_start:file_end]))
    if len(overlay) != ram_size:
        raise ValueError(
            f"Seed ROM Overlay 8 expands to {len(overlay)} bytes; expected {ram_size}."
        )

    for slot_name, offset in LEVEL_NODE_OFFSET_BY_NAME.items():
        expected = LEVEL_AREA_ID_BY_NAME[slot_name]
        if overlay[offset] != expected:
            raise ValueError(
                f"Overlay 8 node {slot_name} is not vanilla at 0x{offset:X}: "
                f"expected {expected}, found {overlay[offset]}."
            )
        overlay[offset] = LEVEL_AREA_ID_BY_NAME[mapping[slot_name]]

    file_ranges = [
        struct.unpack_from("<II", rom, entry)
        for entry in range(fat_offset, fat_offset + fat_size, 8)
    ]
    if any(start > end or end > len(rom) for start, end in file_ranges):
        raise ValueError("Seed ROM has an invalid NitroFS file allocation.")
    file_ends = [end for _start, end in file_ranges]
    new_start = (max(file_ends) + 3) & ~3
    new_end = new_start + len(overlay)
    if new_end > PATCH_MARKER_ROM_OFFSET:
        raise ValueError("Decompressed Overlay 8 does not fit before the reserved patch marker.")

    patched = bytearray(rom)
    patched[new_start:new_end] = overlay
    struct.pack_into("<II", patched, fat_entry, new_start, new_end)
    # Clear compressed-size and flag fields so the overlay loader reads raw bytes.
    struct.pack_into("<I", patched, overlay_entry + 0x1C, 0)
    return bytes(patched)


def patch_level_randomization_from_json(rom: bytes, config_data: bytes) -> bytes:
    payload = json.loads(config_data.decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Patch configuration root must be an object.")
    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Patch configuration does not contain an options mapping.")
    slot_data = {
        **options,
        "level_randomization": payload.get("level_randomization", 0),
        "level_randomization_version": payload.get("level_randomization_version"),
        "level_mapping": payload.get("level_mapping"),
        "level_mapping_digest": payload.get("level_mapping_digest"),
    }
    return patch_level_randomization(rom, slot_data)


__all__ = [
    "OVERLAY_FILE_ID",
    "OVERLAY_ID",
    "OVERLAY_RAM_ADDRESS",
    "OVERLAY_RAM_SIZE",
    "decompress_code_overlay",
    "patch_level_randomization",
    "patch_level_randomization_from_json",
]
