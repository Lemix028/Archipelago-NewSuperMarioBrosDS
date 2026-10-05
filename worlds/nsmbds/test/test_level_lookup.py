"""Regression checks for the local /level command."""

from types import SimpleNamespace
from unittest import TestCase

from ..client.features.level_lookup import level_command
from ..data.level_randomization import IDENTITY_LEVEL_MAPPING, LEVEL_RANDOMIZATION_VERSION, level_mapping_digest
from ..locations import LOCATION_TABLE


class TestLevelLookupCommand(TestCase):
    def setUp(self) -> None:
        mapping = dict(IDENTITY_LEVEL_MAPPING)
        mapping["World 3-3"], mapping["World 1-1"] = "World 1-1", "World 3-3"
        mapping["World 2-Castle"], mapping["World 3-Castle"] = "World 3-Castle", "World 2-Castle"
        self.ctx = SimpleNamespace(
            slot_data={
                "level_randomization": 1,
                "level_randomization_version": LEVEL_RANDOMIZATION_VERSION,
                "level_mapping": mapping,
                "level_mapping_digest": level_mapping_digest(mapping),
            },
            checked_locations={LOCATION_TABLE["World 3-3 Star Coin 3"]},
            missing_locations={LOCATION_TABLE["World 2-Castle Secret Exit"]},
        )
        self.lines = []

    def run_command(self, query):
        self.lines.clear()
        return level_command(self.ctx, self.lines.append, query)

    def test_original_course_has_one_unambiguous_entrance(self) -> None:
        for query in ("W3-3", " world 3-3 ", "w3-3"):
            self.assertTrue(self.run_command(query))
            self.assertEqual(self.lines, ["World 3-3 -> Enter World 1-1 (1/1 checks)"])

    def test_full_check_name_and_starcoin_spelling(self) -> None:
        for query in ("World 3-3 Star Coin 3", "W3-3 Starcoin 3"):
            self.assertTrue(self.run_command(query))
            self.assertEqual(self.lines, [
                "World 3-3 Star Coin 3 -> Enter World 1-1 (loaded course: World 3-3)",
            ])

    def test_mini_exit_stays_at_its_physical_castle(self) -> None:
        self.assertTrue(self.run_command("World 2-Castle Secret Exit"))
        self.assertEqual(self.lines, [
            "World 2-Castle Secret Exit -> Enter World 2-Castle (loaded course: World 3-Castle)",
        ])

    def test_all_and_world_lists_follow_physical_slots(self) -> None:
        self.assertTrue(self.run_command("all"))
        self.assertEqual(len(self.lines), 80)
        self.assertTrue(self.lines[0].startswith("World 3-3 -> Enter World 1-1"))
        self.assertTrue(self.run_command("world 3"))
        self.assertEqual(len(self.lines), 9)
        self.assertTrue(self.lines[0].startswith("World 3-1 -> Enter World 3-1"))
        self.assertTrue(any(line.startswith("World 1-1 -> Enter World 3-3") for line in self.lines))
        self.assertFalse(any(line.startswith("World 3-3 ->") for line in self.lines))

    def test_help_and_missing_seed(self) -> None:
        self.ctx.slot_data = None
        self.assertTrue(self.run_command(""))
        self.assertIn("Usage: /level", self.lines[0])
        self.assertFalse(self.run_command("W3-3"))
        self.assertIn("Connect to a seed", self.lines[0])

    def test_unknown_check_and_corrupt_mapping(self) -> None:
        self.assertFalse(self.run_command("World 3-3 Star Coin 9"))
        self.assertIn("No matching level or active check", self.lines[0])
        self.ctx.slot_data["level_mapping_digest"] = "wrong"
        self.assertFalse(self.run_command("W3-3"))
        self.assertIn("Could not load level mapping", self.lines[0])

    def test_vanilla_seed_and_updated_progress(self) -> None:
        self.ctx.slot_data = {"level_randomization": 0}
        self.assertTrue(self.run_command("W3-3"))
        self.assertEqual(self.lines, ["World 3-3 -> Enter World 3-3 (1/1 checks)"])
        self.ctx.checked_locations.clear()
        self.ctx.missing_locations = {LOCATION_TABLE["World 3-3 Star Coin 3"]}
        self.assertTrue(self.run_command("W3-3"))
        self.assertEqual(self.lines, ["World 3-3 -> Enter World 3-3 (0/1 checks)"])
