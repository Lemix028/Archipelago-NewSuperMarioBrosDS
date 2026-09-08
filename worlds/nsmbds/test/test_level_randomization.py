"""Regression coverage for alpha level randomization."""

from __future__ import annotations

import struct
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ..client.features.block_checks import BlockCheckTrackingMixin
from ..client.features.goals import GoalHandlingMixin
from ..client.features.red_coins import RedCoinTrackingMixin
from ..data.level_randomization import (
    ALL_STORY_LEVELS,
    FINAL_CASTLE_STAGE,
    IDENTITY_LEVEL_MAPPING,
    LEVEL_AREA_ID_BY_NAME,
    LEVEL_NODE_OFFSET_BY_NAME,
    LEVEL_RANDOMIZATION_GLOBAL,
    LEVEL_RANDOMIZATION_VERSION,
    LEVEL_RANDOMIZATION_WITHIN_WORLD,
    LEVEL_SLOT_BY_NAME,
    LevelPool,
    generate_level_mapping,
    level_mapping_digest,
    validate_level_mapping,
)
from ..data.ram_addresses import AP_EVENT_TYPE_BLOCK_BUMP, MINI_CASTLE_FLAGS_GAME_DATA_OFFSET
from ..locations import (
    ACTIVE_STAGE_BY_NAME,
    LOCATION_TABLE,
    RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME,
    build_boss_location_completion_sources,
    build_secret_exit_ram_requirements,
)
from ..rom.level_randomization import (
    OVERLAY_FILE_ID,
    OVERLAY_ID,
    OVERLAY_RAM_ADDRESS,
    OVERLAY_RAM_SIZE,
    patch_level_randomization,
)
from .bases import NSMBDSTestBase


class TestLevelMapping(TestCase):

    def test_global_mapping_is_stable_bijective_and_pool_safe(self) -> None:
        mapping = generate_level_mapping("mapping-test", 2, LEVEL_RANDOMIZATION_GLOBAL)
        self.assertEqual(
            mapping,
            generate_level_mapping("mapping-test", 2, LEVEL_RANDOMIZATION_GLOBAL),
        )
        self.assertEqual(set(mapping), set(ALL_STORY_LEVELS))
        self.assertEqual(set(mapping.values()), set(ALL_STORY_LEVELS))
        self.assertEqual(mapping[FINAL_CASTLE_STAGE], FINAL_CASTLE_STAGE)
        self.assertTrue(all(
            LEVEL_SLOT_BY_NAME[slot].pool is LEVEL_SLOT_BY_NAME[content].pool
            for slot, content in mapping.items()
        ))
        self.assertTrue(all(
            slot == FINAL_CASTLE_STAGE or slot != content
            for slot, content in mapping.items()
        ))

    def test_within_world_mapping_never_crosses_worlds(self) -> None:
        mapping = generate_level_mapping(
            "mapping-test", 2, LEVEL_RANDOMIZATION_WITHIN_WORLD
        )
        self.assertTrue(all(
            LEVEL_SLOT_BY_NAME[slot].world_number
            == LEVEL_SLOT_BY_NAME[content].world_number
            for slot, content in mapping.items()
        ))
        validate_level_mapping(mapping, LEVEL_RANDOMIZATION_WITHIN_WORLD)

    def test_global_mapping_rejects_cross_pool_corruption(self) -> None:
        mapping = generate_level_mapping("mapping-test", 1, LEVEL_RANDOMIZATION_GLOBAL)
        normal = next(name for name in mapping if LEVEL_SLOT_BY_NAME[name].pool is LevelPool.NORMAL)
        tower = next(name for name in mapping if LEVEL_SLOT_BY_NAME[name].pool is LevelPool.TOWER)
        mapping[normal], mapping[tower] = mapping[tower], mapping[normal]
        with self.assertRaisesRegex(ValueError, "Incompatible level mapping"):
            validate_level_mapping(mapping, LEVEL_RANDOMIZATION_GLOBAL)

    def test_secret_and_boss_sources_follow_destination_slots(self) -> None:
        mapping = generate_level_mapping("mapping-test", 1, LEVEL_RANDOMIZATION_GLOBAL)
        secret_requirements = build_secret_exit_ram_requirements(mapping)
        source = mapping["World 1-2"]
        self.assertIn(f"{source} Secret Exit", secret_requirements)
        self.assertEqual(
            secret_requirements[f"{source} Secret Exit"],
            ((0xD2, 0xC0), (0xDE, 0xC0)),
        )

        castle_content = mapping["World 2-Castle"]
        stage = ACTIVE_STAGE_BY_NAME[castle_content]
        goal_offset = stage.goal_ram_offset if stage.goal_ram_offset is not None else stage.ram_offset
        self.assertEqual(
            secret_requirements["World 2-Castle Secret Exit"],
            ((goal_offset, 0x10), (MINI_CASTLE_FLAGS_GAME_DATA_OFFSET, 0x01)),
        )
        boss_name = next(
            name for name in build_boss_location_completion_sources(mapping)
            if name.startswith(castle_content + " ")
        )
        self.assertIn(
            "World 2-Castle Secret Exit",
            build_boss_location_completion_sources(mapping)[boss_name],
        )

    def test_final_castle_gate_uses_the_course_in_tower_two_slot(self) -> None:
        mapping = generate_level_mapping("mapping-test", 1, LEVEL_RANDOMIZATION_GLOBAL)
        slot_data = {
            "goal": 0,
            "tower_castle_keys": False,
            "level_randomization": LEVEL_RANDOMIZATION_GLOBAL,
            "level_randomization_version": LEVEL_RANDOMIZATION_VERSION,
            "level_mapping": mapping,
            "level_mapping_digest": level_mapping_digest(mapping),
        }
        handler = GoalHandlingMixin()
        handler._observed_locations = {
            LOCATION_TABLE[f"{mapping['World 8-Tower 2']} Goal"]
        }
        context = SimpleNamespace(slot_data=slot_data, items_received=[])
        self.assertTrue(handler._final_castle_gate_should_open(context))

    def test_block_runtime_slot_identity_resolves_loaded_content(self) -> None:
        mapping = dict(IDENTITY_LEVEL_MAPPING)
        mapping["World 1-1"], mapping["World 2-1"] = "World 2-1", "World 1-1"
        slot_data = {
            "level_randomization": LEVEL_RANDOMIZATION_GLOBAL,
            "level_randomization_version": LEVEL_RANDOMIZATION_VERSION,
            "level_mapping": mapping,
            "level_mapping_digest": level_mapping_digest(mapping),
        }
        source_key, expected_name = next(
            (key, name)
            for key, name in RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME.items()
            if key[:2] == (1, 1)
            and (0, 1, *key[2:]) not in RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME
        )
        reported_key = (0, 1, *source_key[2:])
        self.assertEqual(
            BlockCheckTrackingMixin._resolve_seed_block_location(
                slot_data,
                reported_key,
                AP_EVENT_TYPE_BLOCK_BUMP,
            ),
            expected_name,
        )

    def test_red_coin_runtime_slot_identity_resolves_loaded_content(self) -> None:
        mapping = dict(IDENTITY_LEVEL_MAPPING)
        mapping["World 1-3"], mapping["World 2-2"] = "World 2-2", "World 1-3"
        slot_data = {
            "level_randomization": LEVEL_RANDOMIZATION_GLOBAL,
            "level_randomization_version": LEVEL_RANDOMIZATION_VERSION,
            "level_mapping": mapping,
            "level_mapping_digest": level_mapping_digest(mapping),
        }
        self.assertEqual(
            RedCoinTrackingMixin._resolve_seed_red_coin_location(
                slot_data,
                1,
                3,
                0,
                0,
                1,
            ),
            "World 1-3 Red Coin Challenge",
        )


class TestGlobalLevelRandomizationGeneration(NSMBDSTestBase):
    options = {
        "level_randomization": "global",
        "secret_exit_checks": True,
        "secret_exit_shortcut_logic": True,
        "secret_exit_world_unlock_logic": True,
        "cannon_route_logic": True,
    }

    def test_slot_entrances_and_course_checks_use_the_same_mapping(self) -> None:
        mapping = self.world.level_mapping
        content = mapping["World 1-1"]
        entrance = self.multiworld.get_entrance("World 1 -> World 1-1", self.player)
        self.assertEqual(entrance.connected_region.name, content)
        goal = self.multiworld.get_location(f"{content} Goal", self.player)
        self.assertEqual(goal.parent_region.name, content)

        castle_content = mapping["World 2-Castle"]
        mini_exit = self.multiworld.get_location(
            "World 2-Castle Secret Exit", self.player
        )
        self.assertEqual(mini_exit.parent_region.name, castle_content)

    def test_mapping_round_trips_through_slot_data(self) -> None:
        original = dict(self.world.level_mapping)
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["level_mapping"], original)
        self.assertEqual(slot_data["level_randomization_version"], LEVEL_RANDOMIZATION_VERSION)
        self.assertEqual(slot_data["level_mapping_digest"], level_mapping_digest(original))

        self.multiworld.re_gen_passthrough = {self.world.game: slot_data}
        self.world.level_mapping = {}
        self.world.generate_early()
        self.assertEqual(self.world.level_mapping, original)


class TestWithinWorldLevelRandomizationGeneration(NSMBDSTestBase):
    options = {
        "level_randomization": "within_world",
        "secret_exit_checks": True,
    }


class TestRandomizedRouteRequirements(NSMBDSTestBase):
    options = {
        "level_randomization": "global",
        "secret_exit_checks": True,
        "secret_exit_shortcut_logic": True,
        "secret_exit_world_unlock_logic": True,
        "cannon_route_logic": True,
        "tower_castle_keys": False,
        "license_blue_shell": True,
        "license_mini_mushroom": True,
    }

    def setUp(self) -> None:
        mapping = dict(IDENTITY_LEVEL_MAPPING)
        for first, second in (
            ("World 1-2", "World 1-Tower"),
            ("World 2-4", "World 5-B"),
            ("World 1-1", "World 6-2"),
        ):
            mapping[first], mapping[second] = mapping[second], mapping[first]
        with patch("worlds.nsmbds.generate_level_mapping", return_value=mapping):
            super().setUp()

    def test_tower_secret_exit_gates_destination_toad_house(self) -> None:
        self.collect_all_but("Blue Shell Permit")
        self.assertTrue(self.can_reach_location("World 1-Tower Goal"))
        self.assertFalse(self.can_reach_location("World 1-Tower Secret Exit"))
        self.assertFalse(self.can_reach_location("World 1 Red Toad House 1 Goal"))
        self.collect_by_name("Blue Shell Permit")
        self.assertTrue(self.can_reach_location("World 1 Red Toad House 1 Goal"))

    def test_toad_house_does_not_keep_vanilla_mini_requirement(self) -> None:
        self.collect_all_but("Mini Mushroom Permit")
        self.assertTrue(self.can_reach_location("World 5-B Secret Exit"))
        self.assertTrue(self.can_reach_location("World 2 Red Toad House 2 Goal"))

    def test_bonus_room_follows_world_six_two_content(self) -> None:
        region = self.multiworld.get_region("World 6-2 Bonus Area", self.player)
        self.assertEqual([entrance.parent_region.name for entrance in region.entrances],
                         ["World 6-2"])


class TestRandomizedHiddenExitRequirements(TestRandomizedRouteRequirements):
    options = {**TestRandomizedRouteRequirements.options, "secret_exit_checks": False}


class TestTrackerRandomizedRouteRequirements(TestRandomizedHiddenExitRequirements):
    def setUp(self) -> None:
        super().setUp()
        if not hasattr(self, "world"):
            return
        from .. import NSMBDSWorld

        slot_data = NSMBDSWorld.interpret_slot_data(self.world.fill_slot_data())
        generate_early = NSMBDSWorld.generate_early

        def restore_seed(world):
            world.multiworld.re_gen_passthrough = {world.game: slot_data}
            generate_early(world)

        # UT starts from defaults and must restore all options and the mapping.
        self.options = {}
        with patch.object(NSMBDSWorld, "generate_early", restore_seed), patch(
            "worlds.nsmbds.generate_level_mapping",
            side_effect=AssertionError("Tracker must not generate a new mapping"),
        ):
            self.world_setup(seed=12345)


class TestLevelRandomizationRomPatch(TestCase):

    @staticmethod
    def _synthetic_rom() -> tuple[bytes, int, int]:
        overlay_table_offset = 0x100
        fat_offset = 0x200
        old_start = 0x1000
        old_end = old_start + OVERLAY_RAM_SIZE
        rom = bytearray(old_end + OVERLAY_RAM_SIZE + 0x1000)
        struct.pack_into("<II", rom, 0x50, overlay_table_offset, 32)
        struct.pack_into("<II", rom, 0x48, fat_offset, (OVERLAY_FILE_ID + 1) * 8)
        struct.pack_into(
            "<IIIIIIII",
            rom,
            overlay_table_offset,
            OVERLAY_ID,
            OVERLAY_RAM_ADDRESS,
            OVERLAY_RAM_SIZE,
            0,
            0,
            0,
            OVERLAY_FILE_ID,
            0,
        )
        struct.pack_into(
            "<II", rom, fat_offset + OVERLAY_FILE_ID * 8, old_start, old_end
        )
        for stage_name in ALL_STORY_LEVELS:
            rom[old_start + LEVEL_NODE_OFFSET_BY_NAME[stage_name]] = (
                LEVEL_AREA_ID_BY_NAME[stage_name]
            )
        return bytes(rom), overlay_table_offset, fat_offset

    def test_rom_patch_rehomes_uncompressed_overlay_and_writes_all_nodes(self) -> None:
        rom, overlay_entry, fat_offset = self._synthetic_rom()
        mapping = generate_level_mapping("rom-test", 1, LEVEL_RANDOMIZATION_GLOBAL)
        slot_data = {
            "level_randomization": LEVEL_RANDOMIZATION_GLOBAL,
            "level_randomization_version": LEVEL_RANDOMIZATION_VERSION,
            "level_mapping": mapping,
            "level_mapping_digest": level_mapping_digest(mapping),
        }
        patched = patch_level_randomization(rom, slot_data)
        new_start, new_end = struct.unpack_from(
            "<II", patched, fat_offset + OVERLAY_FILE_ID * 8
        )
        self.assertEqual(new_end - new_start, OVERLAY_RAM_SIZE)
        self.assertEqual(struct.unpack_from("<I", patched, overlay_entry + 0x1C)[0], 0)
        for slot_name in ALL_STORY_LEVELS:
            self.assertEqual(
                patched[new_start + LEVEL_NODE_OFFSET_BY_NAME[slot_name]],
                LEVEL_AREA_ID_BY_NAME[mapping[slot_name]],
            )
