"""
New Super Mario Bros. DS - Host Settings
Defines host configuration variables for Archipelago server hosts.
"""

from settings import Group, OptionalUserFilePath


class NSMBDSSettings(Group):
    class RomFile(OptionalUserFilePath):
        """Legacy base-ROM setting; patching always opens a fresh file picker."""
        description = "Legacy NSMBDS Base ROM Path (unused by patcher)"
        md5s = ["a2ddba012e5c3c2096d0be57cc273be5"]

    class LastPatchedRom(OptionalUserFilePath):
        """Last patched NSMBDS seed ROM selected by the client launcher."""
        description = "Patched NSMBDS Seed ROM"

    rom_file: RomFile = RomFile("")
    last_patched_rom: LastPatchedRom = LastPatchedRom("")
    auto_launch_game: bool = False
    allow_unsafe_nsmbds_options: bool = False
