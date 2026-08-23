"""Catalog integrity tests for the stage-level NSMBDS logic graph."""

import unittest

from ..data.logic_data import (
    ADVANCED_LOCATION_NAMES,
    ALL_SECRET_EXITS,
    STAGE_ENTRY_REQUIREMENTS,
    TOAD_HOUSE_ENTRY_REQUIREMENTS,
)
from ..data.powerup_licenses import (
    POWERUP_ABILITY_REQUIREMENTS,
    POWERUP_ALTERNATIVE_REQUIREMENTS,
)
from ..data.star_coin_gates import STAR_COIN_GATES
from ..locations import (
    ACTIVE_STAGE_DEFINITIONS,
    ALL_ACTIVE_DEFINITIONS,
    BOSS_LOCATION_COMPLETION_SOURCES,
    BOSS_LOCATION_NAMES,
    LOCATION_TABLE,
    LocationKind,
)
from ..regions import REGION_LIST, REGION_LOCATIONS


class TestLogicCatalog(unittest.TestCase):
    def test_every_stage_and_toad_house_has_an_entry_rule(self) -> None:
        self.assertEqual(
            set(STAGE_ENTRY_REQUIREMENTS),
            {definition.name for definition in ACTIVE_STAGE_DEFINITIONS},
        )
        self.assertEqual(
            set(TOAD_HOUSE_ENTRY_REQUIREMENTS),
            {
                definition.name for definition in ALL_ACTIVE_DEFINITIONS
                if definition.kind is LocationKind.STATIC_TOAD_HOUSE
            },
        )

    def test_every_logic_reference_is_a_real_location(self) -> None:
        route_references = {
            atom
            for requirement in (
                *STAGE_ENTRY_REQUIREMENTS.values(),
                *TOAD_HOUSE_ENTRY_REQUIREMENTS.values(),
            )
            for alternative in requirement
            for atom in alternative
        }
        powerup_references = {
            name
            for requirement in POWERUP_ABILITY_REQUIREMENTS
            for name in requirement.locations
        } | {
            name
            for requirement in POWERUP_ALTERNATIVE_REQUIREMENTS
            for name in requirement.locations
        }
        self.assertLessEqual(
            {reference for reference in route_references if not reference.startswith("REGION:")},
            LOCATION_TABLE.keys(),
        )
        self.assertLessEqual(powerup_references, LOCATION_TABLE.keys())
        self.assertLessEqual(ADVANCED_LOCATION_NAMES, LOCATION_TABLE.keys())

    def test_all_locations_are_assigned_to_exactly_one_region(self) -> None:
        assigned = [name for names in REGION_LOCATIONS.values() for name in names]
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertEqual(set(assigned), set(LOCATION_TABLE))
        self.assertEqual(len(LOCATION_TABLE.values()), len(set(LOCATION_TABLE.values())))
        self.assertEqual(len(REGION_LIST), len(set(REGION_LIST)))

    def test_castle_boss_catalog_is_complete(self) -> None:
        self.assertEqual(len(BOSS_LOCATION_NAMES), 9)
        self.assertIn("World 8-Castle Dry Bowser Defeated", BOSS_LOCATION_NAMES)
        self.assertEqual(
            BOSS_LOCATION_COMPLETION_SOURCES["World 2-Castle Mummipokey Defeated"],
            ("World 2-Castle Goal", "World 2-Castle Secret Exit"),
        )
        self.assertTrue(all(
            source in LOCATION_TABLE
            for sources in BOSS_LOCATION_COMPLETION_SOURCES.values()
            for source in sources
        ))

    def test_secret_exit_and_gate_catalogs_are_complete(self) -> None:
        runtime_secret_exits = {
            name for name in LOCATION_TABLE if name.endswith(" Secret Exit")
        }
        self.assertEqual(ALL_SECRET_EXITS, runtime_secret_exits)
        self.assertEqual(len(STAR_COIN_GATES), 32)
        gate_targets = {gate.target_stage_name for gate in STAR_COIN_GATES}
        self.assertIn("World 2 Red Toad House 3", gate_targets)
        self.assertNotIn("World 2 Red Toad House 2", gate_targets)
