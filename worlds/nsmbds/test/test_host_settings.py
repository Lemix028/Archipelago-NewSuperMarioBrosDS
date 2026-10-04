"""Host settings remain usable when Core's lazy registry predates this world."""

from types import SimpleNamespace
from unittest import TestCase, mock

import settings as core_settings
from test.general import setup_multiworld
from .. import NSMBDSWorld
from ..client import launcher
from ..client import NSMBDSClient
from ..rom import _settings as rom_settings
from ..settings import NSMBDSSettings, ensure_nsmbds_settings


class TestHostSettings(TestCase):
    def test_client_construction_defers_settings_until_first_use(self):
        with mock.patch.object(launcher, "reserve_mode", return_value="manual") as load_mode:
            client = NSMBDSClient()
            load_mode.assert_not_called()
            self.assertEqual(client.reserve_mode, "manual")
            self.assertEqual(client.reserve_mode, "manual")
            load_mode.assert_called_once_with()

    def test_stale_core_registry_converts_existing_values_without_saving(self):
        with mock.patch.object(core_settings, "skip_autosave", True):
            host = core_settings.Settings(None)
        values = {
            "allow_unsafe_nsmbds_options": True,
            "blocksanity_global_check_percentage_cap": 42,
            "trap_percentage_cap": 73,
            "reserve_mode": "manual",
            "base_rom": "existing-base.nds",
            "last_patched_rom": "existing-seed.nds",
            "future_setting": "preserved",
        }
        host.update({"nsmbds_options": values})
        with mock.patch.object(core_settings, "_world_settings_name_cache", {}), mock.patch.object(
            core_settings, "_world_settings_name_cache_updated", True
        ), mock.patch.object(host, "save") as save:
            self.assertIsInstance(host.nsmbds_options, dict)
            group = ensure_nsmbds_settings(host)
            self.assertIsInstance(host.nsmbds_options, NSMBDSSettings)
            self.assertIs(ensure_nsmbds_settings(host), group)
            for name in ("allow_unsafe_nsmbds_options", "blocksanity_global_check_percentage_cap",
                         "trap_percentage_cap", "reserve_mode", "future_setting"):
                self.assertEqual(getattr(group, name), values[name])
            stored = object.__getattribute__(group, "__dict__")
            self.assertIsInstance(stored["base_rom"], NSMBDSSettings.BaseRom)
            self.assertIsInstance(stored["last_patched_rom"], NSMBDSSettings.LastPatchedRom)
            self.assertEqual(str(stored["base_rom"]), values["base_rom"])
            self.assertEqual(str(stored["last_patched_rom"]), values["last_patched_rom"])
            self.assertEqual(group.emulator_feed_width, 500)
            save.assert_not_called()

    def test_missing_group_uses_defaults_and_existing_group_keeps_identity(self):
        host = SimpleNamespace()
        group = ensure_nsmbds_settings(host)
        self.assertIsInstance(group, NSMBDSSettings)
        self.assertFalse(group.allow_unsafe_nsmbds_options)
        group.reserve_mode = "manual"
        self.assertIs(ensure_nsmbds_settings(host), group)
        self.assertEqual(group.reserve_mode, "manual")

    def test_generation_honors_dictionary_caps_and_unsafe_override(self):
        for unsafe in (False, True):
            host = SimpleNamespace(nsmbds_options={
                "allow_unsafe_nsmbds_options": unsafe,
                "blocksanity_global_check_percentage_cap": 42,
                "trap_percentage_cap": 73,
            })
            with mock.patch("worlds.nsmbds.get_settings", return_value=host):
                mw = setup_multiworld(NSMBDSWorld, steps=("generate_early",), seed=1337, options={
                    "blocksanity_global_check_percentage": 100,
                    "trap_percentage": 100,
                })
            self.assertEqual(mw.worlds[1].options.blocksanity_global_check_percentage.value,
                             100 if unsafe else 42)
            self.assertEqual(mw.worlds[1].options.trap_percentage.value, 100 if unsafe else 73)

    def test_client_and_rom_access_share_converted_host_group(self):
        host = SimpleNamespace(nsmbds_options={"reserve_mode": "manual"})
        with mock.patch.object(core_settings, "get_settings", return_value=host):
            self.assertEqual(launcher.reserve_mode(), "manual")
            group = host.nsmbds_options
            self.assertIs(rom_settings(), host)
            self.assertIs(host.nsmbds_options, group)
