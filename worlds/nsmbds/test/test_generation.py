"""Representative Core generation profiles for NSMBDS."""

from .bases import NSMBDSTestBase


class TestMinimalGeneration(NSMBDSTestBase):
    options = {
        "goal": "defeat_bowser",
        "red_coin_checks": False,
        "one_up_block_checks": False,
        "blocksanity": False,
        "secret_exit_checks": False,
        "toad_house_checks": False,
        "tower_castle_keys": False,
        "star_coin_gate_mode": "vanilla",
        "trap_percentage": 0,
    }


class TestFullLocationGeneration(NSMBDSTestBase):
    options = {
        "goal": "completionist",
        "required_star_coins": 240,
        "red_coin_checks": True,
        "one_up_block_checks": True,
        "blocksanity": True,
        "world_6_2_bonus_area": True,
        "secret_exit_checks": True,
        "toad_house_checks": True,
        "star_coin_gate_mode": "individual",
        "trap_percentage": 50,
        "death_link": True,
    }


class TestProgressiveGeneration(NSMBDSTestBase):
    options = {
        "goal": "world_tour",
        "star_coin_gate_mode": "progressive",
        "tower_castle_keys": True,
        "blocksanity": True,
        "blocksanity_item_placement": "progression",
        "one_up_block_item_placement": "progression",
        "world_6_2_bonus_area": False,
    }


class TestLicensesDisabledGeneration(NSMBDSTestBase):
    options = {
        "goal": "star_coin_hunt",
        "required_star_coins": 30,
        "license_mini_mushroom": False,
        "license_blue_shell": False,
        "license_mega_mushroom": False,
        "license_mushroom": False,
        "license_fire_flower": False,
        "license_touchscreen_pocket": False,
        "tower_castle_keys": False,
    }
