"""
New Super Mario Bros. DS - WebWorld Definition
Customizes WebHost appearance, documentation links, and setup tutorials.
"""

from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld

from .options import NSMBDS_OPTION_GROUPS


class NSMBDSWeb(WebWorld):
    """Webhost interface definition for New Super Mario Bros. DS."""

    theme = "grass"
    game_info_languages = ["en"]
    option_groups = NSMBDS_OPTION_GROUPS
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the New Super Mario Bros. DS randomizer with Archipelago and BizHawk.",
            "English",
            "setup_en.md",
            "setup/en",
            ["Lemix028"],
        )
    ]
