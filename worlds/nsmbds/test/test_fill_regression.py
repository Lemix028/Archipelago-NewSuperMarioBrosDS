"""Regression coverage for full-size template generation."""

from typing import ClassVar

from .bases import NSMBDSTestBase


class TestDefaultTemplateFill(NSMBDSTestBase):
    """The generated default template must provide enough valid progression spots."""

    options: ClassVar[dict[str, object]] = {
        "red_coin_checks": True,
        "one_up_block_checks": True,
        "one_up_block_item_placement": "non_progression",
        "blocksanity": False,
        "world_6_2_bonus_area": True,
        "secret_exit_checks": True,
        "toad_house_checks": True,
        "secret_exit_shortcut_logic": False,
        "secret_exit_world_unlock_logic": False,
        "cannon_route_logic": False,
        "advanced_location_item_placement": "allow_progression",
        "star_coin_gate_mode": "vanilla",
        "tower_castle_keys": True,
        "trap_percentage": 20,
    }

    def setUp(self) -> None:
        # This seed originally exposed the production generator failure.
        self.world_setup(97142355401817360234)
