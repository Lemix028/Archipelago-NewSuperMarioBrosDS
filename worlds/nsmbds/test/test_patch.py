"""Core container checks for the generated NSMBDS player patch."""

from __future__ import annotations

import json
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from .bases import NSMBDSTestBase
from ..rom import _read_validated_base_rom, _select_base_rom_path


class TestProcedurePatch(NSMBDSTestBase):
    @patch("worlds.nsmbds.rom._base_rom_setting_path", return_value=None)
    @patch("Utils.open_filename", return_value="")
    def test_base_rom_selection_cancel_has_clear_error(self, open_filename, _saved_path) -> None:
        with self.assertRaisesRegex(FileNotFoundError, "No NSMBDS ROM file was selected"):
            _select_base_rom_path()
        open_filename.assert_called_once()

    @patch("worlds.nsmbds.rom._base_rom_setting_path", return_value=None)
    @patch("Utils.open_filename")
    def test_base_rom_selection_rejects_a_directory(self, open_filename, _saved_path) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            open_filename.return_value = temporary_directory
            with self.assertRaisesRegex(FileNotFoundError, "is not a file"):
                _select_base_rom_path()

    @staticmethod
    def _fake_settings(base_rom=None):
        settings = SimpleNamespace(
            nsmbds_options=SimpleNamespace(base_rom=base_rom),
            save_count=0,
        )

        def save() -> None:
            settings.save_count += 1

        settings.save = save
        return settings

    @patch("worlds.nsmbds.rom._validate_base_rom", return_value=b"validated ROM")
    @patch("Utils.open_filename")
    def test_base_rom_is_saved_after_first_valid_selection(self, open_filename, _validate) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            rom_path = Path(temporary_directory) / "clean.nds"
            rom_path.write_bytes(b"test")
            open_filename.return_value = str(rom_path)
            settings = self._fake_settings()

            with patch("worlds.nsmbds.rom._settings", return_value=settings):
                rom_data = _read_validated_base_rom()

            self.assertEqual(rom_data, b"validated ROM")
            self.assertEqual(Path(settings.nsmbds_options.base_rom), rom_path.resolve())
            self.assertEqual(settings.save_count, 1)

    @patch("worlds.nsmbds.rom._validate_base_rom", return_value=b"validated ROM")
    @patch("Utils.open_filename")
    def test_saved_base_rom_skips_the_file_dialog(self, open_filename, _validate) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            rom_path = Path(temporary_directory) / "clean.nds"
            rom_path.write_bytes(b"test")
            settings = self._fake_settings(str(rom_path))

            with patch("worlds.nsmbds.rom._settings", return_value=settings):
                rom_data = _read_validated_base_rom()

            self.assertEqual(rom_data, b"validated ROM")
            open_filename.assert_not_called()

    @patch("worlds.nsmbds.rom._validate_base_rom", return_value=b"validated ROM")
    @patch("Utils.open_filename")
    def test_missing_saved_base_rom_is_selected_again(self, open_filename, _validate) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "moved.nds"
            replacement_path = Path(temporary_directory) / "clean.nds"
            replacement_path.write_bytes(b"test")
            open_filename.return_value = str(replacement_path)
            settings = self._fake_settings(str(missing_path))

            with patch("worlds.nsmbds.rom._settings", return_value=settings):
                _read_validated_base_rom()

            self.assertEqual(Path(settings.nsmbds_options.base_rom), replacement_path.resolve())
            self.assertEqual(open_filename.call_args.args[2], str(missing_path.resolve()))

    @patch("Utils.messagebox")
    @patch("Utils.open_filename")
    def test_invalid_saved_base_rom_prompts_again_and_only_saves_replacement(
        self,
        open_filename,
        messagebox,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid.nds"
            replacement_path = Path(temporary_directory) / "clean.nds"
            invalid_path.write_bytes(b"wrong")
            replacement_path.write_bytes(b"correct")
            open_filename.return_value = str(replacement_path)
            settings = self._fake_settings(str(invalid_path))

            with (
                patch("worlds.nsmbds.rom._settings", return_value=settings),
                patch(
                    "worlds.nsmbds.rom._validate_base_rom",
                    side_effect=[ValueError("Wrong ROM"), b"validated ROM"],
                ) as validate,
            ):
                _read_validated_base_rom()

            self.assertEqual(
                validate.call_args_list,
                [call(invalid_path.resolve()), call(replacement_path.resolve())],
            )
            messagebox.assert_called_once()
            self.assertEqual(Path(settings.nsmbds_options.base_rom), replacement_path.resolve())
            self.assertEqual(settings.save_count, 1)

    @patch("Utils.messagebox")
    @patch("Utils.open_filename")
    def test_invalid_new_base_rom_is_not_saved(self, open_filename, messagebox) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid.nds"
            invalid_path.write_bytes(b"wrong")
            open_filename.side_effect = [str(invalid_path), ""]
            settings = self._fake_settings()

            with (
                patch("worlds.nsmbds.rom._settings", return_value=settings),
                patch("worlds.nsmbds.rom._validate_base_rom", side_effect=ValueError("Wrong ROM")),
                self.assertRaisesRegex(FileNotFoundError, "No NSMBDS ROM file was selected"),
            ):
                _read_validated_base_rom()

            self.assertEqual(open_filename.call_count, 2)
            messagebox.assert_called_once()
            self.assertIsNone(settings.nsmbds_options.base_rom)
            self.assertEqual(settings.save_count, 0)

    def test_generate_output_writes_complete_player_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.world.generate_output(temporary_directory)
            patches = tuple(Path(temporary_directory).glob("*.apnsmbds"))
            self.assertEqual(len(patches), 1)

            with zipfile.ZipFile(patches[0]) as patch:
                names = set(patch.namelist())
                manifest = json.loads(patch.read("archipelago.json"))
                patch_config = json.loads(patch.read("nsmbds_patch_config.json"))

            self.assertEqual(manifest["game"], "New Super Mario Bros. DS")
            self.assertEqual(manifest["patch_file_ending"], ".apnsmbds")
            self.assertEqual(manifest["result_file_ending"], ".nds")
            self.assertEqual(
                manifest["procedure"],
                [
                    ["apply_bsdiff4", ["native_hooks.bsdiff4"]],
                    ["apply_tokens", ["token_data.bin"]],
                    ["apply_secondary_screen_backgrounds", ["nsmbds_patch_config.json"]],
                    ["apply_player_palettes", ["nsmbds_patch_config.json"]],
                ],
            )
            self.assertTrue({
                "native_hooks.bsdiff4",
                "token_data.bin",
                "nsmbds_patch_config.json",
            } <= names)
            self.assertEqual(patch_config["options"]["secondary_screen_background"], 0)


class TestRandomizedSecondaryScreenProcedurePatch(NSMBDSTestBase):
    options = {
        "secondary_screen_background": "randomized",
    }

    def test_generate_output_persists_randomized_background_option(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.world.generate_output(temporary_directory)
            patch_path = next(Path(temporary_directory).glob("*.apnsmbds"))
            with zipfile.ZipFile(patch_path) as patch:
                patch_config = json.loads(patch.read("nsmbds_patch_config.json"))

            self.assertEqual(patch_config["options"]["secondary_screen_background"], 1)
