"""ROM-side music patching for NSMBDS USA A2DE."""

from __future__ import annotations

import json
import re
import struct
from typing import Any, Mapping

from ..data.music import (
    BAH_SEQUENCE_IDS,
    LEVEL_CONTEXT_BY_NAME,
    MUSIC_MAPPING_VERSION,
    MUSIC_RANDOMIZATION_OFF,
    SAFE_LEVEL_SEQUENCE_IDS,
    SAFE_MIXED_LEVEL_SEQUENCE_IDS,
    WORLD_MAP_MUSIC_CONTEXTS,
    validate_music_mapping,
)
from ..data.patch_protocol import PATCH_MARKER_ROM_OFFSET
from .level_randomization import (
    OVERLAY_FILE_ID,
    OVERLAY_ID,
    OVERLAY_RAM_ADDRESS,
    OVERLAY_RAM_SIZE,
    _overlay_entry_offset,
    decompress_code_overlay,
)


WORLD_MAP_MUSIC_TABLE_OFFSET = 0x1A22C
TOAD_HOUSE_SEQUENCE_ID = 29
NO_SEQUENCE_SENTINEL = 112
WORLD_MAP_MUSIC_TABLE_TAIL = (TOAD_HOUSE_SEQUENCE_ID, NO_SEQUENCE_SENTINEL)
_COURSE_FILE_PATTERN = re.compile(r"^course/([A-H]\d{2})_(\d+)\.bin$")


def _fat(rom: bytes) -> tuple[int, int]:
    fat_offset, fat_size = struct.unpack_from("<II", rom, 0x48)
    if fat_size % 8 or fat_offset + fat_size > len(rom):
        raise ValueError("Seed ROM has an invalid NitroFS allocation table.")
    return fat_offset, fat_size


def _nitrofs_paths(rom: bytes) -> dict[str, int]:
    """Return file paths from the standard Nintendo DS filename table."""
    fnt_offset, fnt_size = struct.unpack_from("<II", rom, 0x40)
    if fnt_size < 8 or fnt_offset + fnt_size > len(rom):
        raise ValueError("Seed ROM has an invalid NitroFS filename table.")
    fnt = rom[fnt_offset:fnt_offset + fnt_size]
    directory_count = struct.unpack_from("<H", fnt, 6)[0]
    if not directory_count or directory_count * 8 > len(fnt):
        raise ValueError("Seed ROM has an invalid NitroFS directory table.")

    paths: dict[str, int] = {}
    active: set[int] = set()

    def visit(directory_id: int, prefix: str) -> None:
        directory_index = directory_id - 0xF000
        if directory_id in active or not 0 <= directory_index < directory_count:
            raise ValueError("Seed ROM has an invalid NitroFS directory reference.")
        entry_offset = directory_index * 8
        subtable_offset, first_file_id = struct.unpack_from("<IH", fnt, entry_offset)
        if subtable_offset >= len(fnt):
            raise ValueError("Seed ROM has an invalid NitroFS directory subtable.")
        active.add(directory_id)
        cursor = subtable_offset
        file_id = first_file_id
        while True:
            if cursor >= len(fnt):
                raise ValueError("Seed ROM has an unterminated NitroFS directory.")
            descriptor = fnt[cursor]
            cursor += 1
            if descriptor == 0:
                break
            name_length = descriptor & 0x7F
            if not name_length or cursor + name_length > len(fnt):
                raise ValueError("Seed ROM has an invalid NitroFS filename.")
            name = fnt[cursor:cursor + name_length].decode("ascii")
            cursor += name_length
            if descriptor & 0x80:
                if cursor + 2 > len(fnt):
                    raise ValueError("Seed ROM has a truncated NitroFS directory entry.")
                child_id = struct.unpack_from("<H", fnt, cursor)[0]
                cursor += 2
                visit(child_id, f"{prefix}{name}/")
            else:
                paths[f"{prefix}{name}"] = file_id
                file_id += 1
        active.remove(directory_id)

    visit(0xF000, "")
    return paths


def patch_course_music_data(course_data: bytes, replacement_sequence_id: int) -> tuple[bytes, int]:
    """Replace compatible BGM bytes in block 7 views without changing file size."""
    if replacement_sequence_id not in SAFE_MIXED_LEVEL_SEQUENCE_IDS:
        raise ValueError(f"Sequence {replacement_sequence_id} is not safe for levels.")
    if len(course_data) < 14 * 8:
        raise ValueError("Course data is too short to contain its block table.")
    view_offset, view_size = struct.unpack_from("<II", course_data, 7 * 8)
    if view_size % 16 or view_offset + view_size > len(course_data):
        raise ValueError("Course data has an invalid view block.")

    patched = bytearray(course_data)
    replaced = 0
    for view_offset_in_file in range(view_offset, view_offset + view_size, 16):
        music_offset = view_offset_in_file + 10
        if (
            patched[music_offset] in SAFE_LEVEL_SEQUENCE_IDS
            and (patched[music_offset] in BAH_SEQUENCE_IDS)
            == (replacement_sequence_id in BAH_SEQUENCE_IDS)
        ):
            patched[music_offset] = replacement_sequence_id
            replaced += 1
    return bytes(patched), replaced


def _patch_level_music(rom: bytes, mapping: Mapping[str, int]) -> bytes:
    paths = _nitrofs_paths(rom)
    fat_offset, fat_size = _fat(rom)
    course_files: dict[str, list[tuple[int, int]]] = {}
    for path, file_id in paths.items():
        match = _COURSE_FILE_PATTERN.match(path)
        if match:
            course_files.setdefault(match.group(1), []).append((int(match.group(2)), file_id))

    patched = bytearray(rom)
    file_count = fat_size // 8
    for level_name, replacement in mapping.items():
        context = LEVEL_CONTEXT_BY_NAME[level_name]
        files = sorted(course_files.get(context.course_prefix, ()))
        if not files:
            raise ValueError(f"Seed ROM has no course data for {level_name}.")
        replaced = 0
        for _area, file_id in files:
            if file_id >= file_count:
                raise ValueError(f"Course file ID for {level_name} is outside the FAT.")
            file_start, file_end = struct.unpack_from("<II", patched, fat_offset + file_id * 8)
            if not 0 <= file_start <= file_end <= len(patched):
                raise ValueError(f"Course data for {level_name} has an invalid FAT allocation.")
            course, area_replaced = patch_course_music_data(
                bytes(patched[file_start:file_end]), replacement
            )
            patched[file_start:file_end] = course
            replaced += area_replaced
        if not replaced:
            raise ValueError(f"No safe level-music views were found for {level_name}.")
    return bytes(patched)


def patch_world_map_music_overlay(
    overlay_data: bytes,
    mapping: Mapping[str, int],
) -> bytes:
    """Patch only the first eight entries of Overlay 8's ten-entry music table."""
    table_end = WORLD_MAP_MUSIC_TABLE_OFFSET + 10 * 4
    if table_end > len(overlay_data):
        raise ValueError("Overlay 8 is too short to contain the world-map music table.")
    current = struct.unpack_from("<10I", overlay_data, WORLD_MAP_MUSIC_TABLE_OFFSET)
    expected = tuple(range(100, 108)) + WORLD_MAP_MUSIC_TABLE_TAIL
    if current != expected:
        raise ValueError(
            "Overlay 8 world-map music table does not match the supported USA A2DE revision."
        )
    patched = bytearray(overlay_data)
    for context in WORLD_MAP_MUSIC_CONTEXTS:
        struct.pack_into(
            "<I", patched, WORLD_MAP_MUSIC_TABLE_OFFSET + context.table_index * 4,
            mapping[context.name],
        )
    return bytes(patched)


def _patch_world_map_music(rom: bytes, mapping: Mapping[str, int]) -> bytes:
    overlay_entry = _overlay_entry_offset(rom, OVERLAY_ID)
    ram_address, ram_size = struct.unpack_from("<II", rom, overlay_entry + 4)
    file_id = struct.unpack_from("<I", rom, overlay_entry + 0x18)[0]
    if (ram_address, ram_size, file_id) != (
        OVERLAY_RAM_ADDRESS, OVERLAY_RAM_SIZE, OVERLAY_FILE_ID
    ):
        raise ValueError("Seed ROM Overlay 8 metadata does not match USA A2DE.")

    fat_offset, fat_size = _fat(rom)
    if file_id * 8 + 8 > fat_size:
        raise ValueError("Seed ROM Overlay 8 file ID is outside the FAT.")
    fat_entry = fat_offset + file_id * 8
    file_start, file_end = struct.unpack_from("<II", rom, fat_entry)
    if not 0 <= file_start <= file_end <= len(rom):
        raise ValueError("Seed ROM Overlay 8 has an invalid FAT allocation.")
    overlay = decompress_code_overlay(rom[file_start:file_end])
    if len(overlay) != ram_size:
        raise ValueError(f"Overlay 8 expands to {len(overlay)} bytes; expected {ram_size}.")
    overlay = patch_world_map_music_overlay(overlay, mapping)

    patched = bytearray(rom)
    if file_end - file_start == len(overlay):
        patched[file_start:file_end] = overlay
    else:
        file_ranges = [
            struct.unpack_from("<II", rom, entry)
            for entry in range(fat_offset, fat_offset + fat_size, 8)
        ]
        if any(start > end or end > len(rom) for start, end in file_ranges):
            raise ValueError("Seed ROM has an invalid NitroFS file allocation.")
        new_start = (max(end for _start, end in file_ranges) + 3) & ~3
        new_end = new_start + len(overlay)
        if new_end > PATCH_MARKER_ROM_OFFSET:
            raise ValueError("Decompressed Overlay 8 does not fit before the patch marker.")
        patched[new_start:new_end] = overlay
        struct.pack_into("<II", patched, fat_entry, new_start, new_end)
    struct.pack_into("<I", patched, overlay_entry + 0x1C, 0)
    return bytes(patched)


def patch_music_randomization(rom: bytes, slot_data: Mapping[str, Any]) -> bytes:
    mode = int(slot_data.get("music_randomization", MUSIC_RANDOMIZATION_OFF))
    if mode == MUSIC_RANDOMIZATION_OFF:
        return rom
    if int(slot_data.get("music_mapping_version", -1)) != MUSIC_MAPPING_VERSION:
        raise ValueError("Unsupported NSMBDS music mapping version.")
    raw_levels = slot_data.get("level_music_mapping")
    raw_maps = slot_data.get("world_map_music_mapping", {})
    if not isinstance(raw_levels, Mapping) or not isinstance(raw_maps, Mapping):
        raise ValueError("Patch configuration does not contain valid music mappings.")
    levels = {str(name): int(value) for name, value in raw_levels.items()}
    maps = {str(name): int(value) for name, value in raw_maps.items()}
    validate_music_mapping(mode, levels, maps)

    patched = _patch_level_music(rom, levels)
    if maps:
        patched = _patch_world_map_music(patched, maps)
    return patched


def patch_music_randomization_from_json(rom: bytes, config_data: bytes) -> bytes:
    payload = json.loads(config_data.decode("utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("Patch configuration root must be an object.")
    options = payload.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Patch configuration does not contain an options mapping.")
    return patch_music_randomization(rom, {
        **options,
        "music_mapping_version": payload.get("music_mapping_version"),
        "level_music_mapping": payload.get("level_music_mapping"),
        "world_map_music_mapping": payload.get("world_map_music_mapping", {}),
    })


__all__ = [
    "WORLD_MAP_MUSIC_TABLE_OFFSET", "patch_course_music_data",
    "patch_music_randomization", "patch_music_randomization_from_json",
    "patch_world_map_music_overlay",
]
