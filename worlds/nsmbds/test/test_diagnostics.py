"""Diagnostics keep support output bounded and usable without an active session."""

from types import SimpleNamespace
from unittest import TestCase

from worlds.nsmbds.items import ITEM_TABLE
from worlds.nsmbds.client.diagnostics import (
    DiagnosticState,
    build_diagnostic_snapshot,
    format_full,
    format_short,
    parse_diagnostic_mode,
)


class TestDiagnostics(TestCase):
    def test_command_modes(self):
        self.assertEqual(parse_diagnostic_mode(""), "short")
        self.assertEqual(parse_diagnostic_mode("short"), "short")
        self.assertEqual(parse_diagnostic_mode("full"), "full")
        self.assertIsNone(parse_diagnostic_mode("full extra"))

    def test_empty_disconnected_snapshot(self):
        ctx = SimpleNamespace(
            server=None, bizhawk_ctx=SimpleNamespace(connection_status=None),
            slot_data=None, client_handler=None, items_received=[],
            checked_locations=set(), missing_locations=set(),
            nsmbds_diagnostics=DiagnosticState(),
        )
        snapshot = build_diagnostic_snapshot(ctx)
        short = format_short(snapshot)
        full = format_full(snapshot)
        self.assertIn("State: Disconnected", short)
        self.assertIn("Pending Items: 0", short)
        self.assertNotIn("Session ID", short)
        self.assertIn("Session ID", full)
        self.assertIn("Recent Events", full)

    def test_event_ring_bounds_and_order(self):
        state = DiagnosticState()
        for number in range(55):
            state.event("ITEM", str(number))
        self.assertEqual(len(state.events), 50)
        self.assertEqual(state.events[0].event, "5")
        self.assertEqual(state.events[-1].event, "54")

    def test_game_status_records_transitions_only(self):
        state = DiagnosticState()
        state.game_status("Ready")
        state.game_status("Ready")
        self.assertEqual(len(state.events), 1)
        self.assertIsNotNone(state.last_ready_at)
        state.game_status("Read unavailable")
        self.assertEqual(len(state.events), 2)

    def test_error_label_keeps_operation_without_leaking_path(self):
        state = DiagnosticState()
        state.error("items", "deferred item application")
        state.error("locations", "C:/Users/private/rom.nds")
        self.assertEqual(state.last_errors["items"][1], "deferred item application")
        self.assertEqual(state.last_errors["locations"][1], "Error")

    def test_new_slot_clears_seed_data_but_keeps_connection_history(self):
        state = DiagnosticState()
        state.network.change(True)
        state.last_received_index = 42
        state.counters["items_received"] = 43
        state.error("items", "item application")
        state.reset_slot()
        self.assertIsNone(state.last_received_index)
        self.assertFalse(state.counters)
        self.assertFalse(state.last_errors)
        self.assertEqual(state.events[-1].event, "slot changed")
        self.assertEqual(state.network.state, "Connected")

    def test_sensitive_context_fields_are_excluded(self):
        secret = "C:/Users/private/secret-rom.nds"
        ctx = SimpleNamespace(
            server=None, server_address="password@secret-server", password="secret-password",
            bizhawk_ctx=SimpleNamespace(connection_status=None), slot_data=None,
            client_handler=None, items_received=[], checked_locations=set(),
            missing_locations=set(), server_seed_name=secret,
            nsmbds_diagnostics=DiagnosticState(),
        )
        output = format_full(build_diagnostic_snapshot(ctx))
        for value in (secret, "secret-password", "secret-server", "C:/Users/private"):
            self.assertNotIn(value, output)

    def test_full_uses_cached_bridge_versions_and_omits_unavailable_fields(self):
        mushroom_id = ITEM_TABLE["Mushroom"][0]
        state = DiagnosticState()
        state.bizhawk_version = "2.11.1"
        state.connector_script_version = 1
        state.lua_runtime_version = "v0.5.1-unstable"
        handler = SimpleNamespace(
            _deferred_item_ids=[mushroom_id], _items_received_index=1,
            _observed_locations=set(), _sent_locations=set(),
            _active_location_set_known=False, _item_cursor_loaded=True,
        )
        ctx = SimpleNamespace(
            server=None, bizhawk_ctx=SimpleNamespace(connection_status=SimpleNamespace(name="CONNECTED")),
            slot_data={"level_randomization": 0}, client_handler=handler,
            items_received=[SimpleNamespace(item=mushroom_id)], checked_locations=set(),
            missing_locations=set(), nsmbds_diagnostics=state,
        )
        output = format_full(build_diagnostic_snapshot(ctx))
        self.assertIn("Version: 2.11.1", output)
        self.assertIn("Connector Script Version: 1", output)
        self.assertIn("Lua Runtime Version: v0.5.1-unstable", output)
        self.assertEqual(output.count("  Mushroom"), 1)
        self.assertIn("Game Data Status: Waiting for AP slot", output)
        self.assertNotIn("Active Trap: None", output)
        self.assertNotIn("Received This Session", output)
        self.assertNotIn("Mapping Hash", output)
        self.assertNotIn("Patch Version", output)
        self.assertNotIn("Unknown", output)
