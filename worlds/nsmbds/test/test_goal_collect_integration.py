"""Exercise Core's cross-world Collect against local NSMBDS goal detection."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from MultiServer import (
    Context,
    collect_player,
    get_checked_checks,
    get_missing_checks,
    get_received_items,
    register_location_checks,
    update_client_status,
)
from NetUtils import ClientStatus, LocationStore, NetworkSlot, SlotType
from worlds.nsmbds.client import NSMBDSClient
from worlds.nsmbds.client.features.goals import FINAL_BOSS_LOCATION_ID
from worlds.nsmbds.data import ram_addresses as ram
from worlds.nsmbds.locations import LOCATION_TABLE


class TestGoalCollectIntegration(IsolatedAsyncioTestCase):
    def setUp(self):
        self.boss_id = FINAL_BOSS_LOCATION_ID
        self.castle_goal_id = LOCATION_TABLE["World 8-Bowser's Castle Goal"]
        self.normal_id = LOCATION_TABLE["World 1-1 Goal"]
        self.server = Context("", 0, "", "", 0, 0, False, release_mode="auto", collect_mode="goal")
        self.server.seed_name = "collect-goal-regression"
        self.server.slot_info = {
            1: NetworkSlot("Mario", "New Super Mario Bros. DS", SlotType.player),
            2: NetworkSlot("Collector", "Other Game", SlotType.player),
            3: NetworkSlot("Unrelated Mario", "New Super Mario Bros. DS", SlotType.player),
        }
        self.server.player_names = {(0, slot): info.name for slot, info in self.server.slot_info.items()}
        self.server.clients = {0: {1: [], 2: [], 3: []}}
        self.server.locations = LocationStore({
            1: {
                self.boss_id: (1001, 2, 0),
                self.castle_goal_id: (1002, 1, 0),
                self.normal_id: (1003, 1, 0),
            },
            2: {20001: (2001, 2, 0)},
            3: {self.boss_id: (3001, 3, 0)},
        })
        # All location/item/status logic stays real. Network output and disk
        # persistence are replaced because no external room participates.
        self.server.broadcast_text_all = Mock()
        self.server.broadcast_team = Mock()
        self.server.broadcast = Mock()
        self.server.save = Mock()
        self.server.logger = Mock()
        self.owner_endpoint = SimpleNamespace(team=0, slot=1)
        self.collector_endpoint = SimpleNamespace(team=0, slot=2)
        self.sent_messages = []
        data = bytearray(ram.LOCATION_DATA_SNAPSHOT_SIZE)
        for offset in ram.LEVEL_DATA_WORLD_HEADER_OFFSETS:
            data[offset] = ram.LEVEL_DATA_WORLD_HEADER_VALUE
        self.uncleared_save = bytes(data)

    def connect_owner(self, client_type=NSMBDSClient):
        checked = get_checked_checks(self.server, 0, 1)
        missing = get_missing_checks(self.server, 0, 1)

        async def send_msgs(messages):
            self.sent_messages.extend(messages)
            for message in messages:
                if message["cmd"] == "LocationChecks":
                    register_location_checks(self.server, 0, 1, message["locations"])
                elif message["cmd"] == "StatusUpdate":
                    update_client_status(
                        self.server, self.owner_endpoint, ClientStatus(message["status"])
                    )
                else:
                    self.fail(f"Unexpected client command: {message}")

        ctx = SimpleNamespace(
            server_seed_name=self.server.seed_name, team=0, slot=1,
            slot_data={"goal": 0}, checked_locations=set(checked),
            missing_locations=set(missing), items_received=[], finished_game=False,
            server=SimpleNamespace(socket=SimpleNamespace(open=True, closed=False)),
            send_msgs=send_msgs,
        )
        client = client_type()
        client._item_cursor_loaded = True
        client._configure_death_counter = Mock()
        client.on_package(ctx, "Connected", {
            "team": 0, "slot": 1, "checked_locations": checked, "missing_locations": missing,
        })
        return client, ctx

    def finish_collector(self):
        update_client_status(self.server, self.collector_endpoint, ClientStatus.CLIENT_GOAL)

    async def test_another_players_goal_and_release_leave_bowser_unchecked(self):
        self.finish_collector()
        self.assertEqual(self.server.client_game_state[0, 2], ClientStatus.CLIENT_GOAL)
        self.assertEqual(get_checked_checks(self.server, 0, 2), [20001])
        self.assertNotIn(self.boss_id, get_checked_checks(self.server, 0, 1))
        client, ctx = self.connect_owner()
        await client._detect_and_send_locations(ctx, self.uncleared_save)
        await client._send_goal_if_complete(ctx, self.uncleared_save)
        self.assertFalse(ctx.finished_game)
        self.assertFalse(self.sent_messages)
        self.assertNotEqual(self.server.client_game_state[0, 1], ClientStatus.CLIENT_GOAL)
        self.assertNotEqual(self.server.client_game_state[0, 3], ClientStatus.CLIENT_GOAL)

    async def test_collect_checks_foreign_boss_item_without_local_victory(self):
        self.finish_collector()
        collect_player(self.server, 0, 2)
        self.assertEqual(get_checked_checks(self.server, 0, 1), [self.boss_id])
        self.assertIn(self.castle_goal_id, get_missing_checks(self.server, 0, 1))
        self.assertTrue(any(
            item.item == 1001 and item.location == self.boss_id and item.player == 1
            for item in get_received_items(self.server, 0, 2, True)
        ))
        self.assertEqual(get_checked_checks(self.server, 0, 3), [])
        for _ in range(2):
            client, ctx = self.connect_owner()
            self.assertIn(self.boss_id, client._observed_locations)
            self.assertTrue(client._is_game_data_ready(self.uncleared_save))
            await client._detect_and_send_locations(ctx, self.uncleared_save)
            await client._send_goal_if_complete(ctx, self.uncleared_save)
            self.assertFalse(ctx.finished_game)
        self.assertFalse(self.sent_messages)
        self.assertNotEqual(self.server.client_game_state[0, 1], ClientStatus.CLIENT_GOAL)
        self.assertNotEqual(self.server.client_game_state[0, 3], ClientStatus.CLIENT_GOAL)

    async def test_actual_local_victory_after_collect_still_goals_and_releases(self):
        self.finish_collector()
        collect_player(self.server, 0, 2)
        client, ctx = self.connect_owner()
        data = bytearray(self.uncleared_save)
        data[187] = 0x90  # Final castle's active node and normal completion bits.
        await client._detect_and_send_locations(ctx, bytes(data))
        await client._send_goal_if_complete(ctx, bytes(data))
        self.assertTrue(ctx.finished_game)
        self.assertEqual(self.server.client_game_state[0, 1], ClientStatus.CLIENT_GOAL)
        self.assertEqual(get_missing_checks(self.server, 0, 1), [])
        self.assertEqual(
            [msg for msg in self.sent_messages if msg["cmd"] == "StatusUpdate"],
            [{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}],
        )
        self.assertEqual(get_checked_checks(self.server, 0, 3), [])
        self.assertNotEqual(self.server.client_game_state[0, 3], ClientStatus.CLIENT_GOAL)
