"""Regression checks for maintainer-only native hook sources."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from ..rom import BASE_ROM_MD5, BASE_ROM_SHA256, BASE_ROM_SIZE
from ..data.ram_addresses import (
    ADDR_ACTIVE_STAR_COIN_FLAGS,
    ADDR_LEVEL_DATA_BASE,
    ADDR_AP_RETURN_TO_MAP_DEATH_SEQUENCE,
    ADDR_STAR_COIN_STATE,
    LEVEL_DATA_WORLD_STRIDE,
)


class TestNativeHookSources(unittest.TestCase):
    def test_return_to_map_death_is_published_to_a_sticky_sequence(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1] / "lua_runtime" / "nsmbds"
        constants = (runtime_root / "constants.lua").read_text(encoding="utf-8")
        protection = (runtime_root / "protection.lua").read_text(encoding="utf-8")

        self.assertIn("M.SYS_AP_RETURN_TO_MAP_DEATH_SEQUENCE = 0x02002FF7", constants)
        self.assertIn("publish_return_to_map_death()", protection)
        self.assertIn("(sequence + 1) % 256", protection)
        self.assertEqual(ADDR_AP_RETURN_TO_MAP_DEATH_SEQUENCE, 0x00002FF7)

    def test_star_coin_pickups_are_committed_before_the_goal(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1] / "lua_runtime"
        orchestrator = (runtime_root / "nsmbds_sideloading.lua").read_text(encoding="utf-8")
        constants = (runtime_root / "nsmbds" / "constants.lua").read_text(encoding="utf-8")
        star_coins = (runtime_root / "nsmbds" / "star_coins.lua").read_text(encoding="utf-8")

        self.assertIn('require("nsmbds.star_coins")', orchestrator)
        self.assertIn("star_coins.commit_active_pickups", orchestrator)
        self.assertIn("M.SYS_ACTIVE_STAR_COIN_FLAGS = 0x02085A2C", constants)
        self.assertIn("M.SYS_STAR_COIN_STATE = 0x02088BDC", constants)
        self.assertIn("M.SYS_LEVEL_DATA_BASE = 0x02088C4C", constants)
        self.assertIn("world * constants.LEVEL_DATA_WORLD_STRIDE", star_coins)
        self.assertIn("merge_star_coin_flags(saved, active)", star_coins)
        self.assertEqual(ADDR_ACTIVE_STAR_COIN_FLAGS, 0x00085A2C)
        self.assertEqual(ADDR_STAR_COIN_STATE, 0x00088BDC)
        self.assertEqual(ADDR_LEVEL_DATA_BASE, 0x00088C4C)
        self.assertEqual(LEVEL_DATA_WORLD_STRIDE, 25)

    def test_death_link_notifications_use_one_unified_dl_popup(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1] / "lua_runtime" / "nsmbds"
        state_source = (runtime_root / "state.lua").read_text(encoding="utf-8")
        hud_source = (runtime_root / "hud.lua").read_text(encoding="utf-8")
        self.assertIn("death_link = 0x0A", state_source)
        for label in ("DEATH", "DAMAGE", "TIMER", "COINS", "GRACE"):
            self.assertIn(f'"{label}"', hud_source)
        self.assertIn('return "DEATH LINK", name', hud_source)
        self.assertIn('context.active_mode == "death_link_damage" then return', hud_source)

    def test_emulator_feed_supports_runtime_presentation_settings(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1] / "lua_runtime"
        feed_source = (runtime_root / "nsmbds" / "emulator_feed.lua").read_text(encoding="utf-8")
        connector_source = (
            runtime_root / "vendor" / "connector_bizhawk_generic.lua"
        ).read_text(encoding="utf-8")
        self.assertIn("function M.configure(request)", feed_source)
        self.assertIn("feed_width", feed_source)
        self.assertIn("feed_position", feed_source)
        self.assertIn("fade_seconds", feed_source)
        self.assertIn("local browsing_history = false", feed_source)
        self.assertIn("fade_seconds > 0 and wheel_delta > 0 and not browsing_history", feed_source)
        self.assertIn("browsing_history = scroll_offset > 0", feed_source)
        self.assertIn("_G.nsmbds_feed_configure = M.configure", feed_source)
        self.assertIn('["NSMBDS_FEED_CONFIG"]', connector_source)

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
        self.assertIn(
            bytes.fromhex("0000A0E3 EE02C2E5"),
            module.STAR_COIN_GATE_HOOK_BYTES,
        )

    def test_gate_tier_hook_and_messages_fit_the_verified_overlay_cave(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        metadata_path = source_root / "native_hooks" / "star_coin_gate_hook.py"
        spec = importlib.util.spec_from_file_location("nsmbds_star_coin_gate_tiers", metadata_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertLessEqual(
            module.HOOK_CAVE + len(module.STAR_COIN_GATE_HOOK_BYTES),
            0x020EE210,
        )
        self.assertEqual(module.DATA_CAVE_START, module.PERMIT_MAILBOX)
        self.assertLessEqual(
            module.TIER_MAILBOX + module.TIER_MAILBOX_SIZE,
            module.DATA_CAVE_END,
        )
        overlay_mailbox_ranges = (
            (module.PERMIT_MAILBOX, module.PERMIT_MAILBOX + module.PERMIT_MAILBOX_SIZE),
            (module.SELECTOR_TRACE, module.SELECTOR_TRACE + 3),
            (module.TIER_MAILBOX, module.TIER_MAILBOX + module.TIER_MAILBOX_SIZE),
        )
        self.assertTrue(all(
            end <= next_start
            for (_start, end), (next_start, _next_end)
            in zip(overlay_mailbox_ranges, overlay_mailbox_ranges[1:])
        ))
        self.assertEqual(module.CURRENCY_MAILBOX, 0x02002EF0)
        self.assertLessEqual(
            module.CURRENCY_GETTER_CAVE + len(module.STAR_COIN_CURRENCY_HOOK_BYTES),
            module.CURRENCY_MAILBOX,
        )
        self.assertLessEqual(
            module.CURRENCY_MAILBOX + module.CURRENCY_MAILBOX_SIZE,
            0x02002F00,
        )
        self.assertEqual(module.VANILLA_TIER_MESSAGE_BASE, 16)
        self.assertEqual(module.PROGRESSIVE_TIER_MESSAGE_BASE, 48)
        self.assertEqual(module.INDIVIDUAL_TIER_MESSAGE_BASE, 80)
        self.assertEqual(len(module.TIER_MESSAGES), 96)
        self.assertIn("Requires 5 total received", module.TIER_MESSAGES[0])
        self.assertIn("Requires 32 Progressive", module.TIER_MESSAGES[63])
        self.assertIn("and 160 total received", module.TIER_MESSAGES[95])
        self.assertIn("Reconnect the Archipelago client", module.INVALID_TIER_MESSAGE)

        assembly = (source_root / "asm" / "star_coin_gate_hook.s").read_text(encoding="utf-8")
        self.assertLess(
            assembly.index("@ Refuse every AP-controlled gate"),
            assembly.index("ldr     r0, =PERMIT_MASKS"),
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
