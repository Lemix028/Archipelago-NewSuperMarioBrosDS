"""Deterministic level secondary-screen background randomization."""

from __future__ import annotations

import hashlib
import json
import random
import struct
from collections.abc import Mapping


SECONDARY_SCREEN_VANILLA = 0
SECONDARY_SCREEN_RANDOMIZED = 1
SECONDARY_SCREEN_WHITE_BRICKS = 2
SECONDARY_SCREEN_STAR_PATTERN = 3
SECONDARY_SCREEN_BLUE_BRICKS = 4
SECONDARY_SCREEN_MARIO_SILHOUETTE = 5
SECONDARY_SCREEN_CLASSIC_OVERWORLD = 6

# The five 32x32 screen maps used as the in-level lower-screen wallpaper.
# They all use the shared d_2d_UI_O_1P_game_in_b_d tile graphics.
SECONDARY_SCREEN_BACKGROUND_FILE_IDS = (2008, 2009, 2010, 2011, 2012)

SECONDARY_SCREEN_FIXED_FILE_IDS = {
    SECONDARY_SCREEN_WHITE_BRICKS: 2008,
    SECONDARY_SCREEN_STAR_PATTERN: 2009,
    SECONDARY_SCREEN_BLUE_BRICKS: 2010,
    SECONDARY_SCREEN_MARIO_SILHOUETTE: 2011,
    SECONDARY_SCREEN_CLASSIC_OVERWORLD: 2012,
}


def _stable_seed(*parts: object) -> int:
    material = "\0".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "little")


def resolve_secondary_screen_order(seed_name: str, player: int) -> tuple[int, ...]:
    """Return a stable derangement so every vanilla wallpaper visibly changes."""
    original = SECONDARY_SCREEN_BACKGROUND_FILE_IDS
    randomized = list(original)
    rng = random.Random(_stable_seed(seed_name, player, "secondary-screen-background"))
    while True:
        rng.shuffle(randomized)
        if all(source != target for target, source in zip(original, randomized)):
            return tuple(randomized)


def resolve_secondary_screen_sources(mode: int, seed_name: str, player: int) -> tuple[int, ...]:
    """Resolve the source wallpaper for each of the five target slots."""
    if mode == SECONDARY_SCREEN_RANDOMIZED:
        return resolve_secondary_screen_order(seed_name, player)
    source_id = SECONDARY_SCREEN_FIXED_FILE_IDS.get(mode)
    if source_id is None:
        raise ValueError(f"Unknown secondary-screen background mode: {mode}")
    return (source_id,) * len(SECONDARY_SCREEN_BACKGROUND_FILE_IDS)


def _fat_entry(rom: bytes | bytearray, fat_offset: int, file_id: int) -> tuple[int, int]:
    return struct.unpack_from("<II", rom, fat_offset + file_id * 8)


def patch_secondary_screen_backgrounds(rom: bytes, config: Mapping[str, object]) -> bytes:
    """Copy and repoint the five compatible vanilla lower-screen wallpapers."""
    options = config.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Patch configuration does not contain an options mapping.")
    mode = int(options.get("secondary_screen_background", SECONDARY_SCREEN_VANILLA))
    if mode == SECONDARY_SCREEN_VANILLA:
        return rom
    source_order = resolve_secondary_screen_sources(
        mode,
        str(config.get("seed_name", "")),
        int(config.get("player", 0)),
    )

    output = bytearray(rom)
    fat_offset, fat_size = struct.unpack_from("<II", output, 0x48)
    file_count = fat_size // 8
    if max(SECONDARY_SCREEN_BACKGROUND_FILE_IDS) >= file_count:
        raise ValueError("The validated ROM has an unexpected NitroFS file table.")

    source_payloads = {
        file_id: bytes(output[start:end])
        for file_id in SECONDARY_SCREEN_BACKGROUND_FILE_IDS
        for start, end in (_fat_entry(output, fat_offset, file_id),)
        if 0 <= start < end <= len(output)
    }
    if len(source_payloads) != len(SECONDARY_SCREEN_BACKGROUND_FILE_IDS):
        raise ValueError("A secondary-screen background FAT entry is invalid.")

    used_end = max(
        _fat_entry(output, fat_offset, file_id)[1]
        for file_id in range(file_count)
    )
    # NitroFS assets in the retail ROM begin on 0x200-byte boundaries. Keep
    # the first copied asset equally aligned; subsequent FAT ranges only need
    # word alignment, matching the existing player-palette patcher.
    cursor = (used_end + 0x1FF) & ~0x1FF
    for target_id, source_id in zip(
        SECONDARY_SCREEN_BACKGROUND_FILE_IDS,
        source_order,
    ):
        payload = source_payloads[source_id]
        new_end = cursor + len(payload)
        if new_end > len(output):
            output.extend(b"\x00" * (new_end - len(output)))
        output[cursor:new_end] = payload
        struct.pack_into(
            "<II",
            output,
            fat_offset + target_id * 8,
            cursor,
            new_end,
        )
        cursor = (new_end + 3) & ~3
    return bytes(output)


def patch_secondary_screen_backgrounds_from_json(rom: bytes, config_data: bytes) -> bytes:
    config = json.loads(config_data.decode("utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Patch configuration root must be an object.")
    return patch_secondary_screen_backgrounds(rom, config)


__all__ = [
    "SECONDARY_SCREEN_BACKGROUND_FILE_IDS",
    "SECONDARY_SCREEN_BLUE_BRICKS",
    "SECONDARY_SCREEN_CLASSIC_OVERWORLD",
    "SECONDARY_SCREEN_FIXED_FILE_IDS",
    "SECONDARY_SCREEN_MARIO_SILHOUETTE",
    "SECONDARY_SCREEN_RANDOMIZED",
    "SECONDARY_SCREEN_STAR_PATTERN",
    "SECONDARY_SCREEN_VANILLA",
    "SECONDARY_SCREEN_WHITE_BRICKS",
    "patch_secondary_screen_backgrounds",
    "patch_secondary_screen_backgrounds_from_json",
    "resolve_secondary_screen_order",
    "resolve_secondary_screen_sources",
]
