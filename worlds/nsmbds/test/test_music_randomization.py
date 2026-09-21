"""Regression coverage for deterministic music randomization."""

from __future__ import annotations

import struct
from collections import Counter
from random import Random
from unittest import TestCase

from ..data.music import (
    LEVEL_MUSIC_CONTEXTS,
    LEVEL_TRACKS,
    MIXED_LEVEL_TRACKS,
    MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS,
    MUSIC_RANDOMIZATION_LEVELS,
    MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS,
    MUSIC_RANDOMIZATION_OFF,
    SAFE_LEVEL_SEQUENCE_IDS,
    SAFE_MIXED_LEVEL_SEQUENCE_IDS,
    SAFE_WORLD_MAP_SEQUENCE_IDS,
    TRACK_BY_ID,
    WORLD_MAP_MUSIC_CONTEXTS,
    MusicCategory,
    MusicTrack,
    balanced_music_assignment,
    generate_music_mapping,
    validate_music_mapping,
)
from ..rom.music import (
    WORLD_MAP_MUSIC_TABLE_OFFSET,
    patch_course_music_data,
    patch_music_randomization,
    patch_world_map_music_overlay,
)


class TestMusicMapping(TestCase):

    def test_off_has_no_mapping(self) -> None:
        self.assertEqual(generate_music_mapping(Random(1), MUSIC_RANDOMIZATION_OFF), ({}, {}))

    def test_level_mapping_is_deterministic_balanced_and_safe(self) -> None:
        first = generate_music_mapping(Random(12345), MUSIC_RANDOMIZATION_LEVELS)
        second = generate_music_mapping(Random(12345), MUSIC_RANDOMIZATION_LEVELS)
        different = generate_music_mapping(Random(54321), MUSIC_RANDOMIZATION_LEVELS)
        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        levels, maps = first
        self.assertFalse(maps)
        self.assertEqual(set(levels), {context.name for context in LEVEL_MUSIC_CONTEXTS})
        self.assertEqual(len(levels), 80)
        self.assertLessEqual(max(Counter(levels.values()).values()) - min(Counter(levels.values()).values()), 1)
        self.assertTrue(set(levels.values()) <= SAFE_LEVEL_SEQUENCE_IDS)
        self.assertTrue(set(levels.values()) <= set(TRACK_BY_ID))
        self.assertTrue(set(levels.values()).isdisjoint(SAFE_WORLD_MAP_SEQUENCE_IDS))
        self.assertTrue(all(TRACK_BY_ID[value].category is MusicCategory.LEVEL for value in levels.values()))
        validate_music_mapping(MUSIC_RANDOMIZATION_LEVELS, levels, maps)

    def test_world_maps_are_a_safe_derangement(self) -> None:
        levels, maps = generate_music_mapping(
            Random(777), MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS
        )
        self.assertEqual(set(maps.values()), SAFE_WORLD_MAP_SEQUENCE_IDS)
        self.assertTrue(all(
            maps[context.name] != context.original_sequence_id
            for context in WORLD_MAP_MUSIC_CONTEXTS
        ))
        validate_music_mapping(MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS, levels, maps)
        invalid_maps = dict.fromkeys(maps, 100)
        with self.assertRaisesRegex(ValueError, "one-to-one permutation"):
            validate_music_mapping(
                MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS, levels, invalid_maps
            )

    def test_mixed_mode_uses_all_19_tracks_across_levels_and_worlds(self) -> None:
        levels, maps = generate_music_mapping(
            Random(2468), MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS
        )
        self.assertEqual(len(MIXED_LEVEL_TRACKS), 19)
        combined_values = (*levels.values(), *maps.values())
        self.assertEqual(set(combined_values), SAFE_MIXED_LEVEL_SEQUENCE_IDS)
        self.assertTrue(set(maps.values()) & SAFE_LEVEL_SEQUENCE_IDS)
        self.assertTrue(set(levels.values()) & SAFE_WORLD_MAP_SEQUENCE_IDS)
        counts = Counter(combined_values)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
        validate_music_mapping(
            MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS, levels, maps
        )

    def test_small_pools_terminate(self) -> None:
        contexts = LEVEL_MUSIC_CONTEXTS[:5]
        one = (MusicTrack("one", "One", 200, MusicCategory.LEVEL, True),)
        two = one + (MusicTrack("two", "Two", 201, MusicCategory.LEVEL, True),)
        with self.assertRaises(ValueError):
            balanced_music_assignment(contexts, (), Random(1))
        self.assertEqual(set(balanced_music_assignment(contexts, one, Random(1)).values()), {200})
        counts = Counter(balanced_music_assignment(contexts, two, Random(1)).values())
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)


class TestMusicRomPatching(TestCase):

    def test_off_returns_exact_original(self) -> None:
        original = b"not even a ROM"
        self.assertIs(patch_music_randomization(original, {"music_randomization": 0}), original)

    def test_course_patch_only_replaces_safe_view_music(self) -> None:
        course = bytearray(160)
        struct.pack_into("<II", course, 7 * 8, 112, 48)
        course[122] = 26
        course[138] = 15
        course[154] = 80
        patched, count = patch_course_music_data(bytes(course), 6)
        self.assertEqual(count, 1)
        self.assertEqual(patched[122], 6)
        self.assertEqual(patched[138], 15)
        self.assertEqual(patched[154], 80)
        self.assertEqual(len(patched), len(course))

    def test_world_map_patch_preserves_non_world_entries(self) -> None:
        overlay = bytearray(WORLD_MAP_MUSIC_TABLE_OFFSET + 40)
        struct.pack_into(
            "<10I", overlay, WORLD_MAP_MUSIC_TABLE_OFFSET,
            *range(100, 108), 29, 112,
        )
        mapping = {
            context.name: 100 + ((context.table_index + 1) % 8)
            for context in WORLD_MAP_MUSIC_CONTEXTS
        }
        patched = patch_world_map_music_overlay(bytes(overlay), mapping)
        values = struct.unpack_from("<10I", patched, WORLD_MAP_MUSIC_TABLE_OFFSET)
        self.assertEqual(values[:8], tuple(mapping[f"World {index}"] for index in range(1, 9)))
        self.assertEqual(values[8:], (29, 112))
        self.assertEqual(len(patched), len(overlay))

    def test_bounds_are_rejected(self) -> None:
        course = bytearray(112)
        struct.pack_into("<II", course, 7 * 8, 112, 16)
        with self.assertRaisesRegex(ValueError, "invalid view block"):
            patch_course_music_data(bytes(course), 6)
        with self.assertRaisesRegex(ValueError, "too short"):
            patch_world_map_music_overlay(b"", {
                context.name: context.original_sequence_id
                for context in WORLD_MAP_MUSIC_CONTEXTS
            })
