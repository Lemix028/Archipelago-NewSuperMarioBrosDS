"""Unit tests for NSMBDS YAML option combinations."""

from types import SimpleNamespace
from unittest.mock import patch

from BaseClasses import LocationProgressType

from .bases import NSMBDSTestBase
from ..data.star_coin_gates import STAR_COIN_GATES, TOTAL_STAR_COIN_GATE_COST
from ..items import FILLER_ITEM_WEIGHTS
from ..locations import (
    BLOCKSANITY_DEFINITIONS,
    BOSS_LOCATION_NAMES,
    ONE_UP_BLOCK_DEFINITIONS,
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES,
)
from ..options import RequiredStarCoins, TrapPercentage


def advancement_star_coins_behind_gates(test: NSMBDSTestBase) -> list:
    gated_regions = {gate.target_stage_name for gate in STAR_COIN_GATES}
    return [
        location
        for location in test.multiworld.get_locations(test.player)
        if location.parent_region.name in gated_regions
        and location.item is not None
        and location.item.name == "Star Coin"
        and location.item.advancement
    ]


class TestStarCoinsAlwaysIncluded(NSMBDSTestBase):
    """Star Coin checks and their randomized items are part of every seed."""

    def test_all_star_coin_checks_and_items_are_present(self) -> None:
        locations = [
            location for location in self.multiworld.get_locations(self.player)
            if "Star Coin" in location.name
        ]
        items = [item for item in self.multiworld.get_items() if item.name == "Star Coin"]
        self.assertEqual(len(locations), 240)
        self.assertEqual(len(items), 240)

    def test_gate_currency_progression_is_not_balanced_early(self) -> None:
        items = [item for item in self.multiworld.get_items() if item.name == "Star Coin"]
        advancement = [item for item in items if item.advancement]
        useful = [item for item in items if item.useful]
        self.assertEqual(TOTAL_STAR_COIN_GATE_COST, 160)
        self.assertEqual(len(advancement), 160)
        self.assertTrue(all(item.skip_in_prog_balancing for item in advancement))
        self.assertEqual(len(useful), 80)

    def test_required_gate_currency_is_never_behind_a_star_coin_sign(self) -> None:
        self.assertFalse(advancement_star_coins_behind_gates(self))


class TestMaximumStarCoinGoalClassification(NSMBDSTestBase):
    options = {
        "goal": "star_coin_hunt",
        "required_star_coins": 240,
    }

    def test_all_coins_are_progression_for_a_240_coin_goal(self) -> None:
        items = [item for item in self.multiworld.get_items() if item.name == "Star Coin"]
        self.assertEqual(len(items), 240)
        self.assertTrue(all(
            item.advancement and item.skip_in_prog_balancing
            for item in items
        ))


class TestBalancingDefaults(NSMBDSTestBase):
    def test_goal_and_trap_defaults(self) -> None:
        self.assertEqual(RequiredStarCoins.range_start, 30)
        self.assertEqual(RequiredStarCoins.default, 80)
        self.assertEqual(TrapPercentage.default, 20)

    def test_strong_filler_items_are_weighted_below_common_items(self) -> None:
        self.assertLess(FILLER_ITEM_WEIGHTS["3-Up Moon"], FILLER_ITEM_WEIGHTS["1-Up Mushroom"])
        self.assertLess(FILLER_ITEM_WEIGHTS["Trap Shield"], FILLER_ITEM_WEIGHTS["Mushroom"])
        self.assertLess(FILLER_ITEM_WEIGHTS["Life Insurance"], FILLER_ITEM_WEIGHTS["Coin Bundle"])


class TestRedCoinChecksDisabled(NSMBDSTestBase):
    """Test world generation when Red Coin checks are disabled."""

    options = {
        "red_coin_checks": False,
    }

    def test_red_coins_excluded(self) -> None:
        """Red Coin Challenge locations should not exist in the location pool when disabled."""
        for loc in self.multiworld.get_locations(self.player):
            self.assertNotIn("Red Coin Challenge", loc.name)


class TestCastleBossLocations(NSMBDSTestBase):
    """Castle bosses are genuine randomized AP checks, not locked events."""

    def test_all_nine_boss_checks_are_randomized_locations(self) -> None:
        locations = [
            self.multiworld.get_location(name, self.player)
            for name in BOSS_LOCATION_NAMES
        ]
        self.assertEqual(len(locations), 9)
        self.assertTrue(all(location.address is not None for location in locations))
        self.assertTrue(all(not location.locked for location in locations))


class TestOneUpBlockChecksDisabled(NSMBDSTestBase):
    """Test world generation when 1-Up Block checks are disabled."""

    options = {
        "one_up_block_checks": False,
    }

    def test_one_up_blocks_excluded(self) -> None:
        """1-Up Block locations should not exist in the location pool when disabled."""
        for loc in self.multiworld.get_locations(self.player):
            self.assertNotIn("1-Up Block", loc.name)


class TestBlocksanityDisabled(NSMBDSTestBase):
    options = {
        "blocksanity": False,
    }

    def test_blocksanity_locations_excluded(self) -> None:
        for loc in self.multiworld.get_locations(self.player):
            self.assertNotIn("Blocksanity", loc.name)


class TestBlocksanityEnabled(NSMBDSTestBase):
    options = {
        "blocksanity": True,
    }

    def test_all_blocksanity_locations_included(self) -> None:
        locations = [
            loc for loc in self.multiworld.get_locations(self.player)
            if "Blocksanity" in loc.name
        ]
        self.assertEqual(len(locations), len(BLOCKSANITY_DEFINITIONS))


class TestWorldSixTwoBonusArea(NSMBDSTestBase):
    options = {
        "blocksanity": True,
        "one_up_block_checks": True,
    }

    def test_bonus_area_is_separate_and_nonprogression(self) -> None:
        bonus_locations = [
            location
            for location in self.multiworld.get_locations(self.player)
            if location.parent_region.name == "World 6-2 Bonus Area"
        ]
        self.assertEqual(len(bonus_locations), 128)
        self.assertTrue(all(
            location.progress_type == LocationProgressType.EXCLUDED
            for location in bonus_locations
        ))


class TestWorldSixTwoBonusAreaDisabled(NSMBDSTestBase):
    options = {
        "blocksanity": True,
        "one_up_block_checks": True,
        "world_6_2_bonus_area": False,
    }

    def test_bonus_area_locations_are_removed(self) -> None:
        self.assertFalse(any(
            location.parent_region.name == "World 6-2 Bonus Area"
            for location in self.multiworld.get_locations(self.player)
        ))


class TestNormalBlockPlacementProgression(NSMBDSTestBase):
    options = {
        "blocksanity": True,
        "one_up_block_checks": True,
        "blocksanity_item_placement": "progression",
        "one_up_block_item_placement": "progression",
        "world_6_2_bonus_area": False,
    }

    def test_normal_block_checks_allow_progression(self) -> None:
        block_locations = [
            location
            for location in self.multiworld.get_locations(self.player)
            if (
                "Blocksanity" in location.name
                or "1-Up Block" in location.name
            )
        ]
        self.assertEqual(
            len(block_locations),
            len(BLOCKSANITY_DEFINITIONS)
            + len(ONE_UP_BLOCK_DEFINITIONS)
            - len(WORLD_6_2_BONUS_AREA_LOCATION_NAMES),
        )
        global_locations = [
            location for location in block_locations
            if location.progress_type == LocationProgressType.DEFAULT
        ]
        self.assertTrue(global_locations)
        self.assertTrue(all(
            location.item_rule(self.world.create_item("Desert Pass"))
            for location in global_locations
        ))


class TestNormalBlockPlacementNonProgression(NSMBDSTestBase):
    options = {
        "blocksanity": True,
        "one_up_block_checks": True,
        "blocksanity_item_placement": "non_progression",
        "one_up_block_item_placement": "non_progression",
        "world_6_2_bonus_area": False,
    }

    def test_normal_blocks_allow_useful_but_reject_progression(self) -> None:
        world = self.multiworld.worlds[self.player]
        progression = world.create_item("Desert Pass")
        useful = world.create_item("Mushroom")
        filler = world.create_item("1-Up Mushroom")
        block_locations = [
            location
            for location in self.multiworld.get_locations(self.player)
            if ("Blocksanity" in location.name or "1-Up Block" in location.name)
            and location.progress_type == LocationProgressType.DEFAULT
        ]
        self.assertTrue(block_locations)
        self.assertTrue(all(
            location.progress_type == LocationProgressType.DEFAULT
            and not location.item_rule(progression)
            and location.item_rule(useful)
            and location.item_rule(filler)
            for location in block_locations
        ))


class TestUnsafeHostOptions(NSMBDSTestBase):
    def test_host_rejects_unsafe_percentages_by_default(self) -> None:
        world = self.multiworld.worlds[self.player]
        world.options.blocksanity_global_check_percentage.value = 31
        host = SimpleNamespace(nsmbds_options=SimpleNamespace(
            allow_unsafe_nsmbds_options=False,
        ))
        with patch("worlds.nsmbds.get_settings", return_value=host):
            with self.assertRaisesRegex(Exception, "host maximum of 30%"):
                world.generate_early()

    def test_host_can_allow_unsafe_percentages(self) -> None:
        world = self.multiworld.worlds[self.player]
        world.options.blocksanity_global_check_percentage.value = 31
        world.options.trap_percentage.value = 51
        host = SimpleNamespace(nsmbds_options=SimpleNamespace(
            allow_unsafe_nsmbds_options=True,
        ))
        with patch("worlds.nsmbds.get_settings", return_value=host):
            world.generate_early()


class TestTowerCastleKeysEnabled(NSMBDSTestBase):
    """Test item pool construction when Tower & Castle Keys are enabled."""

    options = {
        "tower_castle_keys": True,
    }

    def test_keys_in_item_pool(self) -> None:
        """Keys should be added to the item pool when enabled."""
        item_names = [item.name for item in self.multiworld.get_items()]
        self.assertIn("Grassland Tower Key", item_names)
        self.assertIn("Grassland Castle Key", item_names)


class TestPowerupLicensesOff(NSMBDSTestBase):
    options = {
        "license_mini_mushroom": False,
        "license_blue_shell": False,
        "license_mega_mushroom": False,
        "license_mushroom": False,
        "license_fire_flower": False,
        "license_touchscreen_pocket": False,
        "tower_castle_keys": False,
    }

    def test_license_items_are_absent(self) -> None:
        item_names = [item.name for item in self.multiworld.get_items()]
        self.assertNotIn("Mini Mushroom Permit", item_names)
        self.assertNotIn("Blue Shell Permit", item_names)
        self.assertNotIn("Mega Mushroom Permit", item_names)
        self.assertNotIn("Mushroom Permit", item_names)
        self.assertNotIn("Fire Flower Permit", item_names)
        self.assertNotIn("Touchscreen Pocket Permit", item_names)


class TestExistingPowerupLicenses(NSMBDSTestBase):
    options = {
        "license_mega_mushroom": False,
        "license_mushroom": False,
        "license_fire_flower": False,
        "license_touchscreen_pocket": False,
        "tower_castle_keys": False,
    }

    def test_only_existing_licenses_are_in_pool(self) -> None:
        item_names = [item.name for item in self.multiworld.get_items()]
        self.assertIn("Mini Mushroom Permit", item_names)
        self.assertIn("Blue Shell Permit", item_names)
        self.assertNotIn("Mega Mushroom Permit", item_names)
        self.assertNotIn("Mushroom Permit", item_names)
        self.assertNotIn("Fire Flower Permit", item_names)
        self.assertNotIn("Touchscreen Pocket Permit", item_names)


class TestMajorPowerupLicenses(NSMBDSTestBase):
    options = {
        "license_mushroom": False,
        "license_fire_flower": False,
        "license_touchscreen_pocket": False,
        "tower_castle_keys": False,
    }

    def test_mega_license_is_added(self) -> None:
        item_names = [item.name for item in self.multiworld.get_items()]
        self.assertIn("Mega Mushroom Permit", item_names)
        self.assertNotIn("Mushroom Permit", item_names)
        self.assertNotIn("Fire Flower Permit", item_names)
        self.assertNotIn("Touchscreen Pocket Permit", item_names)


class TestFullPowerupLicenses(NSMBDSTestBase):
    options = {
        "tower_castle_keys": False,
    }

    def test_all_licenses_are_added(self) -> None:
        item_names = [item.name for item in self.multiworld.get_items()]
        for item_name in (
            "Mini Mushroom Permit",
            "Blue Shell Permit",
            "Mega Mushroom Permit",
            "Mushroom Permit",
            "Fire Flower Permit",
            "Touchscreen Pocket Permit",
        ):
            self.assertIn(item_name, item_names)


class TestProgressiveStarCoinGatesEnabled(NSMBDSTestBase):
    """Test the complete progressive Gate Permit catalog."""

    options = {
        "star_coin_gate_mode": "progressive",
        "tower_castle_keys": False,
    }

    def test_permits_in_item_pool(self) -> None:
        """The pool needs exactly one progressive copy per verified gate."""
        item_names = [item.name for item in self.multiworld.get_items()]
        self.assertEqual(item_names.count("Progressive Gate Pass"), 32)

    def test_required_gate_currency_stays_outside_progressive_gates(self) -> None:
        self.assertFalse(advancement_star_coins_behind_gates(self))


class TestIndividualStarCoinGatesEnabled(NSMBDSTestBase):
    """Test all explicitly assigned individual Permit items."""

    options = {
        "star_coin_gate_mode": "individual",
        "tower_castle_keys": False,
    }

    def test_individual_permits_in_item_pool(self) -> None:
        item_names = [item.name for item in self.multiworld.get_items()]
        from ..data.star_coin_gates import STAR_COIN_GATES

        expected = {gate.permit_item_name for gate in STAR_COIN_GATES}
        self.assertEqual({name for name in item_names if name in expected}, expected)
        self.assertNotIn("Progressive Gate Pass", item_names)

    def test_required_gate_currency_stays_outside_individual_gates(self) -> None:
        self.assertFalse(advancement_star_coins_behind_gates(self))


class TestAdvancedLocationsNonProgression(NSMBDSTestBase):
    options = {
        "advanced_location_item_placement": "non_progression",
        "blocksanity": True,
        "one_up_block_checks": True,
        "blocksanity_item_placement": "progression",
        "one_up_block_item_placement": "progression",
        "world_6_2_bonus_area": False,
    }

    def test_advanced_locations_reject_progression(self) -> None:
        from ..data.logic_data import ADVANCED_LOCATION_NAMES

        progression = self.world.create_item("Desert Pass")
        active = [
            location for location in self.multiworld.get_locations(self.player)
            if location.name in ADVANCED_LOCATION_NAMES
        ]
        self.assertTrue(active)
        self.assertTrue(all(
            getattr(location, "is_non_progression_only", False)
            and not location.item_rule(progression)
            for location in active
        ))
