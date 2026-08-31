"""Regression checks for maintainer-only native hook sources."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from ..rom import BASE_ROM_MD5, BASE_ROM_SHA256, BASE_ROM_SIZE


class TestNativeHookSources(unittest.TestCase):
    def test_native_hit_block_is_primary_and_preserves_pending_queue(self) -> None:
        runtime_root = Path(__file__).resolve().parents[1] / "lua_runtime"
        hooks_source = (runtime_root / "nsmbds" / "hooks.lua").read_text(encoding="utf-8")
        blocks_source = (runtime_root / "nsmbds" / "blocksanity.lua").read_text(encoding="utf-8")
        constants_source = (runtime_root / "nsmbds" / "constants.lua").read_text(encoding="utf-8")
        orchestrator_source = (runtime_root / "nsmbds_sideloading.lua").read_text(encoding="utf-8")

        self.assertIn('memory.read_arm9_register("R1")', hooks_source)
        self.assertIn('memory.read_arm9_register("R2")', hooks_source)
        self.assertNotIn("ADDR_HIT_BLOCK_X_MASK", hooks_source)
        for address in ("0x0209E914", "0x0209E9F4", "0x0209EB24", "0x0209EB54"):
            self.assertIn(address, hooks_source + constants_source)
        self.assertIn("SYS_CHANGE_TILE_FUNCTION = 0x020AF30C", constants_source)
        self.assertIn('memory.read_arm9_register("LR")', hooks_source)
        self.assertIn('return "W2-A Block 6"', hooks_source)
        self.assertIn('return "W2-A Block 7"', hooks_source)
        self.assertIn('context.active_mode == "head_bonk"', hooks_source)
        self.assertIn("function M.observe_native_block_hits()", blocks_source)
        self.assertNotIn("and not context.hit_block_execute_hook_usable", blocks_source)
        self.assertIn("local capture_ok, capture_error = pcall(capture_native_block_hit)", hooks_source)
        self.assertIn("MOVING_BLOCK_OPEN_STATE_OFFSET = 0x3E4", blocks_source)
        self.assertIn("AP_EVENT_TYPE_MOVING_BLOCK_OPEN", blocks_source)
        self.assertIn("hooks.ensure_hit_block_execute_hook()", orchestrator_source)
        self.assertIn("hooks.sync_head_bonk_execute_hook()", orchestrator_source)
        self.assertNotIn(
            'context.active_mode == "head_bonk" then\n            hooks.ensure_hit_block_execute_hook()',
            orchestrator_source,
        )

        reset_body = blocks_source.split(
            "function M.reset_block_observer_state()", 1
        )[1].split("\nend", 1)[0]
        self.assertNotIn("block_event_queue = {}", reset_body)
        self.assertNotIn("queued_block_events = {}", reset_body)
        self.assertNotIn("native_block_hits = {}", reset_body)

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
        mailbox_ranges = (
            (module.PERMIT_MAILBOX, module.PERMIT_MAILBOX + module.PERMIT_MAILBOX_SIZE),
            (module.CURRENCY_MAILBOX, module.CURRENCY_MAILBOX + module.CURRENCY_MAILBOX_SIZE),
            (module.SELECTOR_TRACE, module.SELECTOR_TRACE + 3),
            (module.TIER_MAILBOX, module.TIER_MAILBOX + module.TIER_MAILBOX_SIZE),
        )
        self.assertTrue(all(
            end <= next_start
            for (_start, end), (next_start, _next_end)
            in zip(mailbox_ranges, mailbox_ranges[1:])
        ))
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
