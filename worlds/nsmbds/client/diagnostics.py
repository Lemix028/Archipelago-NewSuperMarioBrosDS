"""Read-only, bounded support diagnostics for the dedicated NSMBDS client.

Existing sources: CommonContext items/locations/slot data, BizHawk connection
status, NSMBDS item cursor and deferred reserve queue, sent/observed locations,
pending trap counters, DeathLink cooldown, and the cached level mapping digest.
Only connection history, event history, and last event identifiers are new.
"""

from __future__ import annotations

import logging
import hashlib
import platform
import re
import sys
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..items import item_id_to_name
from ..locations import BLOCKSANITY_LOCATION_IDS, LOCATION_TABLE
from ..version import DISPLAY_VERSION

logger = logging.getLogger("NSMBDS.Diag")
_location_names = {identifier: name for name, identifier in LOCATION_TABLE.items()}


@dataclass(frozen=True)
class DiagnosticEvent:
    timestamp: datetime
    subsystem: str
    event: str
    details: str = ""


@dataclass
class ConnectionHistory:
    state: str = "Disconnected"
    connected_at: datetime | None = None
    last_disconnect_at: datetime | None = None
    last_reconnect_at: datetime | None = None
    disconnect_count: int = 0
    reconnect_count: int = 0
    last_error: str | None = None
    ever_connected: bool = False

    def change(self, connected: bool, reason: str | None = None) -> bool:
        target = "Connected" if connected else "Disconnected"
        if self.state == target:
            return False
        now = datetime.now()
        self.state = target
        if connected:
            self.connected_at = now
            if self.ever_connected:
                self.reconnect_count += 1
                self.last_reconnect_at = now
            self.ever_connected = True
        else:
            self.disconnect_count += 1
            self.last_disconnect_at = now
            self.last_error = reason
        return True


@dataclass
class DiagnosticState:
    started_at: float = field(default_factory=time.monotonic)
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    network: ConnectionHistory = field(default_factory=ConnectionHistory)
    bridge: ConnectionHistory = field(default_factory=ConnectionHistory)
    bridge_state: str = "DISCONNECTED"
    events: deque[DiagnosticEvent] = field(default_factory=lambda: deque(maxlen=50))
    counters: Counter[str] = field(default_factory=Counter)
    last_errors: dict[str, tuple[datetime, str, str]] = field(default_factory=dict)
    last_received_index: int | None = None
    last_queued_index: int | None = None
    last_applied_index: int | None = None
    last_applied_item: int | None = None
    last_detected_location: int | None = None
    last_submitted_location: int | None = None
    last_deathlink_sent: datetime | None = None
    last_deathlink_received: datetime | None = None
    bizhawk_version: str | None = None
    lua_runtime_version: str | None = None
    connector_script_version: int | None = None
    game_data_status: str = "Not read"
    last_ready_at: float | None = None

    def event(self, subsystem: str, event: str, details: str = "") -> None:
        self.events.append(DiagnosticEvent(datetime.now(), subsystem, event, details))

    def error(self, subsystem: str, error: BaseException | str) -> None:
        kind = type(error).__name__ if isinstance(error, BaseException) else (
            error if re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]{0,60}", error) else "Error"
        )
        # Error text may include a local path or credential. Keep it in the normal log only.
        self.last_errors[subsystem] = (datetime.now(), kind, "")
        self.event(subsystem.upper(), "error", kind)

    def game_status(self, status: str) -> None:
        if self.game_data_status != status:
            self.game_data_status = status
            self.event("GAME", "data", status)
        if status == "Ready":
            self.last_ready_at = time.monotonic()

    def reset_slot(self) -> None:
        self.events.clear()
        self.counters.clear()
        self.last_errors.clear()
        self.last_received_index = None
        self.last_queued_index = None
        self.last_applied_index = None
        self.last_applied_item = None
        self.last_detected_location = None
        self.last_submitted_location = None
        self.last_deathlink_sent = None
        self.last_deathlink_received = None
        self.game_data_status = "Not read"
        self.last_ready_at = None
        self.event("NETWORK", "slot changed")


def _clock(value: datetime | None) -> str:
    return value.strftime("%H:%M:%S") if value else "Unknown"


def parse_diagnostic_mode(argument: str) -> str | None:
    mode = argument.strip()
    return "short" if mode == "" else mode if mode in {"short", "full"} else None


def _name(identifier: int | None, lookup: dict[int, str]) -> str:
    return lookup.get(identifier, f"ID {identifier}") if identifier is not None else "None"


def _connection_status(ctx: Any) -> tuple[bool, bool]:
    server = getattr(ctx, "server", None)
    socket = getattr(server, "socket", None)
    ap = socket is not None and not getattr(socket, "closed", True)
    connection = getattr(getattr(ctx, "bizhawk_ctx", None), "connection_status", None)
    return ap, getattr(connection, "name", "") == "CONNECTED"


def build_diagnostic_snapshot(ctx: Any) -> dict[str, Any]:
    """Copy existing state only; this function performs no I/O or emulator calls."""
    state: DiagnosticState = getattr(ctx, "nsmbds_diagnostics", None) or DiagnosticState()
    handler = getattr(ctx, "client_handler", None)
    slot_data = getattr(ctx, "slot_data", None) or {}
    items = getattr(ctx, "items_received", ())
    checked = getattr(ctx, "checked_locations", ())
    missing = getattr(ctx, "missing_locations", ())
    ap_connected, bridge_connected = _connection_status(ctx)
    mapping = slot_data.get("level_mapping")
    mapping = mapping if isinstance(mapping, dict) else {}
    mode = slot_data.get("level_randomization", 0)
    deferred = tuple(getattr(handler, "_deferred_item_ids", ()))
    unsent_locations = set(getattr(handler, "_observed_locations", ())) - set(getattr(handler, "_sent_locations", ()))
    if getattr(handler, "_active_location_set_known", False):
        unsent_locations.intersection_update(getattr(handler, "_active_locations", ()))
    pending_traps = {
        name.removeprefix("_pending_").removesuffix("_traps").replace("_", " "): value
        for name, value in vars(handler).items()
        if name.startswith("_pending_") and name.endswith("_traps") and isinstance(value, int) and value > 0
    } if handler is not None else {}
    timer_drains = getattr(handler, "_pending_timer_drains", 0)
    if timer_drains > 0:
        pending_traps["timer drain"] = timer_drains
    speed_remaining = max(0.0, getattr(handler, "_speed_trap_end_time", 0) - time.monotonic())
    snapshot = {
        "client": {"Version": DISPLAY_VERSION, "AP Version": str(getattr(sys.modules.get("Utils"), "__version__", "Unknown")),
                   "Platform": platform.system(), "Python Version": platform.python_version(),
                   "Session ID": state.session_id, "Captured At": datetime.now().astimezone().isoformat(timespec="seconds"),
                   "Debug Logging": "On" if logging.getLogger("NSMBDS").isEnabledFor(logging.DEBUG) else "Off",
                   "Uptime": time.strftime("%H:%M:%S", time.gmtime(time.monotonic() - state.started_at))},
        "archipelago": {"State": "Connected" if ap_connected else "Disconnected", "Slot Data": "Loaded" if getattr(ctx, "slot_data", None) is not None else "Not Loaded",
                        "Team": getattr(ctx, "team", None), "Received Items": len(items), "Checked Locations": len(checked),
                        "Missing Locations": len(missing), "Connected Since": _clock(state.network.connected_at),
                        "Disconnects": state.network.disconnect_count, "Reconnects": state.network.reconnect_count,
                        "Last Disconnect": _clock(state.network.last_disconnect_at)},
        "bizhawk": {"State": "Connected" if bridge_connected else "Disconnected", "Bridge State": state.bridge_state,
                    "Connected Since": _clock(state.bridge.connected_at), "Disconnects": state.bridge.disconnect_count,
                    "Reconnects": state.bridge.reconnect_count, "Last Disconnect": _clock(state.bridge.last_disconnect_at),
                    "Last Reconnect": _clock(state.bridge.last_reconnect_at), "Last Disconnect Reason": state.bridge.last_error or "Unknown"},
        "rom": {"Region": "USA" if handler is not None else None,
                "AP Seed Fingerprint": hashlib.sha256(str(getattr(ctx, "server_seed_name")).encode()).hexdigest()[:8] if getattr(ctx, "server_seed_name", None) else None,
                "Slot ID": getattr(ctx, "slot", None),
                "Star Coin Gate Gap": slot_data.get("star_coin_gate_gap", 5),
                "Gate Purchase Price": slot_data.get("star_coin_gate_gap", 5)},
        "sync": {"Received Item Index": state.last_received_index, "Queued Item Index": state.last_queued_index,
                 "Last Directly Applied Index": state.last_applied_index,
                 "Unprocessed Item Entries": max(0, len(items) - getattr(handler, "_items_received_index", 0)),
                 "Pending Items": max(0, len(items) - getattr(handler, "_items_received_index", 0)) + len(deferred),
                 "Last Received Item": _name(items[-1].item, item_id_to_name) if items else "None",
                 "Last Applied Item": _name(state.last_applied_item, item_id_to_name),
                 "Detected For Current Slot": state.counters["locations_detected"], "Known Checked Locations": len(getattr(handler, "_sent_locations", ())),
                 "Pending Locations": len(unsent_locations),
                 "Last Detected Location": _name(state.last_detected_location, _location_names),
                 "Last Submitted Location": _name(state.last_submitted_location, _location_names),
                 "Pending Location Entries": [_name(i, _location_names) for i in sorted(unsent_locations)[:10]],
                 "Pending Location Extra": max(0, len(unsent_locations) - 10)},
        "reserve": {"Queue Size": len(deferred), "Persistence Loaded": bool(getattr(handler, "_item_cursor_loaded", False)),
                    "Mode": getattr(handler, "reserve_mode", "automatic").title(),
                    "Delivery Pending": bool(handler and callable(getattr(handler, "reserve_delivery_pending", None))
                                             and handler.reserve_delivery_pending()),
                    "Selected Item": _name(getattr(handler, "_next_powerup_id", None), item_id_to_name),
                    "Entries": [_name(i, item_id_to_name) for i in deferred[:10]], "Extra": max(0, len(deferred) - 10)},
        "game": {"Game Data Status": (
                     state.game_data_status if ap_connected and getattr(ctx, "slot", None) is not None
                     and getattr(ctx, "slot_data", None) is not None else "Waiting for AP slot"
                 ) if bridge_connected and handler is not None else None,
                 "Last Ready Read Ago": f"{time.monotonic() - state.last_ready_at:.1f}s" if bridge_connected and state.last_ready_at is not None else None},
        "traps": {"Speed Trap Remaining": round(speed_remaining, 1) if speed_remaining > 0 else None,
                  "Pending Trap Count": sum(pending_traps.values()), "Pending": list(pending_traps.items())[:10]},
        "deathlink": {"Enabled": bool(slot_data.get("death_link", False)),
                      "Effect": {0: "Death", 1: "Damage", 2: "100-Second Timer Drain", 3: "Lose All Coins", 4: "Random"}.get(slot_data.get("death_link_effect", 0), "Other"),
                      "Grace": f"{slot_data['death_link_grace_percentage']}%" if "death_link_grace_percentage" in slot_data else None,
                      "Cooldown": f"{slot_data['death_link_cooldown_seconds']}s" if "death_link_cooldown_seconds" in slot_data else None,
                      "Cooldown Active": getattr(handler, "_death_link_cooldown_until", 0) > time.monotonic(),
                      "Pending Effect": bool(getattr(handler, "_pending_death_link", False)),
                      "Last Sent": _clock(state.last_deathlink_sent), "Last Received Signal": _clock(state.last_deathlink_received)},
        "level": {"Enabled": bool(mode)},
        "blocksanity": {"Enabled": bool(slot_data.get("blocksanity", False)),
                        "Selected Blocks": len(set(checked) & BLOCKSANITY_LOCATION_IDS) + len(set(missing) & BLOCKSANITY_LOCATION_IDS),
                        "Collected Blocks": len(set(checked) & BLOCKSANITY_LOCATION_IDS)},
        "errors": dict(state.last_errors), "events": tuple(state.events),
    }
    snapshot["bizhawk"]["Version"] = state.bizhawk_version if bridge_connected else None
    snapshot["bizhawk"]["Connector Script Version"] = state.connector_script_version if bridge_connected else None
    snapshot["bizhawk"]["Lua Runtime Version"] = state.lua_runtime_version if bridge_connected else None
    rom_hash = str(getattr(ctx, "rom_hash", "") or "")
    if re.fullmatch(r"[0-9A-Fa-f]{40,64}", rom_hash):
        snapshot["rom"]["ROM Hash"] = rom_hash[:12].upper()
    snapshot["sync"]["Item Cursor"] = getattr(handler, "_items_received_index", None)
    snapshot["sync"]["Item History Ready"] = not (
        getattr(handler, "_awaiting_item_history", False)
        or getattr(handler, "_item_cursor_needs_initial_sync", False)
    ) if handler is not None and ap_connected else None
    if mode:
        mapping_digest = getattr(handler, "_level_mapping_digest", None)
        snapshot["level"].update({
            "Mode": {1: "Global", 2: "Within World"}.get(mode, str(mode)),
            "Mapping Loaded": bool(mapping),
            "Mapping Entries": len(mapping),
            "Mapping Hash": str(mapping_digest)[:8] if mapping_digest else None,
        })
    if not slot_data.get("death_link", False):
        snapshot["deathlink"] = {"Enabled": False}
    if not snapshot["blocksanity"]["Enabled"]:
        snapshot["blocksanity"] = {"Enabled": False}
    for section in ("client", "archipelago", "bizhawk", "rom", "sync", "reserve", "game", "deathlink", "level", "traps"):
        snapshot[section] = {
            key: value for key, value in snapshot[section].items()
            if value is not None and value != "Unknown" and value != "None"
        }
    return snapshot


def _section(title: str, values: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    return [title, *(f"{key}: {values[key]}" for key in keys if key in values), ""]


def format_short(snapshot: dict[str, Any]) -> str:
    lines = ["=== NSMBDS Diagnostics ===", ""]
    for title, key, fields in (
        ("Client", "client", ("Version", "AP Version", "Platform", "Uptime")),
        ("Archipelago", "archipelago", ("State", "Slot Data", "Received Items", "Checked Locations", "Disconnects")),
        ("BizHawk", "bizhawk", ("State", "Version", "Bridge State", "Disconnects", "Reconnects")),
        ("ROM", "rom", ("Region", "ROM Hash", "AP Seed Fingerprint", "Slot ID")),
        ("Sync", "sync", ("Received Item Index", "Item Cursor", "Pending Items", "Pending Locations")),
        ("Game", "game", ("Game Data Status", "Last Ready Read Ago")),
        ("Deferred Items", "reserve", ("Queue Size",)),
    ):
        if not any(field in snapshot[key] for field in fields):
            continue
        lines.extend(_section(title, snapshot[key], fields))
    lines.append("========================")
    return "\n".join(lines)


def format_full(snapshot: dict[str, Any]) -> str:
    lines = ["=== NSMBDS Diagnostics (full) ===", ""]
    for title, key in (("Client", "client"), ("Archipelago", "archipelago"), ("BizHawk", "bizhawk"),
                       ("ROM", "rom"), ("Game", "game"), ("Item / Location Sync", "sync"), ("Level Randomizer", "level"),
                       ("Deferred Items", "reserve"), ("Traps", "traps"), ("DeathLink", "deathlink"),
                       ("Blocksanity", "blocksanity")):
        values = snapshot[key]
        if not values:
            continue
        lines.extend(_section(title, values, tuple(k for k in values if k not in {"Entries", "Extra", "Pending", "Pending Location Entries", "Pending Location Extra"})))
        if key == "reserve":
            lines.pop()
            if values["Entries"]:
                lines.append("Queued Items:")
            lines.extend(f"  {entry}" for entry in values["Entries"])
            extra = values["Extra"]
            if extra:
                lines.append(f"  ... +{extra} more")
            lines.append("")
        if key == "sync":
            lines.pop()
            if values["Pending Location Entries"]:
                lines.append("Pending Locations:")
            lines.extend(f"  Location: {entry}" for entry in values["Pending Location Entries"])
            if values["Pending Location Extra"]:
                lines.append(f"  ... +{values['Pending Location Extra']} more locations")
            lines.append("")
        if key == "traps":
            lines.pop()
            if values["Pending"]:
                lines.append("Queued Traps:")
            lines.extend(f"  {name}: {count}" for name, count in values["Pending"])
            lines.append("")
    lines.append("Last Errors")
    lines.extend(f"{name}: {kind} @ {_clock(when)}" for name, (when, kind, _message) in sorted(snapshot["errors"].items()))
    if not snapshot["errors"]:
        lines.append("None")
    lines.extend(["", "Recent Events"])
    lines.extend(f"{_clock(event.timestamp)} [{event.subsystem}] {event.event} {event.details}".rstrip()
                 for event in snapshot["events"][-30:])
    if not snapshot["events"]:
        lines.append("None")
    lines.append("=================================")
    return "\n".join(lines)
