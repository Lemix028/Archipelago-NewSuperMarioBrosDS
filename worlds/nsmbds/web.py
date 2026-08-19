"""
New Super Mario Bros. DS - WebWorld Definition
Customizes WebHost appearance, documentation links, and setup tutorials.
"""

from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld


class NSMBDSWeb(WebWorld):
    """Webhost interface definition for New Super Mario Bros. DS."""

    theme = "grass"
    game_info_languages = ["en"]
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
