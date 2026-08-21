"""Native NSMBDS Worldmap SAVE-menu patch metadata (USA/A2DE)."""

from __future__ import annotations

OVERLAY_ID = 8

# These are the three instructions used by the established "Save Anytime from Worldmap" patch.
PATCHES = (
    (0x020CDBE8, 0xE5D01000, 0xE3A01001),  # Show SAVE.
    (0x020D0224, 0xE7D11002, 0xE3A01003),  # Extend menu to four entries.
    (0x020D01F8, 0xE3A06000, 0xE3A06001),  # Four-entry menu behaviour.
)
