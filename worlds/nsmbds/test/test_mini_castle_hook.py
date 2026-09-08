"""Static regression coverage for the native Mini-Mario castle hook."""

from __future__ import annotations

import hashlib
import json
import runpy
import struct
from pathlib import Path
from unittest import TestCase

from ..data.patch_protocol import PATCH_MARKER, PATCH_PROTOCOL_VERSION


WORLD_ROOT = Path(__file__).resolve().parent.parent
METADATA_ROOT = WORLD_ROOT / "src" / "native_hooks"


def arm_branch_target(source: int, instruction: int) -> int:
    displacement = instruction & 0x00FF_FFFF
    if displacement & 0x0080_0000:
        displacement -= 0x0100_0000
    return source + 8 + displacement * 4


class TestMiniCastleHook(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.hook = runpy.run_path(METADATA_ROOT / "mini_castle_hook.py")
        cls.star_coin_hook = runpy.run_path(METADATA_ROOT / "star_coin_gate_hook.py")
        cls.manifest = json.loads(
            (METADATA_ROOT / "native_hooks_manifest.json").read_text(encoding="utf-8")
        )

    def test_patch_marker_requires_native_mini_castle_protocol(self) -> None:
        self.assertEqual(PATCH_PROTOCOL_VERSION, 3)
        self.assertEqual(struct.unpack_from("<I", PATCH_MARKER, 8)[0], PATCH_PROTOCOL_VERSION)

    def test_hook_replays_return_value_and_fits_overlay_cave(self) -> None:
        payload = self.hook["MINI_CASTLE_HOOK_BYTES"]
        original = self.hook["ORIGINAL_HOOK_WORD"]
        first = struct.unpack_from("<I", payload)[0]
        self.assertEqual(first, original)  # mov r0, r4
        self.assertEqual(self.hook["CONTINUE"], self.hook["HOOK_SITE"] + 4)
        branch = struct.unpack_from("<I", payload, len(payload) - 8)[0]
        self.assertEqual(
            arm_branch_target(self.hook["HOOK_CAVE"] + len(payload) - 8, branch),
            self.hook["CONTINUE"],
        )
        self.assertGreaterEqual(
            self.hook["HOOK_CAVE"],
            self.star_coin_hook["TIER_MAILBOX"] + self.star_coin_hook["TIER_MAILBOX_SIZE"],
        )
        self.assertLessEqual(
            self.hook["HOOK_CAVE"] + len(payload),
            self.star_coin_hook["DATA_CAVE_END"],
        )

    def test_hook_embeds_sticky_flag_and_secret_routes(self) -> None:
        payload = self.hook["MINI_CASTLE_HOOK_BYTES"]
        self.assertEqual(
            struct.unpack_from("<I", payload, len(payload) - 4)[0],
            self.hook["MINI_CASTLE_FLAGS"],
        )
        self.assertEqual(
            (
                self.hook["W2_CASTLE_WORLD"], self.hook["W2_SECRET_DESTINATION"],
                self.hook["W5_CASTLE_WORLD"], self.hook["W5_SECRET_DESTINATION"],
            ),
            (1, 3, 4, 6),
        )

    def test_manifest_hashes_hook_and_runtime_patch(self) -> None:
        payload = self.hook["MINI_CASTLE_HOOK_BYTES"]
        patch_bytes = (WORLD_ROOT / "rom" / "native_hooks.bsdiff4").read_bytes()
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            self.manifest["mini_castle_hook_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(patch_bytes).hexdigest(),
            self.manifest["native_hooks_bsdiff4_sha256"],
        )
