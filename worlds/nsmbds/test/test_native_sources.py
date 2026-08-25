"""Regression checks for maintainer-only native hook sources."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from ..rom import BASE_ROM_MD5, BASE_ROM_SHA256, BASE_ROM_SIZE


class TestNativeHookSources(unittest.TestCase):
    def test_no_turnaround_uses_input_filter_and_trigger_32(self) -> None:
        runtime_path = (
            Path(__file__).resolve().parents[1]
            / "lua_runtime"
            / "nsmbds"
            / "traps.lua"
        )
        source = runtime_path.read_text(encoding="utf-8")
        self.assertIn("local function apply_no_turnaround_at(address)", source)
        self.assertIn('context.active_mode == "no_turnaround"', source)
        self.assertIn('trigger_code == 32', source)
        self.assertIn('M.begin_timed_trap("no_turnaround", LONG_TRAP_FRAMES)', source)

    def test_powerup_pickpocket_notice_uses_trigger_33(self) -> None:
        runtime_path = (
            Path(__file__).resolve().parents[1]
            / "lua_runtime"
            / "nsmbds"
            / "traps.lua"
        )
        source = runtime_path.read_text(encoding="utf-8")
        self.assertIn("trigger_code == 33", source)
        self.assertIn(
            'M.begin_timed_trap("powerup_pickpocket_notice", BONK_FEEDBACK_FRAMES)',
            source,
        )

    def test_checked_in_native_artifacts_match_manifest(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        verifier_path = source_root / "verify_native_hooks.py"
        spec = importlib.util.spec_from_file_location("nsmbds_verify_native_hooks", verifier_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.verify(), [])

    def test_missing_gate_permit_clears_vanilla_purchase_state(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        metadata_path = source_root / "native_hooks" / "star_coin_gate_hook.py"
        spec = importlib.util.spec_from_file_location("nsmbds_star_coin_gate_hook", metadata_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(
            module.STAR_COIN_GATE_HOOK_BYTES[0x6C:0x74],
            bytes.fromhex("0000A0E3 EE02C2E5"),
        )

    def test_rom_verifier_matches_runtime_identity(self) -> None:
        verifier_path = Path(__file__).resolve().parents[1] / "src" / "verify_base_rom.py"
        spec = importlib.util.spec_from_file_location("nsmbds_verify_base_rom", verifier_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.EXPECTED_SIZE, BASE_ROM_SIZE)
        self.assertEqual(module.EXPECTED_MD5.lower(), BASE_ROM_MD5.lower())
        self.assertEqual(module.EXPECTED_SHA256.lower(), BASE_ROM_SHA256.lower())
