"""
New Super Mario Bros. DS - Host Settings
Defines host configuration variables for Archipelago server hosts.
"""

from typing import Optional

from settings import Group, OptionalUserFilePath


class NSMBDSSettings(Group):
    class BaseRom(OptionalUserFilePath):
        """Clean New Super Mario Bros. DS USA base ROM."""
        description = "New Super Mario Bros. DS (USA) Base ROM"

    class LastPatchedRom(OptionalUserFilePath):
        """Last patched NSMBDS seed ROM selected by the client launcher."""
        description = "Patched NSMBDS Seed ROM"

    base_rom: Optional[BaseRom] = None
    last_patched_rom: Optional[LastPatchedRom] = None
    auto_launch_game: bool = False
    allow_unsafe_nsmbds_options: bool = False
    emulator_feed_enabled: bool = True
    emulator_feed_width: int = 500
    emulator_feed_position: str = "bottom_left"
    emulator_feed_fade_seconds: int = 0
