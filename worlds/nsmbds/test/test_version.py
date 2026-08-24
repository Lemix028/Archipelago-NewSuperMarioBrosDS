"""Keep release metadata synchronized across Python, the manifest, and Lua."""

import json
import unittest
from pathlib import Path

from ..version import APWORLD_VERSION, DISPLAY_VERSION


class TestReleaseVersion(unittest.TestCase):
    def test_release_versions_agree(self) -> None:
        world_dir = Path(__file__).parent.parent
        manifest = json.loads(
            (world_dir / "archipelago.json").read_text(encoding="utf-8")
        )
        lua_version = (
            world_dir / "lua_runtime" / "nsmbds" / "version.lua"
        ).read_text(encoding="utf-8")

        self.assertEqual(manifest["world_version"], APWORLD_VERSION)
        self.assertIn(f'M.VERSION = "{APWORLD_VERSION}"', lua_version)
        self.assertIn(f'M.VERSION_LABEL = "v{DISPLAY_VERSION}"', lua_version)
