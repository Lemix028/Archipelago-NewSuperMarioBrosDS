"""Tests for deterministic secondary-screen background remapping."""

from __future__ import annotations

import struct
import unittest

from ..rom.secondary_screen import (
    SECONDARY_SCREEN_BACKGROUND_FILE_IDS,
    SECONDARY_SCREEN_CLASSIC_OVERWORLD,
    patch_secondary_screen_backgrounds,
    resolve_secondary_screen_order,
    resolve_secondary_screen_sources,
)


def _synthetic_rom() -> tuple[bytes, dict[int, tuple[int, int]], dict[int, bytes]]:
    fat_offset = 0x100
    file_count = max(SECONDARY_SCREEN_BACKGROUND_FILE_IDS) + 1
    output = bytearray(0x6000)
    struct.pack_into("<II", output, 0x48, fat_offset, file_count * 8)
    expected_ranges = {}
    expected_payloads = {}
    for index, file_id in enumerate(SECONDARY_SCREEN_BACKGROUND_FILE_IDS):
        start = 0x5000 + index * 0x20
        end = start + 0x10
        expected_ranges[file_id] = (start, end)
        expected_payloads[file_id] = bytes([index + 1]) * (end - start)
        struct.pack_into("<II", output, fat_offset + file_id * 8, start, end)
        output[start:end] = expected_payloads[file_id]
    return bytes(output), expected_ranges, expected_payloads


class TestSecondaryScreenBackgrounds(unittest.TestCase):
    def test_randomized_order_is_stable_complete_derangement(self) -> None:
        first = resolve_secondary_screen_order("test-seed", 1)
        second = resolve_secondary_screen_order("test-seed", 1)
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(SECONDARY_SCREEN_BACKGROUND_FILE_IDS))
        self.assertTrue(all(
            target != source
            for target, source in zip(SECONDARY_SCREEN_BACKGROUND_FILE_IDS, first)
        ))

    def test_randomized_patch_uses_independent_copies_of_the_shuffled_files(self) -> None:
        rom, original_ranges, original_payloads = _synthetic_rom()
        config = {
            "seed_name": "test-seed",
            "player": 1,
            "options": {"secondary_screen_background": 1},
        }
        patched = patch_secondary_screen_backgrounds(rom, config)
        fat_offset = struct.unpack_from("<I", patched, 0x48)[0]
        resolved = resolve_secondary_screen_order("test-seed", 1)
        patched_ranges = []
        for target_id, source_id in zip(SECONDARY_SCREEN_BACKGROUND_FILE_IDS, resolved):
            start, end = struct.unpack_from("<II", patched, fat_offset + target_id * 8)
            patched_ranges.append((start, end))
            self.assertNotIn((start, end), original_ranges.values())
            self.assertEqual(patched[start:end], original_payloads[source_id])
        self.assertEqual(len(set(patched_ranges)), len(SECONDARY_SCREEN_BACKGROUND_FILE_IDS))
        self.assertEqual(patched_ranges[0][0] % 0x200, 0)
        self.assertEqual(len(patched), len(rom))

    def test_fixed_choice_uses_the_selected_background_in_every_slot(self) -> None:
        rom, _, original_payloads = _synthetic_rom()
        patched = patch_secondary_screen_backgrounds(
            rom,
            {"options": {"secondary_screen_background": SECONDARY_SCREEN_CLASSIC_OVERWORLD}},
        )
        fat_offset = struct.unpack_from("<I", patched, 0x48)[0]
        expected = original_payloads[2012]
        for target_id in SECONDARY_SCREEN_BACKGROUND_FILE_IDS:
            start, end = struct.unpack_from("<II", patched, fat_offset + target_id * 8)
            self.assertEqual(patched[start:end], expected)

    def test_fixed_choice_resolves_to_the_same_source_for_every_slot(self) -> None:
        self.assertEqual(
            resolve_secondary_screen_sources(SECONDARY_SCREEN_CLASSIC_OVERWORLD, "seed", 1),
            (2012,) * len(SECONDARY_SCREEN_BACKGROUND_FILE_IDS),
        )

    def test_vanilla_mode_leaves_rom_unchanged(self) -> None:
        rom, _, _ = _synthetic_rom()
        self.assertIs(
            patch_secondary_screen_backgrounds(
                rom,
                {"options": {"secondary_screen_background": 0}},
            ),
            rom,
        )

    def test_unknown_mode_is_rejected(self) -> None:
        rom, _, _ = _synthetic_rom()
        with self.assertRaisesRegex(ValueError, "Unknown secondary-screen background mode"):
            patch_secondary_screen_backgrounds(
                rom,
                {"options": {"secondary_screen_background": 99}},
            )
