"""Seed-ROM identification shared by the builder, patcher and launcher."""

PATCH_PROTOCOL_VERSION = 2
# Reserve the final 32 bytes of the supported 32-MiB cartridge, outside NitroFS.
PATCH_MARKER_ROM_OFFSET = 0x01FFFFE0
PATCH_MARKER = bytes.fromhex("1E FF 2F E1 41 50 4E 53 02 00 00 00 00 00 00 00 00 00 00 00")
