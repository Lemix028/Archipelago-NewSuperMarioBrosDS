"""Unit tests for NSMBDS item access rules and logic dependencies."""

from ..data.star_coin_gates import STAR_COIN_GATES
from .bases import NSMBDSTestBase


class TestWorldAccessRules(NSMBDSTestBase):
    """Test destination Passes and their equivalent vanilla routes."""

    options = {
        "goal": "defeat_bowser",
        "tower_castle_keys": False,
    }

    def test_world_2_access(self) -> None:
        """World 2 access requires World 2 Access item."""
        self.collect_by_name("Desert Pass")
        self.assertTrue(self.can_reach_region("World 2"))

    def test_world_4_access(self) -> None:
        """Jungle Pass bypasses the Mini-Mario route into World 4."""
        self.collect_by_name("Desert Pass")
        self.collect_by_name("Jungle Pass")
        self.assertTrue(self.can_reach_region("World 4"))

    def test_world_5_warp_access(self) -> None:
        """Glacier Pass bypasses the Blue-Shell cannon route into World 5."""
        self.collect_by_name("Glacier Pass")
        self.assertTrue(self.can_reach_region("World 5"))


class TestStarCoinGoalFinalCastleAccess(NSMBDSTestBase):
    """Star Coin targets must not lock checks inside Bowser's Castle."""

    options = {
        "goal": "star_coin_hunt",
        "required_star_coins": 240,
        "tower_castle_keys": False,
    }

    def test_final_castle_does_not_require_star_coin_target(self) -> None:
        self.collect_by_name("Volcano Pass")
        self.assertEqual(self.count("Star Coin"), 0)
        self.assertTrue(self.can_reach_location("World 8-Bowser's Castle Goal"))


class TestCompletionistFinalCastleAccess(NSMBDSTestBase):
    """Completionist permits collecting final-castle checks before its Coin goal."""

    options = {
        "goal": "completionist",
        "required_star_coins": 240,
        "tower_castle_keys": False,
    }

    def test_final_castle_does_not_require_star_coin_target(self) -> None:
        self.collect_by_name("Volcano Pass")
        self.assertEqual(self.count("Star Coin"), 0)
        self.assertTrue(self.can_reach_location("World 8-Bowser's Castle Goal"))


class TestWorldTourFinalBowserAccess(NSMBDSTestBase):
    options = {
        "goal": "world_tour",
        "tower_castle_keys": False,
    }

    def test_final_bowser_is_independent_of_other_world_bosses(self) -> None:
        self.collect_by_name("Volcano Pass")
        self.assertTrue(self.can_reach_location(
            "World 8-Bowser's Castle Bowser & Bowser Jr. Defeated"
        ))


class TestVanillaWorldRoutes(NSMBDSTestBase):
    """Test normal exits, alternate boss exits, and Warp Cannons."""

    options = {
        "goal": "defeat_bowser",
        "tower_castle_keys": True,
    }

    def test_world_five_castle_goal_opens_world_six(self) -> None:
        self.collect_by_name([
            "Glacier Pass",
            "Glacier Tower Key",
            "Glacier Castle Key",
        ])
        self.assertTrue(self.can_reach_location("World 5-Castle Goal"))
        self.assertTrue(self.can_reach_region("World 6"))

    def test_world_five_castle_secret_exit_opens_world_seven(self) -> None:
        self.collect_by_name([
            "Glacier Pass",
            "Glacier Tower Key",
            "Glacier Castle Key",
            "Mini Mushroom Permit",
        ])
        self.assertTrue(self.can_reach_location("World 5-Castle Secret Exit"))
        self.assertTrue(self.can_reach_region("World 7"))

    def test_world_one_cannon_opens_world_five(self) -> None:
        self.collect_by_name([
            "Grassland Tower Key",
            "Blue Shell Permit",
        ])
        self.assertTrue(self.can_reach_location("World 1-Tower Secret Exit"))
        self.assertTrue(self.can_reach_region("World 5"))


class TestSecretExitAccessRules(NSMBDSTestBase):
    """Test location access rules for secret exits requiring permits."""

    options = {
        "secret_exit_checks": True,
        "tower_castle_keys": False,
    }

    def test_mini_mushroom_secret_exits(self) -> None:
        """Mini Mushroom Permit is required for Mini Mushroom secret exits."""
        self.collect_by_name(["Desert Pass", "Jungle Pass", "Mini Mushroom Permit"])
        self.assertTrue(self.can_reach_location("World 2-4 Secret Exit"))

    def test_blue_shell_secret_exits(self) -> None:
        """Blue Shell Permit is required for Blue Shell secret exits."""
        self.collect_by_name("Blue Shell Permit")
        self.assertTrue(self.can_reach_location("World 1-Tower Secret Exit"))


class TestStarCoinPowerupAccessRules(NSMBDSTestBase):
    """Test strict form requirements for individual Star Coins."""

    options = {
        "tower_castle_keys": False,
    }

    def test_mini_mushroom_star_coin(self) -> None:
        self.collect_by_name(["Desert Pass", "Mini Mushroom Permit"])
        self.assertTrue(self.can_reach_location("World 2-Castle Star Coin 3"))

    def test_blue_shell_star_coin(self) -> None:
        self.collect_by_name(["Desert Pass", "Isle Pass", "Blue Shell Permit"])
        self.assertTrue(self.can_reach_location("World 3-Ghost House Star Coin 3"))

    def test_large_mario_accepts_any_large_form_permit(self) -> None:
        permits = (
            "Mushroom Permit",
            "Fire Flower Permit",
            "Blue Shell Permit",
            "Mega Mushroom Permit",
        )
        for permit in permits:
            with self.subTest(permit=permit):
                self.assertFalse(self.can_reach_location("World 1-1 Star Coin 3"))
                self.collect_by_name(permit)
                self.assertTrue(self.can_reach_location("World 1-1 Star Coin 3"))
                self.remove_by_name(permit)

    def test_world_3_1_star_coin_3_needs_no_large_form(self) -> None:
        self.collect_by_name("Isle Pass")
        self.assertTrue(self.can_reach_location("World 3-1 Star Coin 3"))

    def test_world_3_a_requires_mini(self) -> None:
        self.collect_by_name(["Desert Pass", "Isle Pass"] + ["Star Coin"] * 5)
        self.assertFalse(self.can_reach_location("World 3-A Star Coin 3"))
        self.collect_by_name("Mega Mushroom Permit")
        self.assertFalse(self.can_reach_location("World 3-A Star Coin 3"))
        self.collect_by_name("Mini Mushroom Permit")
        self.assertTrue(self.can_reach_location("World 3-A Star Coin 3"))

    def test_powerup_rule_is_explainable(self) -> None:
        location = self.multiworld.get_location("World 3-A Star Coin 3", self.player)
        self.assertEqual(
            location.access_rule.explain_str(self.multiworld.state),
            "Missing Mini Mushroom Permit",
        )

    def test_world_7_5_requires_mini(self) -> None:
        self.collect_by_name([
            "Desert Pass",
            "Jungle Pass",
            "Cloud Pass",
            "Mini Mushroom Permit",
        ])
        self.assertTrue(self.can_reach_location("World 7-5 Star Coin 2"))


class TestOptionalRouteLogic(NSMBDSTestBase):
    options = {
        "tower_castle_keys": False,
        "secret_exit_shortcut_logic": False,
        "secret_exit_world_unlock_logic": False,
        "cannon_route_logic": False,
    }

    def test_internal_secret_path_remains_usable_but_nonprogression(self) -> None:
        self.collect_by_name(["Desert Pass", "Mini Mushroom Permit"])
        self.assertTrue(self.can_reach_location("World 2-3 Secret Exit"))
        self.assertTrue(self.can_reach_location("World 2-A Goal"))
        location = self.multiworld.get_location("World 2-A Goal", self.player)
        self.assertFalse(location.item_rule(self.world.create_item("Desert Pass")))

    def test_alternate_castle_exit_does_not_open_world_four(self) -> None:
        self.collect_by_name(["Desert Pass", "Mini Mushroom Permit"])
        self.assertTrue(self.can_reach_location("World 2-Castle Secret Exit"))
        self.assertFalse(self.can_reach_region("World 4"))

    def test_checks_behind_ignored_routes_are_nonprogression(self) -> None:
        progression = self.world.create_item("Desert Pass")
        for name in ("World 3 Green Toad House Goal", "World 5 Red Toad House Goal"):
            location = self.multiworld.get_location(name, self.player)
            self.assertFalse(location.item_rule(progression), name)

    def test_cannon_exit_remains_usable_but_nonprogression(self) -> None:
        self.collect_by_name("Blue Shell Permit")
        self.assertTrue(self.can_reach_location("World 1-Tower Secret Exit"))
        location = self.multiworld.get_location("World 1-Tower Secret Exit", self.player)
        self.assertFalse(location.item_rule(self.world.create_item("Desert Pass")))


class TestDisabledShortcutAccess(NSMBDSTestBase):
    options = {
        "tower_castle_keys": True,
        "secret_exit_shortcut_logic": False,
        "secret_exit_world_unlock_logic": False,
        "cannon_route_logic": False,
    }

    def test_world_five_main_route_waits_for_tower_key(self) -> None:
        self.collect_by_name("Glacier Pass")
        for name in ("World 5-3 Goal", "World 5-Ghost House Goal", "World 5-4 Goal"):
            self.assertFalse(self.can_reach_location(name), name)

        self.collect_by_name("Glacier Tower Key")
        for name in ("World 5-3 Goal", "World 5-Ghost House Goal", "World 5-4 Goal"):
            self.assertTrue(self.can_reach_location(name), name)

    def test_world_seven_main_route_uses_world_7_6_secret_exit(self) -> None:
        self.collect_by_name(["Cloud Pass", "Sky Castle Key", "Blue Shell Permit"])
        for name in ("World 7-6 Secret Exit", "World 7-7 Goal", "World 7-Castle Goal"):
            self.assertFalse(self.can_reach_location(name), name)

        self.collect_by_name("Sky Tower Key")
        for name in ("World 7-6 Secret Exit", "World 7-7 Goal", "World 7-Castle Goal"):
            self.assertTrue(self.can_reach_location(name), name)

        self.assertTrue(self.can_reach_location("World 7-A Goal"))
        location = self.multiworld.get_location("World 7-A Goal", self.player)
        self.assertFalse(location.item_rule(self.world.create_item("Cloud Pass")))


class TestPowerupLicensesDisabledAccess(NSMBDSTestBase):
    """Disabled License toggles remove Permit items and their access requirements."""

    options = {
        "license_mini_mushroom": False,
        "license_blue_shell": False,
        "license_mega_mushroom": False,
        "license_mushroom": False,
        "license_fire_flower": False,
        "license_touchscreen_pocket": False,
        "tower_castle_keys": False,
        "secret_exit_checks": True,
    }

    def test_world_route_needs_no_license(self) -> None:
        self.collect_by_name(["Desert Pass", "Jungle Pass"])
        self.assertTrue(self.can_reach_region("World 4"))

    def test_secret_exit_needs_no_license(self) -> None:
        self.collect_by_name(["Desert Pass", "Jungle Pass"])
        self.assertTrue(self.can_reach_location("World 2-4 Secret Exit"))

    def test_disabled_large_form_license_satisfies_alternative(self) -> None:
        self.assertTrue(self.can_reach_location("World 1-1 Star Coin 3"))


class TestProgressiveStarCoinGateAccess(NSMBDSTestBase):
    """Test locations moved behind the global progressive Gate order."""

    options = {
        "star_coin_gate_mode": "progressive",
        "tower_castle_keys": False,
    }

    def test_passes_and_cumulative_coin_budget_limit_progression(self) -> None:
        gates = STAR_COIN_GATES[:3]
        entrances = [
            f"{gate.source_region} -> {gate.region_name}" for gate in gates
        ]

        self.collect_n_by_name("Progressive Gate Pass", 1)
        self.collect_n_by_name("Star Coin", 5)
        self.assertTrue(self.can_reach_entrance(entrances[0]))
        self.assertFalse(self.can_reach_entrance(entrances[1]))

        self.collect_n_by_name("Progressive Gate Pass", 3)
        self.assertTrue(self.can_reach_entrance(entrances[0]))
        self.assertFalse(self.can_reach_entrance(entrances[1]))
        self.assertFalse(self.can_reach_entrance(entrances[2]))

        self.collect_n_by_name("Star Coin", 10)
        self.assertTrue(self.can_reach_entrance(entrances[0]))
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertFalse(self.can_reach_entrance(entrances[2]))

        self.collect_n_by_name("Star Coin", 15)
        self.assertTrue(self.can_reach_entrance(entrances[0]))
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertTrue(self.can_reach_entrance(entrances[2]))

    def test_fifth_gate_enters_world_two_mask(self) -> None:
        self.collect_by_name("Desert Pass")
        self.collect_n_by_name("Star Coin", 25)
        self.collect_n_by_name("Progressive Gate Pass", 4)
        self.assertFalse(self.can_reach_location("World 2 Red Toad House 1 Goal"))
        self.collect_n_by_name("Progressive Gate Pass", 5)
        self.assertTrue(self.can_reach_location("World 2 Red Toad House 1 Goal"))


class TestIndividualStarCoinGateAccess(NSMBDSTestBase):
    """Test that signs in different worlds accept only their assigned Pass."""

    options = {
        "star_coin_gate_mode": "individual",
        "tower_castle_keys": False,
    }

    def test_randomized_tiers_are_a_complete_non_catalog_permutation(self) -> None:
        tiers = self.world.individual_gate_tiers
        self.assertEqual(
            set(tiers),
            {gate.permit_item_name for gate in STAR_COIN_GATES},
        )
        self.assertEqual(set(tiers.values()), set(range(1, 33)))
        self.assertTrue(any(
            tiers[gate.permit_item_name] != gate.progressive_index
            for gate in STAR_COIN_GATES
        ))

    def test_named_permits_respect_their_cumulative_tiers(self) -> None:
        gates_by_tier = {
            tier: next(
                gate for gate in STAR_COIN_GATES
                if self.world.individual_gate_tiers[gate.permit_item_name] == tier
            )
            for tier in (1, 2, 3)
        }
        self.collect_by_name([
            "Desert Pass", "Isle Pass", "Jungle Pass", "Glacier Pass",
            "Mountain Pass", "Cloud Pass", "Volcano Pass",
            *(gate.permit_item_name for gate in gates_by_tier.values()),
        ])

        entrances = {
            tier: f"{gate.source_region} -> {gate.region_name}"
            for tier, gate in gates_by_tier.items()
        }
        self.collect_n_by_name("Star Coin", 5)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertFalse(self.can_reach_entrance(entrances[2]))
        self.assertFalse(self.can_reach_entrance(entrances[3]))

        self.collect_n_by_name("Star Coin", 10)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertTrue(self.can_reach_entrance(entrances[2]))
        self.assertFalse(self.can_reach_entrance(entrances[3]))

        self.collect_n_by_name("Star Coin", 15)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertTrue(self.can_reach_entrance(entrances[2]))
        self.assertTrue(self.can_reach_entrance(entrances[3]))

    def test_slot_data_restores_the_exact_tier_mapping(self) -> None:
        original = dict(self.world.individual_gate_tiers)
        slot_data = self.world.fill_slot_data()
        self.multiworld.re_gen_passthrough = {self.world.game: slot_data}
        self.world.individual_gate_tiers = {}

        self.world.generate_early()

        self.assertEqual(self.world.individual_gate_tiers, original)

    def test_old_slot_data_without_individual_tiers_is_rejected(self) -> None:
        slot_data = self.world.fill_slot_data()
        del slot_data["individual_gate_tiers"]
        self.multiworld.re_gen_passthrough = {self.world.game: slot_data}

        with self.assertRaisesRegex(ValueError, "missing required individual_gate_tiers"):
            self.world.generate_early()


class TestVanillaStarCoinGateAccess(NSMBDSTestBase):
    """Vanilla gates use randomized logical budgets without permit items."""

    options = {
        "star_coin_gate_mode": "vanilla",
        "tower_castle_keys": False,
    }

    def test_randomized_tiers_are_complete_and_require_no_gate_passes(self) -> None:
        self.assertEqual(
            set(self.world.vanilla_gate_tiers),
            {gate.name for gate in STAR_COIN_GATES},
        )
        self.assertEqual(
            set(self.world.vanilla_gate_tiers.values()),
            set(range(1, 33)),
        )
        item_names = {item.name for item in self.multiworld.get_items()}
        self.assertNotIn("Progressive Gate Pass", item_names)
        self.assertFalse(any(
            gate.permit_item_name in item_names for gate in STAR_COIN_GATES
        ))

    def test_vanilla_gate_logic_respects_cumulative_tiers(self) -> None:
        gates_by_tier = {
            tier: next(
                gate for gate in STAR_COIN_GATES
                if self.world.vanilla_gate_tiers[gate.name] == tier
            )
            for tier in (1, 2, 3)
        }
        self.collect_by_name([
            "Desert Pass", "Isle Pass", "Jungle Pass", "Glacier Pass",
            "Mountain Pass", "Cloud Pass", "Volcano Pass",
        ])
        entrances = {
            tier: f"{gate.source_region} -> {gate.region_name}"
            for tier, gate in gates_by_tier.items()
        }

        self.collect_n_by_name("Star Coin", 5)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertFalse(self.can_reach_entrance(entrances[2]))
        self.assertFalse(self.can_reach_entrance(entrances[3]))

        self.collect_n_by_name("Star Coin", 10)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertTrue(self.can_reach_entrance(entrances[2]))
        self.assertFalse(self.can_reach_entrance(entrances[3]))

        self.collect_n_by_name("Star Coin", 15)
        self.assertTrue(self.can_reach_entrance(entrances[1]))
        self.assertTrue(self.can_reach_entrance(entrances[2]))
        self.assertTrue(self.can_reach_entrance(entrances[3]))

    def test_slot_data_restores_the_exact_tier_mapping(self) -> None:
        original = dict(self.world.vanilla_gate_tiers)
        slot_data = self.world.fill_slot_data()
        self.multiworld.re_gen_passthrough = {self.world.game: slot_data}
        self.world.vanilla_gate_tiers = {}

        self.world.generate_early()

        self.assertEqual(self.world.vanilla_gate_tiers, original)

    def test_old_slot_data_without_vanilla_tiers_is_rejected(self) -> None:
        slot_data = self.world.fill_slot_data()
        del slot_data["vanilla_gate_tiers"]
        self.multiworld.re_gen_passthrough = {self.world.game: slot_data}

        with self.assertRaisesRegex(ValueError, "missing required vanilla_gate_tiers"):
            self.world.generate_early()
