"""DeathLink lifecycle and seed statistics across transitions and restarts."""

import copy
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from worlds.nsmbds.client import NSMBDSClient
from worlds.nsmbds.client.features.death_link import (
    DEATH_LINK_EFFECT_DAMAGE, DEATH_LINK_EFFECT_DEATH, DEATH_LINK_EFFECT_TIMER_DRAIN,
)
from worlds.nsmbds.client.ui.tracker.state import build_tracker_snapshot, render_tracker_markup
from worlds.nsmbds.client.features.death_counter_status import death_counter_command
from worlds.nsmbds.client import launcher
from worlds.nsmbds.data import ram_addresses as ram


class TestDeathLink(IsolatedAsyncioTestCase):
    def setUp(self):
        self.storage = {}
        self.load = patch("Utils.persistent_load", return_value=self.storage).start()
        self.store = patch("Utils.persistent_store", side_effect=self.save).start()
        self.addCleanup(patch.stopall)
        patch.object(launcher, "show_death_counter", return_value=True).start()
        self.ctx = SimpleNamespace(
            slot=1, team=0, server_seed_name="death-test-seed", auth="Mario",
            slot_data={"death_link": True}, items_received=[], checked_locations=set(),
            missing_locations=set(), bizhawk_ctx=object(),
            server=SimpleNamespace(socket=SimpleNamespace(open=True, closed=False)),
            player_names={1: "Mario", 2: "Luigi", 3: "Peach"},
            slot_info={1: SimpleNamespace(game="New Super Mario Bros. DS", name="Mario"),
                       2: SimpleNamespace(game="New Super Mario Bros. DS", name="Luigi"),
                       3: SimpleNamespace(game="Super Mario World", name="Peach")},
            send_msgs=AsyncMock(), send_death=AsyncMock(),
        )
        self.client = NSMBDSClient()
        self.client._session_identity = (self.ctx.server_seed_name, 0, 1)
        self.client._configure_death_counter(self.ctx)
        self.ctx.client_handler = self.client
        self.client._last_lives = 5
        self.client._last_timer = 101 * ram.TIMER_UNITS_PER_SECOND
        self.client._last_insured_death_sequence = 0
        self.client._last_return_to_map_death_sequence = 0

    def save(self, category, key, value, **_kwargs):
        self.storage.setdefault(category, {})[key] = copy.deepcopy(value)

    def incoming(self, *, source="Luigi", timestamp=1.0):
        self.client.on_package(self.ctx, "Bounced", {
            "tags": ["DeathLink"], "data": {"source": source, "time": timestamp},
        })

    async def poll(self, *, lives=5, timer=100, insured=0, returned=0, flags=0, powerup=0, freeze=0, menu=0):
        self.client._read_lives_and_timer = AsyncMock(return_value=(
            lives, timer * ram.TIMER_UNITS_PER_SECOND, powerup, 0, 0, insured, returned, flags, freeze, menu,
        ))
        await self.client._handle_death_link(self.ctx)

    async def test_normal_death_counts_and_sends_once_including_last_life(self):
        await self.poll(lives=4)
        await self.poll(lives=4, timer=0)
        await self.poll(lives=4, timer=0)
        self.ctx.send_death.assert_awaited_once_with("Mario died.")
        self.assertEqual((self.client._death_count, self.client._death_link_death_count), (1, 0))
        self.client._last_lives = 1
        await self.poll(lives=0, timer=0)
        await self.poll(lives=5, timer=0)
        self.assertEqual(self.client._death_count, 2)
        self.assertEqual(self.ctx.send_death.await_count, 2)

    async def test_counter_counts_with_deathlink_disabled_and_before_amnesty(self):
        self.ctx.slot_data["death_link"] = False
        await self.poll(lives=4)
        self.assertEqual(self.client._death_count, 1)
        self.ctx.send_death.assert_not_awaited()
        self.ctx.slot_data.update(death_link=True, death_link_amnesty=3)
        await self.poll(lives=3, timer=99)
        await self.poll(lives=2, timer=98)
        self.assertEqual(self.client._death_count, 3)
        self.ctx.send_death.assert_not_awaited()
        await self.poll(lives=1, timer=97)
        self.ctx.send_death.assert_awaited_once()
        self.assertEqual(self.client._death_count, 4)

    async def test_return_to_map_sticky_sequence_and_later_normal_death(self):
        await self.poll(flags=ram.STAGE_EXIT_RETURN_TO_MAP_MASK)
        await self.poll(lives=4, timer=99, returned=1)
        self.assertEqual(self.client._death_count, 0)
        self.assertEqual(self.client._death_link_amnesty_count, 0)
        self.ctx.send_death.assert_not_awaited()
        await self.poll(lives=4, timer=200, returned=1)
        await self.poll(lives=3, timer=199, returned=1)
        self.ctx.send_death.assert_awaited_once()
        self.assertEqual(self.client._death_count, 1)

    async def test_insured_death_counts_once_and_respects_send_setting(self):
        await self.poll(insured=1)
        await self.poll(insured=1, timer=99)
        self.assertEqual(self.client._death_count, 1)
        self.ctx.send_death.assert_awaited_once()
        self.ctx.slot_data["death_link_triggers_on_insured_death"] = False
        await self.poll(insured=2, timer=98)
        self.assertEqual(self.client._death_count, 2)
        self.assertEqual(self.ctx.send_death.await_count, 1)

    async def test_pending_deathlink_never_claims_an_already_observed_death(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)) as write:
            await self.poll(lives=4)
            write.assert_not_awaited()
            self.assertTrue(self.client._pending_death_link)
            self.assertEqual((self.client._death_count, self.client._death_link_death_count), (1, 0))
            self.ctx.send_death.assert_awaited_once()
            await self.poll(lives=4, timer=300)
            await self.poll(lives=4, timer=299)
            write.assert_awaited_once()
            self.assertFalse(self.client._pending_death_link)

    async def test_single_pending_effect_waits_through_menu_and_failed_guard(self):
        self.incoming()
        self.ctx.slot_data["death_link_effect"] = DEATH_LINK_EFFECT_DAMAGE
        self.incoming(timestamp=2.0)
        self.assertEqual(self.client._pending_death_link_effect, DEATH_LINK_EFFECT_DEATH)
        with patch("worlds._bizhawk.guarded_write", AsyncMock(side_effect=[False, True])) as write:
            await self.poll(timer=101)
            await self.poll(timer=101)
            write.assert_not_awaited()
            await self.poll(timer=100)
            self.assertTrue(self.client._pending_death_link)
            self.assertFalse(self.client._suppress_next_local_death)
            await self.poll(timer=99)
            self.assertFalse(self.client._pending_death_link)
            guards = write.await_args.args[2]
            for address, value in ((ram.ADDR_STAGE_MENU_OPEN, [0]), (ram.ADDR_STAGE_FREEZE_FLAG, [0]),
                                   (ram.ADDR_STAGE_EXIT_FLAGS, [0, 0, 0, 0])):
                self.assertIn((address, value, ram.MEMORY_DOMAIN), guards)
        self.assertEqual(self.client._death_count, 0)

    async def test_incoming_lethal_effect_counts_only_on_death_without_echo(self):
        for effect in (DEATH_LINK_EFFECT_DEATH, DEATH_LINK_EFFECT_DAMAGE, DEATH_LINK_EFFECT_TIMER_DRAIN):
            with self.subTest(effect=effect):
                self.client._last_lives = 5
                self.client._last_timer = 76 * ram.TIMER_UNITS_PER_SECOND
                self.client._pending_death_link = True
                self.client._pending_death_link_effect = effect
                before = self.client._death_count
                with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
                    await self.poll(timer=75)
                self.assertEqual(self.client._death_count, before)
                await self.poll(lives=4, timer=0)
                await self.poll(lives=4, timer=0)
                self.assertEqual(self.client._death_count, before + 1)
                self.assertEqual(self.client._death_count, self.client._death_link_death_count)
        self.ctx.send_death.assert_not_awaited()

    async def test_long_paused_incoming_death_is_still_suppressed_and_counted(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
            await self.poll()
        for _ in range(40):
            await self.poll(timer=0)
        self.assertTrue(self.client._suppress_next_local_death)
        await self.poll(lives=4, timer=0)
        self.assertEqual((self.client._death_count, self.client._death_link_death_count), (1, 1))
        self.ctx.send_death.assert_not_awaited()

    async def test_long_pause_preserves_normal_death_context(self):
        await self.poll()
        for _ in range(40):
            await self.poll(menu=1, freeze=1)
        await self.poll(lives=4, timer=0)
        self.ctx.send_death.assert_awaited_once()
        self.assertEqual(self.client._death_count, 1)

    async def test_pause_and_stage_exit_defer_pending_effect(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)) as write:
            await self.poll(timer=100, menu=1)
            await self.poll(timer=99, freeze=1)
            await self.poll(timer=98, flags=1)
            write.assert_not_awaited()
            self.assertTrue(self.client._pending_death_link)
            await self.poll(timer=97)
            write.assert_awaited_once()

    async def test_life_delivery_refresh_keeps_next_death_visible(self):
        await self.poll(lives=4)
        with patch("worlds._bizhawk.guarded_read", AsyncMock(return_value=[bytes([4])])), \
                patch.object(self.client, "_write_item_transaction", AsyncMock(return_value=True)):
            await self.client._adjust_byte(self.ctx, ram.ADDR_LIVES, 1, 99, 123)
        self.assertTrue(self.client._life_delivery_needs_observation)
        await self.poll(lives=5, timer=99)
        self.assertFalse(self.client._life_delivery_needs_observation)
        await self.poll(lives=4, timer=98)
        self.assertEqual(self.client._death_count, 2)
        self.assertEqual(self.ctx.send_death.await_count, 2)

    async def test_nonlethal_damage_cannot_suppress_later_unrelated_death(self):
        self.ctx.slot_data["death_link_effect"] = DEATH_LINK_EFFECT_DAMAGE
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
            await self.poll()
        # Lua may find a powered-up Mario by the time it consumes this trigger.
        await self.poll(timer=100, powerup=2)
        self.assertTrue(self.client._suppress_next_local_death)
        await self.poll(timer=98, powerup=2)
        self.assertFalse(self.client._suppress_next_local_death)
        await self.poll(lives=4, timer=97)
        self.assertEqual((self.client._death_count, self.client._death_link_death_count), (1, 0))
        self.ctx.send_death.assert_awaited_once()

    async def test_return_to_map_clears_echo_expectation(self):
        self.client._suppress_next_local_death = True
        await self.poll(lives=4, returned=1)
        self.assertFalse(self.client._suppress_next_local_death)
        self.assertEqual(self.client._death_count, 0)
        await self.poll(lives=3, timer=99, returned=1)
        self.assertEqual(self.client._death_link_death_count, 0)
        self.ctx.send_death.assert_awaited_once()

    async def test_duplicate_own_and_malformed_packets_are_ignored(self):
        self.incoming(source="Mario")
        self.incoming(timestamp=float("nan"))
        self.client.on_package(self.ctx, "Bounced", {"tags": ["DeathLink"], "data": []})
        self.assertFalse(self.client._pending_death_link)
        self.incoming()
        self.client._pending_death_link = False
        self.incoming()
        self.assertFalse(self.client._pending_death_link)
        self.assertEqual(self.client._observed_death_links, {"Luigi": 1})

    async def test_grace_and_cooldown_still_record_unique_observed_deaths(self):
        self.ctx.slot_data["death_link_grace_percentage"] = 75
        with patch.object(self.client._death_link_rng, "randrange", return_value=0) as roll:
            self.incoming()
            self.incoming()
            roll.assert_called_once()
        self.assertFalse(self.client._pending_death_link)
        self.client._death_link_cooldown_until = float("inf")
        self.incoming(timestamp=2.0)
        self.assertFalse(self.client._pending_death_link)
        self.assertEqual(self.client._observed_death_links, {"Luigi": 2})
        self.assertEqual(self.client._death_count, 0)

    async def test_restart_and_seed_and_slot_isolation(self):
        await self.poll(lives=4)
        self.incoming(source="Peach")
        restarted = NSMBDSClient()
        restarted._session_identity = self.client._session_identity
        restarted._configure_death_counter(self.ctx)
        self.assertEqual(restarted._death_count, 1)
        self.assertEqual(restarted._observed_death_links, {"Peach": 1})
        self.assertFalse(restarted._accept_death_link_packet(self.ctx, {"source": "Peach", "time": 1.0}))
        for identity in (("other-seed", 0, 1), (self.ctx.server_seed_name, 0, 2),
                         (self.ctx.server_seed_name, 1, 1)):
            restarted._reset_session_state()
            restarted._session_identity = identity
            restarted._configure_death_counter(self.ctx)
            self.assertEqual(restarted._death_count, 0)
            self.assertFalse(restarted._observed_death_links)

    async def test_server_merge_and_retry_never_double_count(self):
        self.client._record_death(death_link=True)
        await self.client._sync_death_counter(self.ctx)
        key = self.client._death_counter_key()
        sets = [p for call in self.ctx.send_msgs.await_args_list for p in call.args[0] if p["cmd"] == "Set"]
        self.assertEqual([p["operations"] for p in sets], [
            [{"operation": "max", "value": 1}], [{"operation": "max", "value": 1}],
        ])
        self.client._handle_death_counter_packet(self.ctx, "Retrieved", {"keys": {key: 12, key + "_deathlink": 3}})
        self.assertEqual((self.client._death_count, self.client._death_link_death_count), (12, 3))
        self.client._handle_death_counter_packet(self.ctx, "SetReply", {"key": key, "value": 1})
        self.assertEqual(self.client._death_count, 12)
        self.ctx.send_msgs.side_effect = ConnectionError("Disconnected")
        with self.assertRaises(ConnectionError):
            await self.client._sync_death_counter(self.ctx)
        self.assertTrue(self.client._death_counter_write_pending)
        self.ctx.send_msgs.side_effect = None
        await self.client._sync_death_counter(self.ctx)
        self.assertFalse(self.client._death_counter_write_pending)
        self.assertEqual(self.client._death_count, 12)

    async def test_counter_save_failure_retries_without_incrementing(self):
        self.store.side_effect = OSError("Disk unavailable")
        with self.assertLogs("NSMBDS", level="WARNING"):
            self.client._record_death(death_link=False)
        self.assertTrue(self.client._death_counter_save_pending)
        self.store.side_effect = self.save
        await self.client._sync_death_counter(self.ctx)
        self.assertFalse(self.client._death_counter_save_pending)
        self.assertEqual(self.storage["nsmbds"][self.client._death_counter_key()]["total"], 1)

    async def test_other_totals_are_available_in_chat_but_absent_from_overview(self):
        key = self.client._death_counter_key(2)
        self.client._handle_death_counter_packet(self.ctx, "Retrieved", {
            "keys": {key: 10, key + "_deathlink": 4},
        })
        self.incoming(source="Luigi")
        self.incoming(source="Peach", timestamp=2.0)
        snapshot = build_tracker_snapshot(self.ctx)
        self.assertEqual(self.client._other_death_counter_rows(self.ctx), (
            ("Luigi", 10, 4, True), ("Peach", 1, None, False),
        ))
        overview = render_tracker_markup(snapshot)
        self.assertIn("Deaths: 0", overview)
        for detail in ("Luigi", "Peach", "DeathLink waiting", "from DeathLink", "Death Link Rules"):
            self.assertNotIn(detail, overview)
        output = []
        self.assertTrue(death_counter_command(self.ctx, output.append))
        self.assertIn("Luigi: 10 (4 deathlink)", output[0])
        self.assertIn("Peach: 1", output[0])
        self.assertNotIn("Waiting effect", output[0])
        for value in (-1, True, "99", {}, float("inf")):
            self.client._handle_death_counter_packet(self.ctx, "SetReply", {"key": key, "value": value})
        self.assertEqual(self.client._other_death_counts[2]["total"], 10)

    async def test_hiding_overview_counter_keeps_tracking_and_chat_statistics(self):
        with patch.object(launcher, "show_death_counter", return_value=False):
            await self.poll(lives=4)
            snapshot = build_tracker_snapshot(self.ctx)
            self.assertFalse(snapshot.show_death_counter)
            self.assertNotIn("Deaths:", render_tracker_markup(snapshot))
            output = []
            self.assertTrue(death_counter_command(self.ctx, output.append))
            self.assertIn("You: 1 (0 deathlink)", output[0])
            self.assertNotIn("Overview", output[0])
            self.assertEqual(self.storage["nsmbds"][self.client._death_counter_key()]["total"], 1)
        self.assertIn("Deaths: 1", render_tracker_markup(build_tracker_snapshot(self.ctx)))

    async def test_chat_report_is_short_and_contains_only_counters(self):
        self.client._death_count = 8
        self.client._death_link_death_count = 3
        self.client._death_link_amnesty_count = 2
        self.client._death_link_cooldown_until = 105
        self.client._pending_death_link = True
        self.client._pending_death_link_effect = DEATH_LINK_EFFECT_TIMER_DRAIN
        self.ctx.slot_data.update(
            death_link_effect=4, death_link_random_effects=["timer_drain", "lose_all_coins"],
            death_link_amnesty=3, death_link_grace_percentage=50,
            death_link_cooldown_seconds=10, death_link_triggers_on_insured_death=False,
        )
        output = []
        self.assertTrue(death_counter_command(self.ctx, output.append))
        report = output[0]
        self.assertEqual(report, "Deathcounter\nYou: 8 (3 deathlink)")
        for detail in ("Grace", "Cooldown", "Amnesty", "Waiting", "Random", "Insured", "Overview"):
            self.assertNotIn(detail, report)
        self.ctx.send_msgs.assert_not_awaited()
        self.ctx.send_death.assert_not_awaited()
        self.assertEqual(self.client._death_count, 8)

    async def test_chat_status_without_seed_or_with_arguments_is_actionable(self):
        output = []
        self.assertFalse(death_counter_command(SimpleNamespace(slot_data=None, slot=None), output.append))
        self.assertIn("Connect to an NSMBDS seed", output.pop())
        self.assertFalse(death_counter_command(self.ctx, output.append, "on"))
        self.assertEqual("Usage: /deathcounter", output.pop())
        self.assertFalse(self.client._pending_death_link)

    async def test_chat_status_handles_partial_shared_counts_and_player_names(self):
        self.client._other_death_counts[2] = {"total": 7}
        self.ctx.player_names[2] = "Luigi\nYour deaths"
        output = []
        self.assertTrue(death_counter_command(self.ctx, output.append))
        self.assertIn("Luigi Your deaths: 7", output[0])
        self.assertNotIn("\nYour deaths", output[0])
