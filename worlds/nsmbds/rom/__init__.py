"""Archipelago patch-file support and ROM modification package for NSMBDS USA A2DE."""

from __future__ import annotations

import hashlib
import importlib.resources
import json
from pathlib import Path
from typing import TYPE_CHECKING

from worlds.Files import APPatchExtension, APProcedurePatch, APTokenMixin, APTokenTypes

from .palette import patch_player_palettes_from_json
from ..version import APWORLD_VERSION, DISPLAY_VERSION, RELEASE_CHANNEL

if TYPE_CHECKING:
    from .. import NSMBDSWorld


BASE_ROM_MD5 = "a2ddba012e5c3c2096d0be57cc273be5"
BASE_ROM_SHA256 = "9F67FEF1B4C73E966767F6153431ADA3751DC1B0DA2C70F386C14A5E3017F354"
BASE_ROM_SIZE = 33_554_432
BASE_GAME_CODE = b"A2DE"
BASE_ROM_GAME_CODE = BASE_GAME_CODE
PATCH_PROTOCOL_VERSION = 1

PATCH_MARKER_ROM_OFFSET = 0x013A57A8
PATCH_MARKER = bytes.fromhex("1E FF 2F E1 41 50 4E 53 01 00 00 00 00 00 00 00 00 00 00 00")


def _select_base_rom_path() -> Path:
    """Always ask for the clean source ROM used by this patch operation."""
    from Utils import open_filename

    chosen = open_filename(
        "Select New Super Mario Bros. DS (USA) Base ROM",
        [("Nintendo DS ROM", ["*.nds"]), ("All Files", ["*.*"])],
    )
    if not chosen:
        raise FileNotFoundError(
            "No NSMBDS ROM file was selected. Please select a clean USA copy of New Super Mario Bros. DS."
        )
    rom_path = Path(chosen)
    if not rom_path.is_file():
        raise FileNotFoundError(f"The selected NSMBDS ROM is not a file: {rom_path}")
    return rom_path


def _read_validated_base_rom() -> bytes:
    """Prompt for and load only the ROM revision supported by this patch format."""
    rom_path = _select_base_rom_path()

    rom_data = rom_path.read_bytes()
    if len(rom_data) != BASE_ROM_SIZE:
        raise ValueError(
            f"Unsupported NSMBDS ROM size {len(rom_data)}; expected {BASE_ROM_SIZE}."
        )
    if rom_data[0x0C:0x10] != BASE_GAME_CODE:
        raise ValueError(
            f"Unsupported NSMBDS game code {rom_data[0x0C:0x10]!r}; expected {BASE_GAME_CODE!r}."
        )
    actual_md5 = hashlib.md5(rom_data, usedforsecurity=False).hexdigest()
    if actual_md5 != BASE_ROM_MD5:
        raise ValueError(
            "The selected NSMBDS ROM does not match the required clean USA A2DE base ROM "
            f"(expected MD5 {BASE_ROM_MD5}, got {actual_md5})."
        )
    marker_region = rom_data[PATCH_MARKER_ROM_OFFSET:PATCH_MARKER_ROM_OFFSET + len(PATCH_MARKER)]
    if marker_region != b"\xFF" * len(PATCH_MARKER):
        raise ValueError("The validated ROM does not have the expected padding reserved for the patch marker.")
    return rom_data


class NSMBDSPatchExtension(APPatchExtension):
    """Apply NSMBDS-specific steps used by the procedure patch."""

    game = "New Super Mario Bros. DS"
    patch_file_ending = ".apnsmbds"
    result_file_ending = ".nds"

    @staticmethod
    def apply_player_palettes(caller: APProcedurePatch, rom: bytes, config_file: str) -> bytes:
        """Apply deterministic in-level Mario and Luigi palette selections."""
        return patch_player_palettes_from_json(rom, caller.get_file(config_file))


class NSMBDSProcedurePatch(APProcedurePatch, APTokenMixin):
    """Create a per-player patch."""

    hash = BASE_ROM_MD5
    game = "New Super Mario Bros. DS"
    patch_file_ending = ".apnsmbds"
    result_file_ending = ".nds"
    procedure = [
        ("apply_bsdiff4", ["native_hooks.bsdiff4"]),
        ("apply_tokens", ["token_data.bin"]),
        ("apply_player_palettes", ["nsmbds_patch_config.json"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        """Prompt for and return the verified clean base ROM for this patch operation."""
        return _read_validated_base_rom()


def write_patch_payload(world: "NSMBDSWorld", patch: NSMBDSProcedurePatch) -> None:
    """Store seed metadata, native markers, and configuration payload."""
    options = {
        "goal": world.options.goal.value,
        "star_coin_checks": True,
        "red_coin_checks": bool(world.options.red_coin_checks.value),
        "one_up_block_checks": bool(world.options.one_up_block_checks.value),
        "one_up_block_item_placement": world.options.one_up_block_item_placement.value,
        "blocksanity": bool(world.options.blocksanity.value),
        "blocksanity_item_placement": world.options.blocksanity_item_placement.value,
        "world_6_2_bonus_area": world.options.world_6_2_bonus_area.value,
        "required_star_coins": world.options.required_star_coins.value,
        "trap_percentage": world.options.trap_percentage.value,
        "mario_palette": world.options.mario_palette.value,
        "luigi_palette": world.options.luigi_palette.value,
        "tower_castle_keys": bool(world.options.tower_castle_keys.value),
        "license_mini_mushroom": bool(world.options.license_mini_mushroom.value),
        "license_blue_shell": bool(world.options.license_blue_shell.value),
        "license_mega_mushroom": bool(world.options.license_mega_mushroom.value),
        "license_mushroom": bool(world.options.license_mushroom.value),
        "license_fire_flower": bool(world.options.license_fire_flower.value),
        "license_touchscreen_pocket": bool(world.options.license_touchscreen_pocket.value),
        "star_coin_gate_mode": world.options.star_coin_gate_mode.value,
        "death_link": bool(world.options.death_link.value),
    }
    payload = {
        "protocol_version": PATCH_PROTOCOL_VERSION,
        "apworld_version": APWORLD_VERSION,
        "release_channel": RELEASE_CHANNEL,
        "display_version": DISPLAY_VERSION,
        "base_rom_sha256": BASE_ROM_SHA256,
        "player": world.player,
        "player_name": world.multiworld.player_name[world.player],
        "seed_name": world.multiworld.seed_name,
        "options": options,
    }
    patch.write_token(APTokenTypes.WRITE, PATCH_MARKER_ROM_OFFSET, PATCH_MARKER)
    native_patch = (
        importlib.resources.files(__package__)
        .joinpath("native_hooks.bsdiff4")
        .read_bytes()
    )
    if not native_patch.startswith(b"BSDIFF40"):
        raise ValueError("Packaged native hook delta is missing or invalid.")
    patch.write_file("native_hooks.bsdiff4", native_patch)
    patch.write_file("nsmbds_patch_config.json", json.dumps(payload, sort_keys=True).encode("utf-8"))
    patch.write_file("token_data.bin", patch.get_token_binary())


__all__ = [
    "BASE_GAME_CODE",
    "BASE_ROM_MD5",
    "BASE_ROM_SHA256",
    "BASE_ROM_SIZE",
    "NSMBDSPatchExtension",
    "NSMBDSProcedurePatch",
    "PATCH_MARKER",
    "PATCH_MARKER_ROM_OFFSET",
    "PATCH_PROTOCOL_VERSION",
    "write_patch_payload",
]
