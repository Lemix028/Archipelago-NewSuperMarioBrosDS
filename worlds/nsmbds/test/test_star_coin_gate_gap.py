"""Gap boundaries, seed reconstruction, currency budget and guarded ROM edits."""

from copy import deepcopy
from unittest import TestCase
import runpy
import struct
from pathlib import Path

from BaseClasses import CollectionState
from test.general import setup_multiworld
from .. import NSMBDSWorld
from ..data.star_coin_gates import STAR_COIN_GATES, star_coin_gate_gap
from ..data.star_coin_gate_messages import (
    GATE_GAP_CHECK_OFFSET, GATE_GAP_CHECK_WORD, GATE_HOOK_CAVE,
    GATE_PRICE_OFFSET, GATE_PRICE_WORD, gate_tier_messages,
)
from ..options import StarCoinGateGap
from ..rom.star_coin_gates import patch_gate_overlay, patch_gate_messages


class TestStarCoinGateGap(TestCase):
    def test_new_options_accept_three_through_five_and_saved_prices_accept_legacy_gaps(self):
        self.assertEqual(StarCoinGateGap.default, 5)
        self.assertEqual(star_coin_gate_gap({}), 5)
        for gap in range(3, 6):
            self.assertEqual(StarCoinGateGap.from_any(gap).value, gap)
        for gap in range(1, 6):
            self.assertEqual(star_coin_gate_gap({"star_coin_gate_gap": gap}), gap)
            self.assertEqual(StarCoinGateGap.from_slot_data(gap).value, gap)
        for gap in (0, 6, 7, -1, True, 2.5, "3", None):
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                star_coin_gate_gap({"star_coin_gate_gap": gap})
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                StarCoinGateGap.from_slot_data(gap)
        for gap in (0, 1, 2, 6):
            with self.assertRaises(Exception):
                StarCoinGateGap.from_any(gap)

    def test_all_signs_at_each_gap_and_mode_use_lifetime_threshold_and_passes(self):
        by_target = {gate.target_stage_name: gate for gate in STAR_COIN_GATES}
        for mode in range(3):
            for gap in range(3, 6):
                mw = setup_multiworld(NSMBDSWorld, seed=9187, options={
                    "star_coin_gate_mode": mode, "star_coin_gate_gap": gap,
                })
                world = mw.worlds[1]
                tiers = {
                    gate.name: (world.vanilla_gate_tiers[gate.name] if mode == 0 else
                                world.individual_gate_tiers[gate.permit_item_name] if mode == 2 else
                                gate.progressive_index)
                    for gate in STAR_COIN_GATES
                }
                coins = [item for item in mw.get_items() if item.name == "Star Coin"]
                self.assertEqual(sum(item.advancement for item in coins), 32 * gap)
                for gate in STAR_COIN_GATES:
                    chain = [gate, *(by_target[target] for target in gate.prerequisite_target_stage_names)]
                    required = max(tiers[entry.name] for entry in chain) * gap
                    rule = mw.get_entrance(f"{gate.source_region} -> {gate.region_name}", 1).access_rule
                    state = CollectionState(mw)
                    for _ in range(required - 1):
                        state.collect(world.create_item("Star Coin"), prevent_sweep=True)
                    if mode == 1:
                        for _ in range(max(entry.progressive_index for entry in chain)):
                            state.collect(world.create_item("Progressive Gate Pass"), prevent_sweep=True)
                    elif mode == 2:
                        for entry in chain:
                            state.collect(world.create_item(entry.permit_item_name), prevent_sweep=True)
                    with self.subTest(mode=mode, gap=gap, gate=gate.name):
                        self.assertFalse(rule(state))
                        state.collect(world.create_item("Star Coin"), prevent_sweep=True)
                        self.assertTrue(rule(state))
                        if mode:
                            without_pass = CollectionState(mw)
                            for _ in range(required + 1):
                                without_pass.collect(world.create_item("Star Coin"), prevent_sweep=True)
                            self.assertFalse(rule(without_pass))
                slot = world.fill_slot_data()
                self.assertEqual(slot["star_coin_gate_gap"], gap)
                self.assertEqual(slot["options"]["star_coin_gate_gap"], gap)

    def test_tracker_reconstruction_preserves_gap_and_old_seeds_default_to_five(self):
        mw = setup_multiworld(NSMBDSWorld, seed=913, options={"star_coin_gate_gap": 3})
        world = mw.worlds[1]
        slot = world.fill_slot_data()
        original_tiers = deepcopy(world.vanilla_gate_tiers)
        world.options.star_coin_gate_gap = StarCoinGateGap(5)
        mw.re_gen_passthrough = {world.game: slot}
        world.generate_early()
        self.assertEqual(world.options.star_coin_gate_gap.value, 3)
        self.assertEqual(world.vanilla_gate_tiers, original_tiers)
        del slot["star_coin_gate_gap"]
        del slot["options"]["star_coin_gate_gap"]
        world.generate_early()
        self.assertEqual(world.options.star_coin_gate_gap.value, 5)

    def test_tracker_preserves_existing_one_and_two_gap_seeds(self):
        world = setup_multiworld(NSMBDSWorld, options={"star_coin_gate_gap": 3}).worlds[1]
        slot = world.fill_slot_data()
        for gap in (1, 2):
            with self.subTest(gap=gap):
                slot["star_coin_gate_gap"] = gap
                slot["options"]["star_coin_gate_gap"] = gap
                world.multiworld.re_gen_passthrough = {world.game: slot}
                world.generate_early()
                self.assertEqual(world.options.star_coin_gate_gap.value, gap)
                self.assertEqual(world.fill_slot_data()["star_coin_gate_gap"], gap)

    def test_goal_coin_budget_can_exceed_gate_budget(self):
        mw = setup_multiworld(NSMBDSWorld, options={
            "star_coin_gate_gap": 3, "goal": "star_coin_hunt", "required_star_coins": 200,
        })
        coins = [item for item in mw.get_items() if item.name == "Star Coin"]
        self.assertEqual(sum(item.advancement for item in coins), 200)
        self.assertEqual(len(coins), 240)

    def test_native_patch_sites_are_guarded_and_messages_cover_each_gap(self):
        metadata = runpy.run_path(Path(__file__).parents[1] / "src/native_hooks/star_coin_gate_hook.py")
        original = metadata["STAR_COIN_GATE_HOOK_BYTES"]
        for gap in range(1, 6):
            patched = patch_gate_overlay(original, GATE_HOOK_CAVE, gap)
            self.assertEqual(struct.unpack_from("<I", patched, GATE_GAP_CHECK_OFFSET)[0],
                             (GATE_GAP_CHECK_WORD & ~0xFF) | gap)
            self.assertEqual(struct.unpack_from("<I", patched, GATE_PRICE_OFFSET)[0],
                             (GATE_PRICE_WORD & ~0xFF) | gap)
            messages = gate_tier_messages(gap)
            self.assertEqual(len(messages), 96)
            for tier in range(1, 33):
                for index in (tier - 1, 32 + tier - 1, 64 + tier - 1):
                    self.assertIn(f"{tier * gap} total", messages[index])
                    self.assertIn(f"Opening costs {gap} Star Coin", messages[index])
        corrupt = bytearray(original)
        corrupt[GATE_PRICE_OFFSET] ^= 0xFF
        with self.assertRaises(ValueError):
            patch_gate_overlay(corrupt, GATE_HOOK_CAVE, 3)

    def test_bmg_edit_preserves_existing_bytes_and_attributes(self):
        header = bytearray(32)
        header[:8] = b"MESGbmg1"
        struct.pack_into("<I", header, 12, 2)
        header[16] = 2
        info = bytearray(928)
        struct.pack_into("<4sIHHI", info, 0, b"INF1", len(info), 112, 8, 91)
        for index in range(112):
            info[16 + index * 8 + 4:24 + index * 8] = b"\xAA\xBB\xCC\xDD"
        strings = bytearray(32)
        struct.pack_into("<4sI", strings, 0, b"DAT1", len(strings))
        strings[10:18] = b"\x1A\x00\x08\xFF\x00\x00\x01\x00"
        original = header + info + strings
        struct.pack_into("<I", original, 8, len(original))
        for gap in range(1, 6):
            result = patch_gate_messages(original, gap)
            if gap == 5:
                self.assertEqual(result, original)
            result_info = result[32:32 + len(info)]
            result_strings = result[32 + len(info):]
            self.assertEqual(result_info[:16 + 16 * 8], info[:16 + 16 * 8])
            self.assertEqual(result_strings[8:32], strings[8:32])
            self.assertEqual(struct.unpack_from("<I", result, 8)[0], len(result))
            for index, text in enumerate(gate_tier_messages(gap), 16):
                self.assertEqual(result_info[20 + index * 8:24 + index * 8], b"\xAA\xBB\xCC\xDD")
                if gap != 5:
                    offset = struct.unpack_from("<I", result_info, 16 + index * 8)[0]
                    self.assertEqual(result_strings[8 + offset:].decode("utf-16le").split("\0")[0], text)
        for offset, replacement in ((0, b"bad!"), (16, b"\xFF"), (40, b"\x01\x00")):
            corrupt = bytearray(original)
            corrupt[offset:offset + len(replacement)] = replacement
            with self.assertRaises(ValueError):
                patch_gate_messages(corrupt, 3)
