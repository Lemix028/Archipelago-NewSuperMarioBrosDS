"""Core container checks for the generated NSMBDS player patch."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

from .bases import NSMBDSTestBase
from ..rom import _select_base_rom_path
from ..settings import NSMBDSSettings


class TestProcedurePatch(NSMBDSTestBase):
    def test_base_rom_setting_is_optional_and_unset_by_default(self) -> None:
        self.assertFalse(NSMBDSSettings.RomFile.required)
        self.assertIsNone(NSMBDSSettings.rom_file)

    @patch("Utils.open_filename", return_value="")
    def test_base_rom_selection_cancel_has_clear_error(self, open_filename) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "No NSMBDS ROM file was selected"):
            _select_base_rom_path()
        open_filename.assert_called_once()

    @patch("Utils.open_filename")
    def test_base_rom_selection_rejects_a_directory(self, open_filename) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            open_filename.return_value = temporary_directory
            with self.assertRaisesRegex(FileNotFoundError, "is not a file"):
                _select_base_rom_path()

    def test_generate_output_writes_complete_player_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.world.generate_output(temporary_directory)
            patches = tuple(Path(temporary_directory).glob("*.apnsmbds"))
            self.assertEqual(len(patches), 1)

            with zipfile.ZipFile(patches[0]) as patch:
                names = set(patch.namelist())
                manifest = json.loads(patch.read("archipelago.json"))

            self.assertEqual(manifest["game"], "New Super Mario Bros. DS")
            self.assertEqual(manifest["patch_file_ending"], ".apnsmbds")
            self.assertEqual(manifest["result_file_ending"], ".nds")
            self.assertEqual(
                manifest["procedure"],
                [
                    ["apply_bsdiff4", ["native_hooks.bsdiff4"]],
                    ["apply_tokens", ["token_data.bin"]],
                    ["apply_player_palettes", ["nsmbds_patch_config.json"]],
                ],
            )
            self.assertTrue({
                "native_hooks.bsdiff4",
                "token_data.bin",
                "nsmbds_patch_config.json",
            } <= names)
