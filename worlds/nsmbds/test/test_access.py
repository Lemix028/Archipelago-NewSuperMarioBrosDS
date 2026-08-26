"""Unit tests for NSMBDS item access rules and logic dependencies."""

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
        self.assertFalse(self.can_reach_location("World 1-1 Star Coin 3"))
        self.collect_by_name("Fire Flower Permit")
        self.assertTrue(self.can_reach_location("World 1-1 Star Coin 3"))

    def test_world_3_a_accepts_mini_or_mega(self) -> None:
        self.collect_by_name(["Desert Pass", "Isle Pass"] + ["Star Coin"] * 5)
        self.assertFalse(self.can_reach_location("World 3-A Star Coin 3"))
        self.collect_by_name("Mega Mushroom Permit")
        self.assertTrue(self.can_reach_location("World 3-A Star Coin 3"))

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


class TestProgressiveStarCoinGateAccess(NSMBDSTestBase):
    """Test locations moved behind the global progressive Gate order."""

    options = {
        "star_coin_gate_mode": "progressive",
        "tower_castle_keys": False,
    }

    def test_first_gate_requires_one_permit(self) -> None:
        self.assertFalse(self.can_reach_location("World 1 Green Toad House 1 Goal"))
        self.collect_n_by_name("Progressive Gate Pass", 1)
        self.collect_n_by_name("Star Coin", 5)
        self.assertTrue(self.can_reach_location("World 1 Green Toad House 1 Goal"))
        self.assertFalse(self.can_reach_location("World 1 Orange Toad House Goal"))

    def test_third_gate_requires_three_permits(self) -> None:
        self.collect_n_by_name("Progressive Gate Pass", 3)
        self.collect_n_by_name("Star Coin", 5)
        self.assertTrue(self.can_reach_location("World 1-A Goal"))

    def test_fifth_gate_enters_world_two_mask(self) -> None:
        self.collect_by_name("Desert Pass")
        self.collect_n_by_name("Star Coin", 5)
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

    def test_green_house_one_permit_does_not_open_orange_house(self) -> None:
        self.collect_by_name(["World 1 Green Toad House 1 Gate Pass"] + ["Star Coin"] * 5)
        self.assertTrue(self.can_reach_location("World 1 Green Toad House 1 Goal"))
        self.assertFalse(self.can_reach_location("World 1 Orange Toad House Goal"))

    def test_world_one_a_requires_its_named_permit(self) -> None:
        self.collect_by_name(["World 1-A Gate Pass"] + ["Star Coin"] * 5)
        self.assertTrue(self.can_reach_location("World 1-A Goal"))

    def test_world_two_red_one_requires_its_named_permit(self) -> None:
        self.collect_by_name(["Desert Pass"] + ["Star Coin"] * 5)
        self.assertFalse(self.can_reach_location("World 2 Red Toad House 1 Goal"))
        self.collect_by_name("World 2 Red Toad House 1 Gate Pass")
        self.assertTrue(self.can_reach_location("World 2 Red Toad House 1 Goal"))

    def test_world_three_red_toad_house_requires_world_three_a_gate(self) -> None:
        self.collect_by_name(["Desert Pass", "Isle Pass"] + ["Star Coin"] * 5)
        self.assertFalse(self.can_reach_location("World 3 Red Toad House Goal"))
        self.collect_by_name("World 3-A Gate Pass")
        self.assertTrue(self.can_reach_location("World 3 Red Toad House Goal"))
