"""Unit tests for NSMBDS goal options and accessibility conditions."""

from .bases import NSMBDSTestBase


class TestDefeatBowser(NSMBDSTestBase):
    options = {
        "goal": "defeat_bowser",
    }

    def test_fill_regression_seed_4380723837207189548(self) -> None:
        self.world_setup(seed=4380723837207189548)
        self.test_fill()


class TestStarCoinHunt(NSMBDSTestBase):
    options = {
        "goal": "star_coin_hunt",
        "required_star_coins": 50,
    }


class TestWorldTour(NSMBDSTestBase):
    options = {
        "goal": "world_tour",
    }


class TestCompletionist(NSMBDSTestBase):
    options = {
        "goal": "completionist",
        "required_star_coins": 80,
    }
