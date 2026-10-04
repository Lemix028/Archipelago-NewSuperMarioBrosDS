"""Apply a seed's gate price and requirement messages to the native ROM."""

from __future__ import annotations

import json
import struct
from typing import Mapping

from ..data.patch_protocol import PATCH_MARKER, PATCH_MARKER_ROM_OFFSET
from ..data.star_coin_gates import star_coin_gate_gap
from ..data.star_coin_gate_messages import (
    GATE_GAP_CHECK_OFFSET, GATE_GAP_CHECK_WORD, GATE_HOOK_CAVE,
    GATE_MESSAGE_BASE, GATE_MESSAGE_COUNT, GATE_PRICE_OFFSET, GATE_PRICE_WORD,
    gate_tier_messages,
)
from .level_randomization import (
    OVERLAY_ID, OVERLAY_FILE_ID, OVERLAY_RAM_ADDRESS, OVERLAY_RAM_SIZE,
    _overlay_entry_offset, decompress_code_overlay,
)
from .music import _fat, _nitrofs_paths


def patch_gate_overlay(data: bytes, ram_address: int, gap: int) -> bytes:
    """Patch the handshake and the actor price used for checking and spending."""
    star_coin_gate_gap({"star_coin_gate_gap": gap})
    patched = bytearray(data)
    for relative, expected in (
        (GATE_GAP_CHECK_OFFSET, GATE_GAP_CHECK_WORD),
        (GATE_PRICE_OFFSET, GATE_PRICE_WORD),
    ):
        offset = GATE_HOOK_CAVE + relative - ram_address
        if offset < 0 or offset + 4 > len(patched):
            raise ValueError("Seed ROM gate patch is outside Overlay 8.")
        if struct.unpack_from("<I", patched, offset)[0] != expected:
            raise ValueError("Seed ROM does not contain the supported gate-price hook.")
        struct.pack_into("<I", patched, offset, (expected & ~0xFF) | gap)
    return bytes(patched)


def patch_gate_messages(data: bytes, gap: int) -> bytes:
    """Append UTF-16 text and repoint INF1 entries, preserving native escapes."""
    texts = gate_tier_messages(gap)
    if len(data) < 32 or data[:8] != b"MESGbmg1" or data[16] != 2:
        raise ValueError("Seed ROM has an unsupported course.bmg encoding.")
    count = struct.unpack_from("<I", data, 12)[0]
    if not 2 <= count <= 16:
        raise ValueError("Seed ROM has an invalid course.bmg section count.")
    sections = []
    cursor = 32
    for _ in range(count):
        if cursor + 8 > len(data):
            raise ValueError("Seed ROM has truncated course.bmg sections.")
        size = struct.unpack_from("<I", data, cursor + 4)[0]
        if size < 8 or cursor + size > len(data):
            raise ValueError("Seed ROM has invalid course.bmg section sizes.")
        sections.append(bytearray(data[cursor:cursor + size]))
        cursor += size
    infos = [section for section in sections if section[:4] == b"INF1"]
    strings = [section for section in sections if section[:4] == b"DAT1"]
    if len(infos) != 1 or len(strings) != 1 or len(infos[0]) < 16:
        raise ValueError("Seed ROM has invalid course.bmg message sections.")
    info, string_section = infos[0], strings[0]
    message_count, entry_size = struct.unpack_from("<HH", info, 8)
    if (message_count != GATE_MESSAGE_BASE + GATE_MESSAGE_COUNT or entry_size < 4
            or 16 + message_count * entry_size > len(info)):
        raise ValueError("Seed ROM has an unsupported gate-message catalog.")
    if gap == 5:
        return data
    # Original DAT1 stays intact, including the price escapes used by messages
    # 6 and 10 and any flow/script references. Only the 96 AP text offsets move.
    for index, text in enumerate(texts, GATE_MESSAGE_BASE):
        struct.pack_into("<I", info, 16 + index * entry_size, len(string_section) - 8)
        string_section.extend(text.encode("utf-16le") + b"\x00\x00")
    string_section.extend(bytes((-len(string_section)) % 32))
    struct.pack_into("<I", string_section, 4, len(string_section))
    patched = bytearray(data[:32])
    for section in sections:
        patched.extend(section)
    struct.pack_into("<I", patched, 8, len(patched))
    return bytes(patched)


def patch_star_coin_gates(rom: bytes, options: Mapping[str, object]) -> bytes:
    gap = star_coin_gate_gap(options)
    if rom[PATCH_MARKER_ROM_OFFSET:PATCH_MARKER_ROM_OFFSET + len(PATCH_MARKER)] != PATCH_MARKER:
        raise ValueError("Seed ROM is missing the current patch-protocol marker.")
    fat_offset, fat_size = _fat(rom)
    paths = _nitrofs_paths(rom)
    file_id = paths.get("script/course.bmg")
    if file_id is None:
        raise ValueError("Seed ROM has no course.bmg gate messages.")
    entry = _overlay_entry_offset(rom, OVERLAY_ID)
    ram_address, ram_size = struct.unpack_from("<II", rom, entry + 4)
    overlay_file = struct.unpack_from("<I", rom, entry + 0x18)[0]
    if (ram_address, ram_size, overlay_file) != (OVERLAY_RAM_ADDRESS, OVERLAY_RAM_SIZE, OVERLAY_FILE_ID):
        raise ValueError("Seed ROM Overlay 8 metadata does not match USA A2DE.")
    ranges = [struct.unpack_from("<II", rom, offset)
              for offset in range(fat_offset, fat_offset + fat_size, 8)]
    if (max(file_id, overlay_file) >= len(ranges)
            or any(start > end or end > PATCH_MARKER_ROM_OFFSET for start, end in ranges)):
        raise ValueError("Seed ROM has invalid NitroFS file allocations.")
    start, end = ranges[overlay_file]
    overlay = decompress_code_overlay(rom[start:end])
    if len(overlay) != ram_size:
        raise ValueError("Seed ROM Overlay 8 has an invalid decompressed size.")
    patched_overlay = patch_gate_overlay(overlay, ram_address, gap)
    start, end = ranges[file_id]
    patched_messages = patch_gate_messages(rom[start:end], gap)
    if gap == 5:
        return rom  # The native delta already contains the default price/text.
    patched = bytearray(rom)
    for target, payload in ((overlay_file, patched_overlay), (file_id, patched_messages)):
        start, end = ranges[target]
        if len(payload) > end - start:
            start = (max(end for _start, end in ranges) + 3) & ~3
        end = start + len(payload)
        if end > PATCH_MARKER_ROM_OFFSET:
            raise ValueError("Gate price/text patch overlaps the reserved ROM marker.")
        patched[start:end] = payload
        ranges[target] = start, end
        struct.pack_into("<II", patched, fat_offset + target * 8, start, end)
    # The modified executable is stored uncompressed, without the retail hash.
    struct.pack_into("<I", patched, entry + 0x1C, 0)
    return bytes(patched)


def patch_star_coin_gates_from_json(rom: bytes, config: bytes) -> bytes:
    payload = json.loads(config)
    options = payload.get("options", {})
    if not isinstance(options, dict):
        raise ValueError("Patch configuration has no valid gate options.")
    return patch_star_coin_gates(rom, options)
