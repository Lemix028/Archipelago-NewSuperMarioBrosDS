"""Semantic regression tests for Universal Tracker-compatible rules."""

from typing import ClassVar, cast
from unittest import TestCase

from rule_builder.rules import Rule, True_

from ..rules import _alternative_rule
from .bases import NSMBDSTestBase


class TestRequirementConversion(TestCase):
    def test_empty_alternative_is_explicitly_true(self) -> None:
        self.assertIsInstance(_alternative_rule(()), True_)


class TestRuleExplanations(NSMBDSTestBase):
    options: ClassVar[dict[str, object]] = {
        "goal": "world_tour",
        "star_coin_gate_mode": "progressive",
        "tower_castle_keys": True,
    }

    def assert_resolved_rule(self, rule: object) -> Rule.Resolved:
        self.assertIsInstance(rule, Rule.Resolved)
        return cast(Rule.Resolved, rule)

    def test_world_access_exposes_pass_and_route_dependencies(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.get_entrance("Menu -> World 5", self.player).access_rule
        )
        self.assertIn("Glacier Pass", rule.item_dependencies())
        self.assertIn("World 3-Castle Goal", rule.location_dependencies())
        self.assertIn("World 1-Tower Secret Exit", rule.location_dependencies())

    def test_stage_access_exposes_route_and_tower_key(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.get_entrance("World 5 -> World 5-Tower", self.player).access_rule
        )
        self.assertIn("Glacier Tower Key", rule.item_dependencies())
        self.assertIn("World 5-2 Goal", rule.location_dependencies())
        explanation = rule.explain_str(self.multiworld.state)
        self.assertIn("Glacier Tower Key", explanation)
        self.assertIn("World 5-2 Goal", explanation)

    def test_powerup_alternatives_remain_structured(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.get_location("World 1-1 Star Coin 3", self.player).access_rule
        )
        for permit in (
            "Mushroom Permit",
            "Fire Flower Permit",
            "Blue Shell Permit",
            "Mega Mushroom Permit",
        ):
            self.assertIn(permit, rule.item_dependencies())
            self.assertIn(permit, rule.explain_str(self.multiworld.state))

    def test_progressive_gate_explains_exact_cost_and_index(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.get_entrance(
                "World 3 -> World 3 Gate: World 3-A", self.player
            ).access_rule
        )
        explanation = rule.explain_str(self.multiworld.state)
        self.assertIn("Star Coin x45", explanation)
        self.assertIn("Progressive Gate Pass x9", explanation)

    def test_boss_rule_exposes_both_castle_exits(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.get_location(
                "World 2-Castle Mummipokey Defeated", self.player
            ).access_rule
        )
        self.assertEqual(
            set(rule.location_dependencies()),
            {"World 2-Castle Goal", "World 2-Castle Secret Exit"},
        )

    def test_completion_rule_exposes_every_boss(self) -> None:
        rule = self.assert_resolved_rule(
            self.multiworld.completion_condition[self.player]
        )
        self.assertEqual(
            set(rule.location_dependencies()),
            set(self.world._boss_location_names),
        )


class TestDisabledRouteRuleExplanations(NSMBDSTestBase):
    options: ClassVar[dict[str, object]] = {
        "cannon_route_logic": False,
        "secret_exit_world_unlock_logic": False,
        "tower_castle_keys": False,
    }

    def test_disabled_routes_and_keys_are_absent_from_dependencies(self) -> None:
        world_rule = self.multiworld.get_entrance(
            "Menu -> World 5", self.player
        ).access_rule
        tower_rule = self.multiworld.get_entrance(
            "World 5 -> World 5-Tower", self.player
        ).access_rule
        self.assertIsInstance(world_rule, Rule.Resolved)
        self.assertIsInstance(tower_rule, Rule.Resolved)
        self.assertNotIn("World 1-Tower Secret Exit", world_rule.location_dependencies())
        self.assertNotIn("Glacier Tower Key", tower_rule.item_dependencies())


class TestIndividualGateRuleExplanations(NSMBDSTestBase):
    options: ClassVar[dict[str, object]] = {
        "star_coin_gate_mode": "individual",
        "tower_castle_keys": False,
    }

    def test_individual_gate_names_its_own_pass(self) -> None:
        rule = self.multiworld.get_entrance(
            "World 1 -> World 1 Gate: World 1 Orange Toad House", self.player
        ).access_rule
        self.assertIsInstance(rule, Rule.Resolved)
        self.assertEqual(
            set(rule.item_dependencies()),
            {"Star Coin", "World 1 Orange Toad House Gate Pass"},
        )
