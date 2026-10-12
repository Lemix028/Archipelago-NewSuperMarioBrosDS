"""Permit deadlines in real seeds and controlled multiworld sphere chains."""

from collections import Counter
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest import TestCase

from BaseClasses import CollectionState, ItemClassification, Location, LocationProgressType, Region
from Fill import balance_multiworld_progression, distribute_items_restrictive, swap_location_item
from Options import OptionError
from test.general import gen_steps, setup_multiworld
from worlds.AutoWorld import call_all
from worlds.generic.Rules import locality_rules

from .. import NSMBDSWorld
from ..early_powerup_permits import (
    permit_check_spheres,
    prepare_early_powerup_permits,
    validate_early_powerup_permits,
)
from ..items import NSMBDSItem
from ..options import PowerupPermitPlacement, SelectedPowerupPermits

ALL_PERMITS = sorted(SelectedPowerupPermits.valid_keys)
ALL_LICENSES = {
    "license_mushroom": True,
    "license_fire_flower": True,
    "license_mini_mushroom": True,
    "license_blue_shell": True,
    "license_mega_mushroom": True,
    "license_touchscreen_pocket": True,
}


def generate(options, seed=1337, players=1, link=False):
    mw = setup_multiworld(
        [NSMBDSWorld] * players, steps=("generate_early",), seed=seed, options=options,
    )
    for player in mw.player_ids:
        for name, count in mw.worlds[player].options.start_inventory.value.items():
            for _ in range(count):
                mw.push_precollected(mw.worlds[player].create_item(name))
    for step in gen_steps[1:]:
        call_all(mw, step)
    if link:
        mw.link_items()
    locality_rules(mw)
    distribute_items_restrictive(mw)
    call_all(mw, "post_fill")
    if players > 1:
        balance_multiworld_progression(mw)
    call_all(mw, "finalize_multiworld")
    call_all(mw, "pre_output")
    return mw


def chain(mode="early", permits=ALL_PERMITS, players=1, overrides=None):
    """Seven spheres with filler targets and all selected permits in sphere seven."""
    options = {
        **ALL_LICENSES,
        "powerup_permit_placement": mode,
        "selected_powerup_permits": permits,
        **(overrides or {}),
    }
    mw = setup_multiworld(
        [NSMBDSWorld] * players, steps=("generate_early",), seed=1337,
        options=[options] + [{}] * (players - 1),
    )
    for player in mw.player_ids:
        previous = None
        for number in range(1, 8):
            region = Region("Menu" if number == 1 else f"Sphere {number}", player, mw)
            mw.regions.append(region)
            if previous:
                previous.connect(region, rule=lambda state, n=number - 1, p=player: state.has(f"Bridge {n}", p))
            previous = region
            for index in range(7):
                location = Location(player, f"Sphere {number} Check {index}", player * 1000 + number * 10 + index, region)
                region.locations.append(location)
                if index == 0 and number < 7:
                    item = NSMBDSItem(f"Bridge {number}", ItemClassification.progression, 0xF00000 + number, player)
                else:
                    item = mw.worlds[player].create_item("Small Coin Bundle")
                location.item = item
                item.location = location
    # Put the permits in the other game when testing non-local placement.
    source_player = players
    for index, name in enumerate(permits, 1):
        location = mw.get_location(f"Sphere 7 Check {index}", source_player)
        location.item.location = None
        location.item = mw.worlds[1].create_item(name)
        location.item.location = location
    return mw


class TestEarlyPermitOptions(TestCase):
    def test_world_loads_when_core_fill_is_imported_first(self):
        result = subprocess.run(
            [sys.executable, "-c", "import unittest; import Fill; from worlds.nsmbds import NSMBDSWorld; "
             "from worlds.AutoWorld import AutoWorldRegister; "
             "assert AutoWorldRegister.world_types[NSMBDSWorld.game] is NSMBDSWorld"],
            env={**os.environ, "AP_TEST_WORLDS": "nsmbds", "SKIP_REQUIREMENTS_UPDATE": "1"},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_defaults_and_normal_do_not_change_generation(self):
        mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337)
        self.assertEqual(mw.worlds[1].options.powerup_permit_placement.value, 0)
        self.assertEqual(mw.worlds[1].options.selected_powerup_permits.value, {
            "Mushroom Permit", "Fire Flower Permit", "Touchscreen Pocket Permit",
        })
        self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {})
        self.assertEqual(mw.early_items[1], {})
        configured = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
            "selected_powerup_permits": ALL_PERMITS,
        })
        self.assertEqual(configured.worlds[1].early_powerup_permit_deadlines, {})
        self.assertEqual(configured.worlds[1].random.getstate(), mw.worlds[1].random.getstate())

    def test_selection_rejects_consumables_and_unknown_names(self):
        for invalid in ("Fire Flower", "Super Mushroom Permit", "Desert Pass"):
            with self.subTest(invalid=invalid), self.assertRaises(OptionError):
                SelectedPowerupPermits.from_any([invalid]).verify_keys()

    def test_early_assigns_sphere_two_to_every_selected_permit(self):
        options = {**ALL_LICENSES, "powerup_permit_placement": "early", "selected_powerup_permits": ALL_PERMITS}
        first = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options=options)
        second = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
            **options, "selected_powerup_permits": list(reversed(ALL_PERMITS)),
        })
        self.assertEqual(first.worlds[1].early_powerup_permit_deadlines, dict.fromkeys(ALL_PERMITS, 2))
        self.assertEqual(first.worlds[1].early_powerup_permit_deadlines, second.worlds[1].early_powerup_permit_deadlines)
        self.assertEqual(first.early_items[1], dict.fromkeys(ALL_PERMITS, 1))
        self.assertEqual(first.worlds[1].random.getstate(), second.worlds[1].random.getstate())

    def test_progressive_mode_is_rejected(self):
        with self.assertRaises((KeyError, ValueError)):
            PowerupPermitPlacement.from_any("progressive")

    def test_disabled_and_starting_permits_do_not_take_deadline_slots(self):
        with self.assertLogs(level="WARNING") as logs:
            mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
                "powerup_permit_placement": "early",
                "selected_powerup_permits": ["Mini Mushroom Permit", "Fire Flower Permit", "Touchscreen Pocket Permit"],
                "license_mini_mushroom": False,
                "start_inventory": {"Fire Flower Permit": 1},
            })
        self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {})
        self.assertEqual(mw.early_items[1], {})
        self.assertTrue(any("Mini Mushroom Permit" in line for line in logs.output))
        self.assertTrue(any("Touchscreen Pocket Permit" in line for line in logs.output))

    def test_optional_start_inventory_from_pool_is_also_satisfied(self):
        mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
            "powerup_permit_placement": "early", "selected_powerup_permits": ["Fire Flower Permit"],
        })
        mw.early_items[1].clear()
        mw.worlds[1].options.start_inventory_from_pool = SimpleNamespace(value={"Fire Flower Permit": 1})
        prepare_early_powerup_permits(mw.worlds[1])
        self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {})
        self.assertEqual(mw.early_items[1], {})

    def test_empty_selection_needs_no_placements(self):
        for mode in ("normal", "early"):
            mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
                "powerup_permit_placement": mode,
                "selected_powerup_permits": [],
            })
            self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {})

    def test_early_uses_default_selection_with_enabled_licenses(self):
        mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
            **ALL_LICENSES, "powerup_permit_placement": "early",
        })
        self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {
            "Mushroom Permit": 2, "Fire Flower Permit": 2, "Touchscreen Pocket Permit": 2,
        })


class TestPermitSpherePlacement(TestCase):
    def test_early_repairs_late_permits_without_changing_item_pool(self):
        mw = chain()
        before = Counter((location.item.name, location.item.player) for location in mw.get_filled_locations())
        self.assertFalse(any(location.item.name in ALL_PERMITS for location in permit_check_spheres(mw)))
        call_all(mw, "finalize_multiworld")
        spheres = permit_check_spheres(mw)
        for name, deadline in mw.worlds[1].early_powerup_permit_deadlines.items():
            location = mw.find_item(name, 1)
            self.assertLessEqual(spheres[location], deadline)
            self.assertTrue(location.locked)
        self.assertEqual(before, Counter((location.item.name, location.item.player) for location in mw.get_filled_locations()))
        self.assertTrue(mw.fulfills_accessibility())
        call_all(mw, "pre_output")

    def test_early_repairs_all_selected_permits_within_two_spheres(self):
        mw = chain(mode="early")
        call_all(mw, "finalize_multiworld")
        spheres = permit_check_spheres(mw)
        self.assertTrue(all(spheres[mw.find_item(name, 1)] <= 2 for name in ALL_PERMITS))

    def test_non_local_targets_can_be_in_another_players_game(self):
        mw = chain(players=2, overrides={"non_local_items": ALL_PERMITS})
        call_all(mw, "finalize_multiworld")
        for name in ALL_PERMITS:
            self.assertEqual(mw.find_item(name, 1).player, 2)
        validate_early_powerup_permits(mw, [mw.worlds[1]])

    def test_local_setting_is_preserved(self):
        mw = chain(players=2, overrides={"local_items": ALL_PERMITS})
        call_all(mw, "finalize_multiworld")
        for name in ALL_PERMITS:
            self.assertEqual(mw.find_item(name, 1).player, 1)

    def test_earlier_fixed_placement_is_allowed(self):
        mw = chain(permits=["Fire Flower Permit"])
        source = mw.find_item("Fire Flower Permit", 1)
        target = mw.get_location("Sphere 1 Check 1", 1)
        swap_location_item(source, target)
        target.locked = True
        call_all(mw, "finalize_multiworld")
        self.assertIs(mw.find_item("Fire Flower Permit", 1), target)

    def test_late_plando_is_rejected_without_changing_it(self):
        mw = chain(permits=["Fire Flower Permit"])
        source = mw.find_item("Fire Flower Permit", 1)
        source.locked = True
        with self.assertRaisesRegex(ValueError, "Fire Flower Permit.*sphere 2.*fixed placement"):
            call_all(mw, "finalize_multiworld")
        self.assertIs(mw.find_item("Fire Flower Permit", 1), source)

    def test_item_rules_and_exclusions_can_prevent_early_placement(self):
        for restriction in ("item_rule", "excluded", "locked"):
            with self.subTest(restriction=restriction):
                mw = chain(permits=["Fire Flower Permit"])
                for location in permit_check_spheres(mw):
                    if restriction == "item_rule":
                        location.item_rule = lambda item: not item.advancement
                    elif restriction == "excluded":
                        location.progress_type = LocationProgressType.EXCLUDED
                    else:
                        location.locked = True
                with self.assertRaisesRegex(ValueError, "no legal early check"):
                    call_all(mw, "finalize_multiworld")

    def test_progression_swap_fallback_preserves_accessibility(self):
        mw = chain(permits=["Fire Flower Permit"])
        for location in permit_check_spheres(mw):
            if location.item.name.startswith("Bridge"):
                continue
            location.item = NSMBDSItem("Desert Pass", ItemClassification.progression, 0xE50000, 1)
            location.item.location = location
        call_all(mw, "finalize_multiworld")
        self.assertLessEqual(permit_check_spheres(mw)[mw.find_item("Fire Flower Permit", 1)], 2)
        self.assertTrue(mw.fulfills_accessibility())
        self.assertEqual(mw.get_location("Sphere 1 Check 0", 1).item.name, "Bridge 1")

    def test_events_do_not_consume_extra_check_spheres(self):
        mw = chain(permits=["Fire Flower Permit"])
        start = mw.get_region("Menu", 1)
        region = mw.get_region("Sphere 2", 1)
        start.exits[0].access_rule = lambda state: state.has("Route Clear", 1)
        event = Location(1, "Route Event", None, start)
        start.locations.append(event)
        event.place_locked_item(NSMBDSItem("Route Clear", ItemClassification.progression, None, 1))
        self.assertEqual(permit_check_spheres(mw)[region.locations[1]], 1)

    def test_unreachable_tail_is_never_counted_as_early(self):
        mw = chain(permits=["Fire Flower Permit"])
        mw.get_region("Menu", 1).exits[0].access_rule = lambda state: False
        self.assertNotIn(mw.find_item("Fire Flower Permit", 1), permit_check_spheres(mw))

    def test_missing_permit_has_actionable_error(self):
        mw = chain(permits=["Fire Flower Permit"])
        location = mw.find_item("Fire Flower Permit", 1)
        location.item = mw.worlds[1].create_item("Small Coin Bundle")
        location.item.location = location
        with self.assertRaisesRegex(ValueError, "Fire Flower Permit.*no copy exists"):
            call_all(mw, "finalize_multiworld")

    def test_starting_permit_satisfies_an_existing_deadline(self):
        mw = chain(permits=["Fire Flower Permit"])
        mw.push_precollected(mw.worlds[1].create_item("Fire Flower Permit"))
        mw.find_item("Fire Flower Permit", 1).locked = True
        call_all(mw, "finalize_multiworld")

    def test_final_check_catches_changes_from_later_hooks(self):
        mw = chain(permits=["Fire Flower Permit"])
        call_all(mw, "finalize_multiworld")
        source = mw.find_item("Fire Flower Permit", 1)
        swap_location_item(source, mw.get_location("Sphere 7 Check 2", 1), check_locked=False)
        with self.assertRaisesRegex(ValueError, "completed seed does not satisfy"):
            call_all(mw, "pre_output")


class TestEarlyPermitGeneration(TestCase):
    def test_real_seeds_with_all_six_permits_and_level_shuffle(self):
        for seed in (0, 42, 1337):
            with self.subTest(seed=seed):
                mw = generate({
                    **ALL_LICENSES,
                    "powerup_permit_placement": "early",
                    "selected_powerup_permits": ALL_PERMITS,
                    "level_randomization": "global",
                }, seed=seed)
                spheres = permit_check_spheres(mw)
                for name, deadline in mw.worlds[1].early_powerup_permit_deadlines.items():
                    self.assertLessEqual(spheres[mw.find_item(name, 1)], deadline)
                    self.assertEqual(sum(location.item.name == name for location in mw.get_filled_locations()), 1)
                self.assertTrue(mw.fulfills_accessibility())

    def test_two_players_with_normal_and_early_non_local_permits(self):
        mw = generate([
            {**ALL_LICENSES, "powerup_permit_placement": "early", "selected_powerup_permits": ALL_PERMITS,
             "non_local_items": ALL_PERMITS},
            {**ALL_LICENSES, "powerup_permit_placement": "normal", "selected_powerup_permits": ALL_PERMITS,
             "non_local_items": ALL_PERMITS},
        ], players=2)
        for player in mw.player_ids:
            for name in ALL_PERMITS:
                self.assertNotEqual(mw.find_item(name, player).player, player)
        self.assertTrue(mw.fulfills_accessibility())

    def test_item_linked_permits_respect_early_placement(self):
        link = [{"name": "Shared Permits", "item_pool": ALL_PERMITS, "replacement_item": "Nothing",
                 "link_replacement": False}]
        mw = generate([
            {**ALL_LICENSES, "powerup_permit_placement": "early", "selected_powerup_permits": ALL_PERMITS,
             "item_links": link},
            {**ALL_LICENSES, "powerup_permit_placement": "early", "selected_powerup_permits": ALL_PERMITS,
             "item_links": link},
        ], players=2, link=True)
        validate_early_powerup_permits(mw, list(mw.get_game_worlds(NSMBDSWorld.game)))
        self.assertTrue(mw.fulfills_accessibility())

    def test_start_inventory_and_slot_data_round_trip(self):
        mw = generate({
            "powerup_permit_placement": "early",
            "selected_powerup_permits": ["Fire Flower Permit", "Mini Mushroom Permit"],
            "start_inventory": {"Fire Flower Permit": 1},
        })
        self.assertEqual(mw.worlds[1].early_powerup_permit_deadlines, {"Mini Mushroom Permit": 2})
        self.assertTrue(CollectionState(mw).has("Fire Flower Permit", 1))
        data = mw.worlds[1].fill_slot_data()
        self.assertEqual(data["options"]["powerup_permit_placement"], PowerupPermitPlacement.option_early)
        self.assertEqual(data["options"]["selected_powerup_permits"], {"Fire Flower Permit", "Mini Mushroom Permit"})
        tracker = setup_multiworld(NSMBDSWorld, steps=(), seed=1337)
        tracker.re_gen_passthrough = {NSMBDSWorld.game: data}
        for step in gen_steps:
            call_all(tracker, step)
        self.assertEqual(tracker.worlds[1].options.selected_powerup_permits.value, data["options"]["selected_powerup_permits"])
        self.assertEqual(tracker.worlds[1].early_powerup_permit_deadlines, {})
        self.assertEqual(tracker.early_items[1], {})
