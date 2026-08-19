"""Per-seed Mario and Luigi palette patching for the clean A2DE ROM."""

from __future__ import annotations

import colorsys
import hashlib
import json
import random
import struct
from collections.abc import Mapping


PALETTE_VANILLA = 0
PALETTE_CRIMSON = 1
PALETTE_EMERALD = 2
PALETTE_SAPPHIRE = 3
PALETTE_PURPLE = 4
PALETTE_MONOCHROME = 5
PALETTE_RANDOM = 6
PALETTE_CRAZY_RANDOM = 7
PALETTE_PASTEL_ROSA = 8
PALETTE_GOLD = 9
PALETTE_SILVER = 10
PALETTE_PEACH = 11

PALETTE_NAMES = {
    PALETTE_VANILLA: "vanilla",
    PALETTE_CRIMSON: "crimson",
    PALETTE_EMERALD: "emerald",
    PALETTE_SAPPHIRE: "sapphire",
    PALETTE_PURPLE: "purple",
    PALETTE_MONOCHROME: "monochrome",
    PALETTE_RANDOM: "random",
    PALETTE_CRAZY_RANDOM: "crazy_random",
    PALETTE_PASTEL_ROSA: "pastel_rosa",
    PALETTE_GOLD: "gold",
    PALETTE_SILVER: "silver",
    PALETTE_PEACH: "peach",
}

FIXED_RANDOM_PALETTES = (
    PALETTE_CRIMSON,
    PALETTE_EMERALD,
    PALETTE_SAPPHIRE,
    PALETTE_PURPLE,
    PALETTE_MONOCHROME,
    PALETTE_PASTEL_ROSA,
    PALETTE_GOLD,
    PALETTE_SILVER,
    PALETTE_PEACH,
)

FIXED_RANDOM_PALETTES_BY_CHARACTER = {
    # Do not let Random silently choose the character's near-vanilla color.
    "mario": tuple(value for value in FIXED_RANDOM_PALETTES if value != PALETTE_CRIMSON),
    "luigi": tuple(value for value in FIXED_RANDOM_PALETTES if value != PALETTE_EMERALD),
}

PLAYER_MODEL_FILE_IDS = {
    "luigi": (
        1875,  # detached cap
        1876,  # defeated head with cap
        1877,  # defeated head without cap
        1878,  # head with cap
        1879,  # head without cap
        1881,  # body; contains the power-up palette banks
    ),
    "mario": (
        1874,  # detached cap
        1882,  # defeated head with cap
        1883,  # defeated head without cap
        1884,  # head with cap
        1885,  # head without cap
        1887,  # body; contains the power-up palette banks
    ),
}

_TARGET_HUES = {
    PALETTE_CRIMSON: 0.0,
    PALETTE_EMERALD: 0.34,
    PALETTE_SAPPHIRE: 0.62,
    PALETTE_PURPLE: 0.79,
    PALETTE_PASTEL_ROSA: 0.92,
}


def _stable_seed(*parts: object) -> int:
    material = "\0".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "little")


def resolve_palette(value: int, seed_name: str, player: int, character: str) -> int:
    """Resolve the random choice once for a player and character."""
    if value != PALETTE_RANDOM:
        return value
    rng = random.Random(_stable_seed(seed_name, player, character, "palette"))
    return rng.choice(FIXED_RANDOM_PALETTES_BY_CHARACTER.get(character, FIXED_RANDOM_PALETTES))


def _lz10_decompress(data: bytes) -> bytes:
    if len(data) < 4 or data[0] != 0x10:
        raise ValueError("Player model is not LZ10-compressed.")
    output_size = int.from_bytes(data[:4], "little") >> 8
    output = bytearray()
    source = 4
    while len(output) < output_size:
        if source >= len(data):
            raise ValueError("Truncated LZ10 stream.")
        flags = data[source]
        source += 1
        for bit_index in range(8):
            if len(output) >= output_size:
                break
            if flags & (0x80 >> bit_index):
                if source + 2 > len(data):
                    raise ValueError("Truncated LZ10 back-reference.")
                value = int.from_bytes(data[source:source + 2], "big")
                source += 2
                length = (value >> 12) + 3
                displacement = (value & 0xFFF) + 1
                if displacement > len(output):
                    raise ValueError("Invalid LZ10 back-reference.")
                for _ in range(length):
                    output.append(output[-displacement])
                    if len(output) >= output_size:
                        break
            else:
                if source >= len(data):
                    raise ValueError("Truncated LZ10 literal.")
                output.append(data[source])
                source += 1
    return bytes(output)


def _lz10_compress(data: bytes) -> bytes:
    """Create a standard greedy LZ10 stream accepted by the DS loader."""

    def find_match(position: int) -> tuple[int, int]:
        window_start = max(0, position - 0x1000)
        maximum = min(18, len(data) - position)
        best_position = 0
        best_length = 0
        lower, upper = 3, maximum
        while lower <= upper:
            length = (lower + upper) // 2
            match_position = data.find(data[position:position + length], window_start, position)
            if match_position < 0:
                upper = length - 1
            else:
                best_position, best_length = match_position, length
                lower = length + 1
        return best_position, best_length

    payload = bytearray()
    position = 0
    while position < len(data):
        flag_offset = len(payload)
        payload.append(0)
        flags = 0
        for bit_index in range(8):
            if position >= len(data):
                break
            match_position, match_length = find_match(position)
            if match_length >= 3:
                displacement = position - match_position - 1
                flags |= 0x80 >> bit_index
                payload.append(((match_length - 3) << 4) | (displacement >> 8))
                payload.append(displacement & 0xFF)
                position += match_length
            else:
                payload.append(data[position])
                position += 1
        payload[flag_offset] = flags
    return ((len(data) << 8) | 0x10).to_bytes(4, "little") + bytes(payload)


def _decode_rgb555(color: int) -> tuple[float, float, float]:
    return (color & 0x1F) / 31.0, ((color >> 5) & 0x1F) / 31.0, ((color >> 10) & 0x1F) / 31.0


def _encode_rgb555(red: float, green: float, blue: float, high_bit: int = 0) -> int:
    red_5 = max(0, min(31, round(red * 31)))
    green_5 = max(0, min(31, round(green * 31)))
    blue_5 = max(0, min(31, round(blue * 31)))
    return high_bit | red_5 | (green_5 << 5) | (blue_5 << 10)


def _is_primary_clothing(character: str, hue: float, saturation: float, value: float) -> bool:
    if value < 0.12:
        return False
    if character == "mario":
        return saturation >= 0.35 and (hue <= 0.045 or hue >= 0.97)
    return saturation >= 0.30 and 0.20 <= hue <= 0.47


def _apply_preset(
    red: float,
    green: float,
    blue: float,
    palette: int,
    neon_hue: float | None,
    character: str,
) -> tuple[float, float, float]:
    _hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    if palette == PALETTE_MONOCHROME:
        return colorsys.hsv_to_rgb(0.0, 0.0, value)
    if palette == PALETTE_PASTEL_ROSA:
        if character == "luigi":
            return colorsys.hsv_to_rgb(
                0.95,
                0.46,
                0.68 + value * 0.32,
            )
        return colorsys.hsv_to_rgb(0.95, 0.4, 0.55 + value * 0.45)
    if palette == PALETTE_PEACH:
        return (255 / 255.0, 131 / 255.0, 172 / 255.0)
    if palette == PALETTE_SILVER:
        silver_ramp = (
            (0.00, (2, 3, 4)),      # Deep cool shadow
            (0.25, (7, 8, 10)),     # Dark silver
            (0.50, (15, 16, 18)),   # Main silver
            (0.75, (23, 24, 25)),   # Bright silver
            (1.00, (31, 31, 30)),   # Metallic highlight
        )

        for index in range(len(silver_ramp) - 1):
            start_value, start_rgb = silver_ramp[index]
            end_value, end_rgb = silver_ramp[index + 1]

            if value <= end_value:
                span = end_value - start_value
                amount = (value - start_value) / span
                amount = max(0.0, min(1.0, amount))

                red_5 = start_rgb[0] + (
                    end_rgb[0] - start_rgb[0]
                ) * amount

                green_5 = start_rgb[1] + (
                    end_rgb[1] - start_rgb[1]
                ) * amount

                blue_5 = start_rgb[2] + (
                    end_rgb[2] - start_rgb[2]
                ) * amount

                return (
                    red_5 / 31.0,
                    green_5 / 31.0,
                    blue_5 / 31.0,
                )

        return tuple(
            channel / 31.0
            for channel in silver_ramp[-1][1]
        )
    if palette == PALETTE_GOLD:
        gold_ramp = (
            (0.00, (3, 1, 0)),    # Deep brown shadow
            (0.25, (9, 4, 0)),    # Dark bronze
            (0.50, (19, 10, 1)),  # Main gold
            (0.75, (27, 18, 4)),  # Bright gold
            (1.00, (31, 27, 13)), # Pale metallic highlight
        )

        for index in range(len(gold_ramp) - 1):
            start_value, start_rgb = gold_ramp[index]
            end_value, end_rgb = gold_ramp[index + 1]

            if value <= end_value:
                span = end_value - start_value
                amount = (value - start_value) / span
                amount = max(0.0, min(1.0, amount))

                red_5 = start_rgb[0] + (end_rgb[0] - start_rgb[0]) * amount
                green_5 = start_rgb[1] + (end_rgb[1] - start_rgb[1]) * amount
                blue_5 = start_rgb[2] + (end_rgb[2] - start_rgb[2]) * amount

                return (
                    red_5 / 31.0,
                    green_5 / 31.0,
                    blue_5 / 31.0,
                )

        return tuple(channel / 31.0 for channel in gold_ramp[-1][1])
    target_hue = _TARGET_HUES.get(palette)
    if target_hue is None:
        return red, green, blue
    if palette == PALETTE_CRIMSON:
        value = max(0.10, value * 0.72)
        saturation = max(0.72, saturation)
    else:
        saturation = max(0.55, saturation)
    return colorsys.hsv_to_rgb(target_hue, saturation, value)


def _recolor_color(
    color: int,
    character: str,
    palette: int,
    crazy_rng: random.Random,
    force_primary: bool = False,
    neon_hue: float | None = None,
) -> int:
    high_bit = color & 0x8000
    red, green, blue = _decode_rgb555(color)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)

    if palette == PALETTE_CRAZY_RANDOM:
        if value < 0.08:
            return color
        hue = crazy_rng.random()
        saturation = 0.70 + crazy_rng.random() * 0.30
        red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
        return _encode_rgb555(red, green, blue, high_bit)

    if not force_primary and not _is_primary_clothing(character, hue, saturation, value):
        return color
    red, green, blue = _apply_preset(red, green, blue, palette, neon_hue, character)
    return _encode_rgb555(red, green, blue, high_bit)


def _tex0_palette_ranges(data: bytes, tex_offset: int) -> list[tuple[int, int]]:
    """Return the individual named palette ranges stored in a TEX0 block."""
    tex_size = struct.unpack_from("<I", data, tex_offset + 4)[0]
    palette_size = struct.unpack_from("<H", data, tex_offset + 0x30)[0] * 8
    palette_info_offset = struct.unpack_from("<I", data, tex_offset + 0x34)[0]
    palette_data_offset = struct.unpack_from("<I", data, tex_offset + 0x38)[0]
    info_start = tex_offset + palette_info_offset
    data_start = tex_offset + palette_data_offset
    data_end = data_start + palette_size
    if palette_size == 0 or data_end > tex_offset + tex_size or data_end > len(data):
        raise ValueError("Player TEX0 palette bounds are invalid.")
    if info_start + 16 > len(data):
        raise ValueError("Player TEX0 palette metadata is truncated.")
    count = data[info_start + 1]
    entry_start = info_start + 16 + count * 4
    if count == 0 or entry_start + count * 4 > len(data):
        raise ValueError("Player TEX0 palette metadata is invalid.")
    starts = []
    for index in range(count):
        relative = struct.unpack_from("<H", data, entry_start + index * 4)[0] * 8
        starts.append(data_start + relative)
    ordered = sorted(set(starts + [data_end]))
    ranges = []
    for start in starts:
        end_index = ordered.index(start) + 1
        if start < data_start or end_index >= len(ordered):
            raise ValueError("Player TEX0 named palette offset is invalid.")
        ranges.append((start, ordered[end_index]))
    return ranges


def recolor_bmd0(
    data: bytes,
    character: str,
    palette: int,
    seed: int,
    neon_hue: float | None = None,
) -> tuple[bytes, int]:
    """Recolor the TEX0 palette block embedded in one BMD0 model."""
    if data[:4] != b"BMD0" or len(data) < 0x14:
        raise ValueError("Player model does not contain a valid BMD0 header.")
    block_count = struct.unpack_from("<H", data, 0x0E)[0]
    tex_offset = None
    for index in range(block_count):
        block_offset = struct.unpack_from("<I", data, 0x10 + index * 4)[0]
        if data[block_offset:block_offset + 4] == b"TEX0":
            tex_offset = block_offset
            break
    if tex_offset is None:
        raise ValueError("Player BMD0 does not contain a TEX0 block.")

    output = bytearray(data)
    crazy_rng = random.Random(seed)
    changed = 0
    for palette_start, palette_end in _tex0_palette_ranges(data, tex_offset):
        color_count = (palette_end - palette_start) // 2
        banked = color_count >= 512 and color_count % 256 == 0
        primary_indices: set[int] = set()
        if banked and palette != PALETTE_CRAZY_RANDOM:
            for index in range(256):
                color = struct.unpack_from("<H", data, palette_start + index * 2)[0]
                red, green, blue = _decode_rgb555(color)
                hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
                if _is_primary_clothing(character, hue, saturation, value):
                    primary_indices.add(index)
        for index in range(color_count):
            offset = palette_start + index * 2
            original = struct.unpack_from("<H", output, offset)[0]
            replacement = _recolor_color(
                original,
                character,
                palette,
                crazy_rng,
                force_primary=banked and index % 256 in primary_indices,
                neon_hue=neon_hue,
            )
            if replacement != original:
                struct.pack_into("<H", output, offset, replacement)
                changed += 1
    return bytes(output), changed


def _fat_entry(rom: bytes | bytearray, fat_offset: int, file_id: int) -> tuple[int, int]:
    entry_offset = fat_offset + file_id * 8
    return struct.unpack_from("<II", rom, entry_offset)


def patch_player_palettes(rom: bytes, config: Mapping[str, object]) -> bytes:
    """Append recolored models and repoint their NitroFS FAT entries."""
    options = config.get("options", {})
    if not isinstance(options, Mapping):
        raise ValueError("Patch configuration does not contain an options mapping.")
    seed_name = str(config.get("seed_name", ""))
    player = int(config.get("player", 0))
    requested = {
        "mario": int(options.get("mario_palette", PALETTE_VANILLA)),
        "luigi": int(options.get("luigi_palette", PALETTE_VANILLA)),
    }
    resolved = {
        character: resolve_palette(value, seed_name, player, character)
        for character, value in requested.items()
    }
    if all(value == PALETTE_VANILLA for value in resolved.values()):
        return rom

    output = bytearray(rom)
    fat_offset, fat_size = struct.unpack_from("<II", output, 0x48)
    file_count = fat_size // 8
    if max(max(ids) for ids in PLAYER_MODEL_FILE_IDS.values()) >= file_count:
        raise ValueError("The validated ROM has an unexpected NitroFS file table.")

    used_end = max(_fat_entry(output, fat_offset, file_id)[1] for file_id in range(file_count))
    cursor = (used_end + 0x1FF) & ~0x1FF
    for character in ("mario", "luigi"):
        palette = resolved[character]
        if palette == PALETTE_VANILLA:
            continue
        for file_id in PLAYER_MODEL_FILE_IDS[character]:
            old_start, old_end = _fat_entry(output, fat_offset, file_id)
            raw_model = _lz10_decompress(bytes(output[old_start:old_end]))
            recolored, changed = recolor_bmd0(
                raw_model,
                character,
                palette,
                _stable_seed(seed_name, player, character, file_id, "crazy"),
                None,
            )
            if changed == 0:
                continue
            compressed = _lz10_compress(recolored)
            new_end = cursor + len(compressed)
            if new_end > len(output):
                output.extend(b"\x00" * (new_end - len(output)))
            output[cursor:new_end] = compressed
            struct.pack_into("<II", output, fat_offset + file_id * 8, cursor, new_end)
            cursor = (new_end + 3) & ~3
    return bytes(output)


def patch_player_palettes_from_json(rom: bytes, config_data: bytes) -> bytes:
    config = json.loads(config_data.decode("utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Patch configuration root must be an object.")
    return patch_player_palettes(rom, config)


__all__ = [
    "PALETTE_NAMES",
    "PALETTE_VANILLA",
    "PALETTE_CRIMSON",
    "PALETTE_EMERALD",
    "PALETTE_SAPPHIRE",
    "PALETTE_PURPLE",
    "PALETTE_MONOCHROME",
    "PALETTE_RANDOM",
    "PALETTE_CRAZY_RANDOM",
    "PALETTE_PASTEL_ROSA",
    "PALETTE_GOLD",
    "PALETTE_SILVER",
    "PALETTE_PEACH",
    "PLAYER_MODEL_FILE_IDS",
    "patch_player_palettes",
    "patch_player_palettes_from_json",
    "recolor_bmd0",
    "resolve_palette",
]
