"""Regression tests for non-interactive BizHawk launcher discovery."""

from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path
from unittest import TestCase, mock

from settings import BizHawkClientOptions
from worlds.nsmbds.client import launcher
from worlds.nsmbds.settings import NSMBDSSettings


class FakeSettings:
    def __init__(self, value: object = None) -> None:
        self.bizhawkclient_options = BizHawkClientOptions()
        if value is not None:
            self.bizhawkclient_options.emuhawk_path = BizHawkClientOptions.EmuHawkPath(value)
        self.save_count = 0

    def save(self) -> None:
        self.save_count += 1


class TestBizHawkLauncherSettings(TestCase):
    def test_reserve_mode_defaults_and_saved_manual_preference(self) -> None:
        settings = FakeSettings()
        settings.nsmbds_options = NSMBDSSettings()
        with mock.patch.object(launcher, "_settings", return_value=settings):
            self.assertEqual(launcher.reserve_mode(), "automatic")
            launcher.set_reserve_mode("manual")
            self.assertEqual(launcher.reserve_mode(), "manual")
            with self.assertRaises(ValueError):
                launcher.set_reserve_mode("invalid")
        self.assertEqual(settings.save_count, 1)

    def test_failed_reserve_save_does_not_change_live_preference(self) -> None:
        settings = FakeSettings()
        settings.nsmbds_options = NSMBDSSettings()
        with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch.object(
            settings, "save", side_effect=OSError("disk full")
        ):
            with self.assertRaises(OSError):
                launcher.set_reserve_mode("manual")
            self.assertEqual(launcher.reserve_mode(), "automatic")

    def test_unset_path_is_read_without_required_file_dialog(self) -> None:
        settings = FakeSettings()
        with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch(
            "settings.FilePath.browse", side_effect=AssertionError("unexpected file dialog")
        ) as browse:
            self.assertIsNone(launcher.configured_emuhawk_path())
        browse.assert_not_called()

    def test_find_with_unset_path_does_not_browse(self) -> None:
        settings = FakeSettings()
        with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch.object(
            launcher, "_candidate_emuhawk_paths", return_value=()
        ), mock.patch(
            "settings.FilePath.browse", side_effect=AssertionError("unexpected file dialog")
        ) as browse:
            self.assertIsNone(launcher.find_emuhawk())
        browse.assert_not_called()

    def test_explicit_picker_saves_selected_path_with_setting_type(self) -> None:
        settings = FakeSettings()
        with tempfile.TemporaryDirectory() as temp_dir:
            selected = Path(temp_dir, "EmuHawk.exe")
            selected.touch()
            fake_utils = types.ModuleType("Utils")
            fake_utils.open_filename = mock.Mock(return_value=str(selected))
            with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch.dict(
                sys.modules, {"Utils": fake_utils}
            ):
                result = launcher.browse_for_emuhawk()

        self.assertEqual(result, selected.resolve())
        self.assertIsInstance(
            object.__getattribute__(settings.bizhawkclient_options, "__dict__")["emuhawk_path"],
            BizHawkClientOptions.EmuHawkPath,
        )
        self.assertEqual(settings.save_count, 1)
        fake_utils.open_filename.assert_called_once()

    def test_cancelling_explicit_picker_does_not_save(self) -> None:
        settings = FakeSettings()
        fake_utils = types.ModuleType("Utils")
        fake_utils.open_filename = mock.Mock(return_value=None)
        with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch.dict(
            sys.modules, {"Utils": fake_utils}
        ):
            self.assertIsNone(launcher.browse_for_emuhawk())
        self.assertEqual(settings.save_count, 0)

    def test_missing_configured_path_remains_available_for_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir, "missing", "EmuHawk.exe")
            settings = FakeSettings(missing)
            with mock.patch.object(launcher, "_settings", return_value=settings), mock.patch(
                "settings.FilePath.browse", side_effect=AssertionError("unexpected file dialog")
            ) as browse:
                configured = launcher.configured_emuhawk_path()
                error = launcher.emuhawk_launcher_error(configured)

        self.assertEqual(configured, missing.resolve())
        self.assertIn("was not found", error or "")
        browse.assert_not_called()
