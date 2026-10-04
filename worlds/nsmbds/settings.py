"""
New Super Mario Bros. DS - Host Settings
Defines host configuration variables for Archipelago server hosts.
"""

from typing import Any, Optional

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
    # Local client preference; does not affect seed generation or item logic.
    reserve_mode: str = "automatic"
    blocksanity_global_check_percentage_cap: int = 30
    trap_percentage_cap: int = 50
    allow_unsafe_nsmbds_options: bool = False
    emulator_feed_enabled: bool = True
    emulator_feed_width: int = 500
    emulator_feed_position: str = "bottom_left"
    emulator_feed_fade_seconds: int = 0


def ensure_nsmbds_settings(host: Any) -> NSMBDSSettings:
    """Resolve our host group even if Core cached world settings during imports."""
    options = getattr(host, "nsmbds_options", None)
    if options is None or isinstance(options, dict):
        # Core can leave an existing YAML section as a dictionary when its
        # lazy world-settings cache was populated before NSMBDS registered.
        # Use the normal Group conversion to preserve values and path types.
        converted = NSMBDSSettings()
        converted.update(options or {})
        host.nsmbds_options = converted
        return converted
    return options
