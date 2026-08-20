"""
New Super Mario Bros. DS - Host Settings
Defines host configuration variables for Archipelago server hosts.
"""

from typing import Optional

from settings import Group, OptionalUserFilePath


class NSMBDSSettings(Group):
    class LastPatchedRom(OptionalUserFilePath):
        """Last patched NSMBDS seed ROM selected by the client launcher."""
        description = "Patched NSMBDS Seed ROM"

    last_patched_rom: Optional[LastPatchedRom] = None
    auto_launch_game: bool = False
    allow_unsafe_nsmbds_options: bool = False
