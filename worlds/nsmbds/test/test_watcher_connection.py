"""Bridge failures end a watcher pass without losing pending gameplay work."""

import struct
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from worlds._bizhawk import ConnectionStatus, NotConnectedError, RequestFailedError
from worlds.nsmbds.client import NSMBDSClient
from worlds.nsmbds.client.transport import NSMBDSBizHawkContext
from worlds.nsmbds.data import ram_addresses as ram
from worlds.nsmbds.items import ITEM_TABLE
from worlds.nsmbds.locations import LOCATION_TABLE


class TestWatcherConnection(IsolatedAsyncioTestCase):
    def watcher_fixture(self):
        client = NSMBDSClient()
        ctx = SimpleNamespace(
            bizhawk_ctx=NSMBDSBizHawkContext(),
            server=SimpleNamespace(socket=SimpleNamespace(open=True, closed=False)),
            slot=1, slot_data={"red_coin_checks": True},
            send_msgs=AsyncMock(), observe_bridge=Mock(),
        )
        # Keep the real watcher scheduler, Red Coin read, submission and ACK.
        # Other features are isolated so a socket reset has one clear trigger.
        for name in (
            "_sync_emulator_feed", "_sync_star_coin_tracking",
            "_sync_native_block_configuration", "_read_level_data",
            "_apply_pending_items", "_sync_death_link", "_detect_and_send_block_check",
            "_detect_and_send_locations", "_handle_death_link", "_apply_pending_timer_drains",
            "_apply_pending_starman_buffs", "_apply_pending_filler_bonuses",
            "_apply_pending_speed_traps", "_publish_next_ap_notification",
            "_flush_emulator_feed", "_detect_and_store_gate_purchases",
            "_reconcile_overworld_state", "_send_goal_if_complete",
            "_sync_gate_purchase_storage", "_initialize_bonus_mailbox",
            "_sync_poptracker_world", "_sync_powerup_licenses",
        ):
            setattr(client, name, AsyncMock())
        client._sync_native_block_configuration.return_value = True
        data = bytearray(ram.LOCATION_DATA_SNAPSHOT_SIZE)
        for offset in ram.LEVEL_DATA_WORLD_HEADER_OFFSETS:
            data[offset] = ram.LEVEL_DATA_WORLD_HEADER_VALUE
        client._read_level_data.return_value = bytes(data)
        client._active_location_set_known = True
        client._active_locations = {LOCATION_TABLE["World 1-1 Red Coin Challenge"]}
        return client, ctx

    async def test_windows_socket_reset_stops_pass_and_red_coin_retries(self):
        client, ctx = self.watcher_fixture()
        reader = SimpleNamespace(readline=AsyncMock(side_effect=ConnectionResetError(64, "Connection lost")))
        writer = SimpleNamespace(write=Mock(), drain=AsyncMock(), close=Mock())
        ctx.bizhawk_ctx.streams = (reader, writer)
        ctx.bizhawk_ctx.connection_status = ConnectionStatus.CONNECTED

        with self.assertLogs("NSMBDS", level="INFO") as logs:
            await client.game_watcher(ctx)
        writer.close.assert_called_once()
        self.assertIsNone(ctx.bizhawk_ctx.streams)
        self.assertEqual(ctx.bizhawk_ctx.connection_status, ConnectionStatus.NOT_CONNECTED)
        client._detect_and_send_block_check.assert_not_awaited()
        client._handle_death_link.assert_not_awaited()
        ctx.send_msgs.assert_not_awaited()
        ctx.observe_bridge.assert_called_once()
        self.assertEqual(len(logs.records), 1)
        self.assertIn("BizHawk connection lost", logs.output[0])
        self.assertIsNone(logs.records[0].exc_info)
        self.assertFalse(client._sent_locations)

        mailbox = [
            bytes([12]), bytes([ram.AP_EVENT_TYPE_RED_COIN_COMPLETE]),
            struct.pack("<I", 0), struct.pack("<I", 1), struct.pack("<I", 0),
            struct.pack("<i", 50), bytes([1]), bytes([11]), bytes([12]),
        ]
        with patch("worlds._bizhawk.read", AsyncMock(return_value=mailbox)), \
                patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)) as acknowledge:
            await client.game_watcher(ctx)
        location_id = LOCATION_TABLE["World 1-1 Red Coin Challenge"]
        ctx.send_msgs.assert_awaited_once_with([{"cmd": "LocationChecks", "locations": [location_id]}])
        self.assertIn(location_id, client._sent_locations)
        self.assertEqual(acknowledge.await_args.args[1], [
            (ram.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, [12], ram.MEMORY_DOMAIN),
        ])
        client._detect_and_send_block_check.assert_awaited_once()

    async def test_connection_timeout_is_not_reported_as_gameplay_stall(self):
        client = NSMBDSClient()
        ctx = SimpleNamespace(observe_bridge=Mock())

        async def run(_ctx):
            await client._run_watcher_operation(
                "Red Coin detection", AsyncMock(side_effect=RequestFailedError("Connection timed out"))()
            )

        client._run_game_watcher = run
        with patch("worlds.nsmbds.client.perf_counter", side_effect=[0, 0, 5, 5, 5]), \
                self.assertLogs("NSMBDS", level="INFO") as logs:
            await client.game_watcher(ctx)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Connection timed out", logs.output[0])
        self.assertFalse(client._watcher_slow_log_times)

    async def test_read_helpers_propagate_connection_failures(self):
        client = NSMBDSClient()
        ctx = SimpleNamespace(bizhawk_ctx=NSMBDSBizHawkContext())
        for error in (NotConnectedError, RequestFailedError):
            for read_state in (client._read_level_data, client._read_lives_and_timer):
                with self.subTest(error=error.__name__, reader=read_state.__name__), \
                        patch("worlds._bizhawk.read", AsyncMock(side_effect=error("Connection lost"))):
                    with self.assertRaises(error):
                        await read_state(ctx)

    async def test_disconnect_does_not_create_later_maintenance_coroutines(self):
        for failed, skipped in (
            ("_handle_death_link", "_apply_pending_timer_drains"),
            ("_detect_and_store_gate_purchases", "_reconcile_overworld_state"),
        ):
            with self.subTest(operation=failed):
                client, ctx = self.watcher_fixture()
                client._detect_and_send_red_coin_challenge = AsyncMock()
                getattr(client, failed).side_effect = NotConnectedError("Connection lost")
                with self.assertLogs("NSMBDS", level="INFO"):
                    await client.game_watcher(ctx)
                getattr(client, skipped).assert_not_called()

    async def test_unexpected_feature_errors_still_have_tracebacks(self):
        client = NSMBDSClient()
        with self.assertLogs("NSMBDS", level="ERROR") as logs:
            result = await client._run_watcher_operation(
                "Red Coin detection", AsyncMock(side_effect=ValueError("Invalid event"))()
            )
        self.assertIsNone(result)
        self.assertIsNotNone(logs.records[0].exc_info)
        self.assertIn("Invalid event", logs.output[0])

    async def test_item_disconnect_preserves_cursor_and_transaction(self):
        client = NSMBDSClient()
        item_id = ITEM_TABLE["Coin Bundle"][0]
        ctx = SimpleNamespace(items_received=[SimpleNamespace(item=item_id)] * 2)
        client._missing_powerup_license = Mock(return_value=None)
        client._persist_item_cursor = Mock(return_value=True)
        client._queue_item_receipt = Mock()
        pending = {"owner": "network", "item_id": item_id}

        async def apply(_ctx, _item_id):
            if client._items_received_index == 0:
                return True
            client._pending_item_transaction = pending
            raise RequestFailedError("Connection closed before ACK")

        client._apply_item = AsyncMock(side_effect=apply)
        with self.assertRaises(RequestFailedError):
            await client._apply_pending_items(ctx)
        self.assertEqual(client._items_received_index, 1)
        self.assertIs(client._pending_item_transaction, pending)
        self.assertFalse(client._deferred_item_ids)
        client._persist_item_cursor.assert_called_once()
        client._queue_item_receipt.assert_called_once_with(item_id)

        client._apply_item = AsyncMock(return_value=True)
        await client._apply_pending_items(ctx)
        self.assertEqual(client._items_received_index, 2)
        self.assertIsNone(client._pending_item_transaction)

    async def test_deferred_disconnect_preserves_queue_and_selection(self):
        client = NSMBDSClient()
        item_id = ITEM_TABLE["Mushroom"][0]
        pending = {"owner": "deferred", "item_id": item_id}
        client._deferred_item_ids = [item_id, item_id]
        client._next_powerup_id = item_id
        client._next_powerup_mode = "manual"
        client._pending_item_transaction = pending
        client._persist_item_cursor = Mock(return_value=True)
        client._apply_item = AsyncMock(side_effect=NotConnectedError("Connection lost"))
        with self.assertRaises(NotConnectedError):
            await client._retry_one_deferred_item(SimpleNamespace())
        self.assertEqual(client._deferred_item_ids, [item_id, item_id])
        self.assertEqual(client._next_powerup_id, item_id)
        self.assertIs(client._pending_item_transaction, pending)
        client._persist_item_cursor.assert_called_once()
