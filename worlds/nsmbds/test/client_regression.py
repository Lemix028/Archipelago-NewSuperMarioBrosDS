"""Isolated regression checks for pure NSMBDS BizHawk client behavior."""

from __future__ import annotations

import asyncio
import builtins
import inspect
import hashlib
import importlib.util
import logging
import os
import struct
import sys
import tempfile
import types
from pathlib import Path


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NSMBDS_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CORE_ROOT = str(Path(SCRIPT_DIR).parents[2])
if CORE_ROOT not in sys.path:
    sys.path.insert(0, CORE_ROOT)


def load_module(name: str, filename: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeBizHawkClient:
    def __init__(self) -> None:
        pass


class FakeAutoBizHawkClientRegister:
    game_handlers = {}


fake_worlds = types.ModuleType("worlds")
fake_bizhawk = types.ModuleType("worlds._bizhawk")
fake_bizhawk_client = types.ModuleType("worlds._bizhawk.client")
fake_bizhawk.read = lambda *args, **kwargs: None
fake_bizhawk.write = lambda *args, **kwargs: None
fake_bizhawk.guarded_read = lambda *args, **kwargs: None
fake_bizhawk.guarded_write = lambda *args, **kwargs: None
fake_bizhawk.send_requests = lambda *args, **kwargs: None
fake_bizhawk.disconnect = lambda *args, **kwargs: None
fake_bizhawk_client.BizHawkClient = FakeBizHawkClient
fake_bizhawk_client.AutoBizHawkClientRegister = FakeAutoBizHawkClientRegister
fake_worlds._bizhawk = fake_bizhawk
sys.modules["worlds"] = fake_worlds
sys.modules["worlds._bizhawk"] = fake_bizhawk
sys.modules["worlds._bizhawk.client"] = fake_bizhawk_client

package = types.ModuleType("nsmbds")
package.__path__ = [NSMBDS_DIR]
package.__package__ = "nsmbds"
sys.modules["nsmbds"] = package

load_module("nsmbds.items", os.path.join(NSMBDS_DIR, "items.py"))
locations = load_module("nsmbds.locations", os.path.join(NSMBDS_DIR, "locations.py"))
ram_addresses = load_module("nsmbds.data.ram_addresses", os.path.join(NSMBDS_DIR, "data", "ram_addresses.py"))
client_module = load_module("nsmbds.client", os.path.join(NSMBDS_DIR, "client", "__init__.py"))
ui_module = load_module("nsmbds.client.ui", os.path.join(NSMBDS_DIR, "client", "ui", "__init__.py"))
powerup_licenses = sys.modules["nsmbds.data.powerup_licenses"]
buffs_module = sys.modules["nsmbds.client.features.buffs"]
tracker_module = load_module(
    "nsmbds.client.ui.tracker.state",
    os.path.join(NSMBDS_DIR, "client", "ui", "tracker", "state.py"),
)


class FakeGuiWidget:
    pass


class FakeGameManager:
    pass


fake_kivy = types.ModuleType("kivy")
fake_kivy_clock = types.ModuleType("kivy.clock")
fake_kivy_metrics = types.ModuleType("kivy.metrics")
fake_kivy_button = types.ModuleType("kivy.uix.button")
fake_kivy_checkbox = types.ModuleType("kivy.uix.checkbox")
fake_kivy_progressbar = types.ModuleType("kivy.uix.progressbar")
fake_kivy_slider = types.ModuleType("kivy.uix.slider")
fake_kivy_spinner = types.ModuleType("kivy.uix.spinner")
fake_kivy_utils = types.ModuleType("kivy.utils")
fake_kivymd = types.ModuleType("kivymd")
fake_kivymd_uix = types.ModuleType("kivymd.uix")
fake_kivymd_boxlayout = types.ModuleType("kivymd.uix.boxlayout")
fake_kivymd_button = types.ModuleType("kivymd.uix.button")
fake_kivymd_card = types.ModuleType("kivymd.uix.card")
fake_kivymd_gridlayout = types.ModuleType("kivymd.uix.gridlayout")
fake_kivymd_label = types.ModuleType("kivymd.uix.label")
fake_kivymd_progress = types.ModuleType("kivymd.uix.progressindicator")
fake_kivymd_scrollview = types.ModuleType("kivymd.uix.scrollview")
fake_kvui = types.ModuleType("kvui")
fake_kivy_clock.Clock = types.SimpleNamespace(
    schedule_interval=lambda *_args: None,
    schedule_once=lambda *_args: None,
)
fake_kivy_metrics.dp = lambda value: value
fake_kivy_button.Button = FakeGuiWidget
fake_kivy_checkbox.CheckBox = FakeGuiWidget
fake_kivy_progressbar.ProgressBar = FakeGuiWidget
fake_kivy_slider.Slider = FakeGuiWidget
fake_kivy_spinner.Spinner = FakeGuiWidget
fake_kivy_utils.escape_markup = lambda value: value
fake_kivymd_boxlayout.MDBoxLayout = FakeGuiWidget
fake_kivymd_button.MDButton = FakeGuiWidget
fake_kivymd_button.MDButtonText = FakeGuiWidget
fake_kivymd_card.MDCard = FakeGuiWidget
fake_kivymd_gridlayout.MDGridLayout = FakeGuiWidget
fake_kivymd_label.MDLabel = FakeGuiWidget
fake_kivymd_progress.MDLinearProgressIndicator = FakeGuiWidget
fake_kivymd_scrollview.MDScrollView = FakeGuiWidget
fake_kvui.GameManager = FakeGameManager
sys.modules.update({
    "kivy": fake_kivy,
    "kivy.clock": fake_kivy_clock,
    "kivy.metrics": fake_kivy_metrics,
    "kivy.uix.button": fake_kivy_button,
    "kivy.uix.checkbox": fake_kivy_checkbox,
    "kivy.uix.progressbar": fake_kivy_progressbar,
    "kivy.uix.slider": fake_kivy_slider,
    "kivy.uix.spinner": fake_kivy_spinner,
    "kivy.utils": fake_kivy_utils,
    "kivymd": fake_kivymd,
    "kivymd.uix": fake_kivymd_uix,
    "kivymd.uix.boxlayout": fake_kivymd_boxlayout,
    "kivymd.uix.button": fake_kivymd_button,
    "kivymd.uix.card": fake_kivymd_card,
    "kivymd.uix.gridlayout": fake_kivymd_gridlayout,
    "kivymd.uix.label": fake_kivymd_label,
    "kivymd.uix.progressindicator": fake_kivymd_progress,
    "kivymd.uix.scrollview": fake_kivymd_scrollview,
    "kvui": fake_kvui,
})
tracker_view_module = load_module(
    "nsmbds.client.ui.tracker.view",
    os.path.join(NSMBDS_DIR, "client", "ui", "tracker", "view.py"),
)
launcher_module = sys.modules["nsmbds.client.launcher"]


class FakeContext:
    def __init__(
        self,
        goal: int = 0,
        required_star_coins: int = 80,
        death_link: bool = False,
    ) -> None:
        self.slot_data = {
            "goal": goal,
            "required_star_coins": required_star_coins,
            "star_coin_checks": True,
            "red_coin_checks": True,
            "death_link": death_link,
        }
        self.finished_game = False
        self.server_seed_name = "seed-a"
        self.team = 1
        self.slot = 1
        self.checked_locations: set[int] = set()
        self.missing_locations: set[int] = set(locations.LOCATION_TABLE.values())
        self.bizhawk_ctx = object()
        self.game = None
        self.items_handling = None
        self.want_slot_data = False
        self.rom_hash = "test-hash"
        self.items_received = []


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def test_client_shutdown_wakes_and_disconnects_background_work() -> None:
    class FakeEvent:
        def __init__(self) -> None:
            self.was_set = False

        def set(self) -> None:
            self.was_set = True

    class FakeTask:
        def __init__(self) -> None:
            self.was_cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self.was_cancelled = True

    exit_event = FakeEvent()
    watcher_event = FakeEvent()
    feed_task = FakeTask()
    bizhawk_context = object()
    disconnected = []
    original_disconnect = fake_bizhawk.disconnect
    fake_bizhawk.disconnect = lambda ctx: disconnected.append(ctx)
    context = types.SimpleNamespace(
        exit_event=exit_event,
        watcher_event=watcher_event,
        client_handler=types.SimpleNamespace(_emulator_feed_flush_task=feed_task),
        bizhawk_ctx=bizhawk_context,
    )
    try:
        tracker_view_module.request_client_shutdown(context)
    finally:
        fake_bizhawk.disconnect = original_disconnect

    check(
        exit_event.was_set and watcher_event.was_set,
        "Closing the NSMBDS window immediately wakes the client and BizHawk watcher",
    )
    check(feed_task.was_cancelled, "Closing the NSMBDS window cancels a pending emulator-feed request")
    check(disconnected == [bizhawk_context], "Closing the NSMBDS window disconnects the BizHawk socket")


def test_kivy_hover_density_guard() -> None:
    observed_densities = []

    class FakeMouseProvider:
        def create_hover(self, win, _etype):
            observed_densities.append(win._density)
            return win._density

    ui_module.install_kivy_hover_density_guard(FakeMouseProvider)
    ui_module.install_kivy_hover_density_guard(FakeMouseProvider)

    dpi_window = types.SimpleNamespace(_density=0.0, dpi=144.0)
    fallback_window = types.SimpleNamespace(_density=0.0, dpi=0.0)
    provider = FakeMouseProvider()

    check(
        provider.create_hover(dpi_window, "begin") == 1.5,
        "Kivy hover guard restores a zero density from the window DPI",
    )
    check(
        provider.create_hover(fallback_window, "begin") == 1.0,
        "Kivy hover guard uses a safe density when Windows reports zero DPI",
    )
    check(
        observed_densities == [1.5, 1.0],
        "Kivy hover guard is installed only once",
    )


def test_tracker_gui_loads_kvui_before_kivy_density_guard() -> None:
    events = []
    expected_gui = object()
    original_import = builtins.__import__
    original_guard = ui_module.install_kivy_hover_density_guard
    original_make_gui = tracker_view_module.make_tracker_gui

    def tracking_import(name, *args, **kwargs):
        if name == "kvui":
            events.append("kvui")
        return original_import(name, *args, **kwargs)

    try:
        builtins.__import__ = tracking_import
        ui_module.install_kivy_hover_density_guard = lambda: events.append("guard")
        tracker_view_module.make_tracker_gui = lambda _ctx: expected_gui
        result = client_module._make_tracker_gui_after_patching(object())
    finally:
        builtins.__import__ = original_import
        ui_module.install_kivy_hover_density_guard = original_guard
        tracker_view_module.make_tracker_gui = original_make_gui

    check(
        events[:2] == ["kvui", "guard"],
        "Tracker GUI lets kvui configure Kivy before installing the density guard",
    )
    check(result is expected_gui, "Tracker GUI factory still returns the configured client UI")


def test_patch_startup_guard_stops_failed_patch_before_client_ui() -> None:
    configured = []
    context_module = types.SimpleNamespace(_patch_and_run_game=lambda _path: {})
    client_module.install_patch_startup_guard(
        context_module,
        lambda args: configured.append(tuple(args)),
    )

    stopped = False
    try:
        context_module._patch_and_run_game("failed.apnsmbds")
    except SystemExit:
        stopped = True

    check(stopped, "A cancelled or failed patch stops before the NSMBDS client UI opens")
    check(not configured, "A failed patch does not publish a nonexistent patched-ROM path")


def test_patch_startup_guard_publishes_successful_output_path() -> None:
    configured = []
    metadata = {"game": "New Super Mario Bros. DS"}
    context_module = types.SimpleNamespace(_patch_and_run_game=lambda _path: metadata)
    client_module.install_patch_startup_guard(
        context_module,
        lambda args: configured.append(tuple(args)),
    )

    result = context_module._patch_and_run_game("seed.apnsmbds")
    check(result is metadata, "A successful patch continues into the NSMBDS client")
    check(
        configured == [("seed.apnsmbds",)],
        "The patched-ROM path is published only after patching succeeds",
    )


def test_client_title_contains_apworld_version() -> None:
    check(
        tracker_view_module.NSMBDSTrackerManager.base_title
        == "NSMBDS Client | APWorld v0.4.5-alpha | Archipelago",
        "Client window title displays the full APWorld release version",
    )
    version_module = sys.modules["nsmbds.version"]
    check(
        version_module.format_display_version("1.2.3", "stable") == "1.2.3",
        "Stable display versions omit the release-channel suffix",
    )
    check(
        version_module.format_display_version("1.2.3", "unstable") == "1.2.3-unstable",
        "Non-stable display versions include the release-channel suffix",
    )


def test_readiness_guard() -> None:
    ready = bytearray(0xC0)
    for offset in ram_addresses.LEVEL_DATA_WORLD_HEADER_OFFSETS:
        ready[offset] = ram_addresses.LEVEL_DATA_WORLD_HEADER_VALUE
    check(client_module.NSMBDSClient._is_game_data_ready(bytes(ready)), "Readiness guard accepts valid headers")

    ready[ram_addresses.LEVEL_DATA_WORLD_HEADER_OFFSETS[0]] = 0xD7
    check(
        client_module.NSMBDSClient._is_game_data_ready(bytes(ready)),
        "Readiness guard accepts save-progress bits in a D-prefixed world header",
    )
    ready[ram_addresses.LEVEL_DATA_WORLD_HEADER_OFFSETS[4]] = 0x02
    check(
        client_module.NSMBDSClient._is_game_data_ready(bytes(ready)),
        "Readiness guard accepts the live-observed progressed World 6 header state 0x02",
    )
    client = client_module.NSMBDSClient()
    client._game_data_header_values = tuple(
        ready[offset] for offset in ram_addresses.LEVEL_DATA_WORLD_HEADER_OFFSETS
    )
    guarded_values = tuple(expected[0] for _address, expected, _domain in client._game_data_guards())
    check(
        guarded_values == client._game_data_header_values,
        "RAM writes guard the live save-progress header values",
    )

    # World 8 changes this header as its map advances. This exact state was
    # captured after clearing World 8-Castle: header 0x01 and castle byte 0xD1.
    ready[175] = 0x01
    ready[181] = 0xD1
    check(
        client_module.NSMBDSClient._is_game_data_ready(bytes(ready)),
        "Readiness guard accepts the post-World 8-Castle header",
    )
    check(
        client_module.NSMBDSClient._is_location_completed("World 8-Castle Goal", bytes(ready)),
        "Post-castle RAM still completes the World 8-Castle Goal",
    )
    check(
        client_module.NSMBDSClient._is_location_completed("World 8-Castle Star Coin 1", bytes(ready)),
        "Post-castle RAM still completes the World 8-Castle Star Coin",
    )

    guarded_offsets = {
        address - ram_addresses.ADDR_LEVEL_DATA_BASE
        for address, _expected, _domain in client._game_data_guards()
    }
    check(175 not in guarded_offsets, "Mutable World 8 header is excluded from RAM write guards")

    ready[ram_addresses.LEVEL_DATA_WORLD_HEADER_OFFSETS[0]] = 0x80
    check(not client_module.NSMBDSClient._is_game_data_ready(bytes(ready)), "Readiness guard rejects invalid headers")
    check(
        not client_module.NSMBDSClient._is_game_data_ready(bytes(0xC0)),
        "Readiness guard rejects an uninitialized all-zero level-data block",
    )


async def test_poptracker_world_sync_follows_overworld_and_courses() -> None:
    sent_messages: list[dict] = []
    marker = ram_addresses.AP_STAR_COIN_GATE_HOOK_MARKER
    observed_views = iter((
        [bytes([0]), bytes([1]), marker],
        [bytes([0]), bytes([1]), marker],
        [bytes([0]), bytes([1]), bytes(len(marker))],
        [bytes([6]), bytes([2]), marker],
        [bytes([0xFF]), bytes([1]), marker],
    ))

    async def fake_read(_bizhawk_ctx, read_requests):
        check(
            read_requests == [
                (ram_addresses.ADDR_CURRENT_COURSE_WORLD, 1, ram_addresses.MEMORY_DOMAIN),
                (ram_addresses.ADDR_CURRENT_COURSE_LEVEL, 1, ram_addresses.MEMORY_DOMAIN),
                (
                    ram_addresses.ADDR_AP_STAR_COIN_GATE_HOOK_MARKER,
                    len(marker),
                    ram_addresses.MEMORY_DOMAIN,
                ),
            ],
            "PopTracker navigation reads the Worldmap marker and runtime course identity",
        )
        return next(observed_views)

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    fake_bizhawk.read = fake_read
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = fake_send_msgs

    for _index in range(5):
        await client._sync_poptracker_world(context)

    check(
        sent_messages == [
            {
                "cmd": "Set",
                "key": "nsmbds_current_view_1_1",
                "default": "",
                "want_reply": False,
                "operations": [{"operation": "replace", "value": "1|W1 Overworld"}],
            },
            {
                "cmd": "Set",
                "key": "nsmbds_current_view_1_1",
                "default": "",
                "want_reply": False,
                "operations": [{"operation": "replace", "value": "1|W1-1"}],
            },
            {
                "cmd": "Set",
                "key": "nsmbds_current_view_1_1",
                "default": "",
                "want_reply": False,
                "operations": [{"operation": "replace", "value": "7|W7 Overworld"}],
            },
        ],
        "PopTracker navigation publishes each distinct Worldmap or course view once",
    )


async def test_individual_powerup_license_sync() -> None:
    writes = []

    async def guarded_write(_ctx, payload, guards):
        writes.append((payload, guards))
        return True

    fake_bizhawk.guarded_write = guarded_write
    fire_license_id = client_module.ITEM_TABLE[powerup_licenses.FIRE_FLOWER_LICENSE][0]
    context = FakeContext()
    context.slot_data.update({
        "license_mini_mushroom": False,
        "license_blue_shell": False,
        "license_mega_mushroom": False,
        "license_mushroom": False,
        "license_fire_flower": True,
        "license_touchscreen_pocket": False,
    })
    client = client_module.NSMBDSClient()

    await client._sync_powerup_licenses(context)
    check(
        writes[-1][0][:2] == [
            (ram_addresses.ADDR_AP_POWERUP_LICENSE_MODE, [3], ram_addresses.MEMORY_DOMAIN),
            (ram_addresses.ADDR_AP_POWERUP_LICENSE_MASK, [0x1F], ram_addresses.MEMORY_DOMAIN),
        ],
        "Individual License toggles bypass disabled native-hook tiers",
    )

    context.items_received = [types.SimpleNamespace(item=fire_license_id)]
    await client._sync_powerup_licenses(context)
    check(
        writes[-1][0][1][1] == [0x3F],
        "Receiving the only enabled License completes its native-hook mask",
    )


def test_spoiler_free_tracker() -> None:
    disconnected_snapshot = tracker_module.build_tracker_snapshot(FakeContext())
    check(
        not disconnected_snapshot.seed_loaded,
        "Tracker suppresses seed data until a server connection and slot data are available",
    )

    context = FakeContext()
    world_1_goal = locations.LOCATION_TABLE["World 1-1 Goal"]
    world_1_coin = locations.LOCATION_TABLE["World 1-1 Star Coin 1"]
    context.checked_locations = {world_1_goal}
    context.missing_locations = {world_1_coin}
    context.items_received = [
        types.SimpleNamespace(item=tracker_module.ITEM_TABLE["Desert Pass"][0]),
        *[
            types.SimpleNamespace(item=tracker_module.ITEM_TABLE["Star Coin"][0])
            for _ in range(12)
        ],
    ]
    context.server = types.SimpleNamespace(socket=types.SimpleNamespace(closed=False))
    context.bizhawk_ctx = types.SimpleNamespace(
        connection_status=types.SimpleNamespace(name="CONNECTED")
    )
    context.client_handler = types.SimpleNamespace(
        server_game="New Super Mario Bros. DS",
        _pending_trap_shields=2,
        _pending_life_insurance=1,
        _star_coin_lifetime=12,
        _star_coin_spent=5,
        _star_coin_available=7,
        _deferred_item_ids=[
            tracker_module.ITEM_TABLE["Mushroom"][0],
            tracker_module.ITEM_TABLE["Fire Flower"][0],
            tracker_module.ITEM_TABLE["Mushroom"][0],
        ],
    )
    context.slot_data.update({
        "tower_castle_keys": False,
        "license_mini_mushroom": 0,
        "license_blue_shell": 0,
        "license_mega_mushroom": 0,
        "license_mushroom": 0,
        "license_fire_flower": 0,
        "license_touchscreen_pocket": 0,
        "star_coin_gate_mode": 0,
    })

    snapshot = tracker_module.build_tracker_snapshot(context)
    markup = tracker_module.render_tracker_markup(snapshot)
    check(
        snapshot.seed_loaded,
        "Tracker enables seed data after server connection and slot data are available",
    )
    check(
        snapshot.total_progress == tracker_module.ProgressCount(1, 2),
        "Tracker counts only active checked and missing NSMBDS locations",
    )
    check(
        "Desert Pass: Received" in markup and "Isle Pass: Missing" in markup,
        "Tracker shows only already-received progression inventory state",
    )
    check(
        "No item placements are shown" in markup,
        "Tracker explicitly keeps item-placement information in the Hints tab",
    )
    check(
        "NSMBDS Overview" in markup,
        "Embedded client status is labelled as an Overview instead of a map tracker",
    )
    check(
        snapshot.trap_shields == 2
        and snapshot.life_insurance == 1
        and "Trap Shields: 2" in markup,
        "Tracker exposes the currently available Shield and Life Insurance charges",
    )
    check(
        sum(entry.received for entry in snapshot.pending_powerups) == 3
        and "Mushroom: 2" in markup
        and "Fire Flower: 1" in markup,
        "Overview lists the count and names of queued reserve Power-Ups",
    )
    check(
        snapshot.star_coin_lifetime == 12
        and snapshot.star_coin_spent == 5
        and snapshot.star_coin_available == 7
        and "Star Coins: 7 available | 12 received total | 5 spent" in markup,
        "Overview keeps available, spent, and lifetime Star Coin totals separate",
    )


def test_tracker_gui_factory_contract() -> None:
    gui_class = tracker_view_module.make_tracker_gui(None)
    check(
        gui_class is tracker_view_module.NSMBDSTrackerManager and isinstance(gui_class, type),
        "Tracker make_gui hook returns the GUI class expected by CommonContext.run_gui",
    )


def test_launcher_patch_path_and_rom_validation() -> None:
    state = launcher_module.configure_launch_from_args(("--connect", "example:38281", "seed.apnsmbds"))
    check(
        state.patch_file.name == "seed.apnsmbds" and state.rom_file.name == "seed.nds",
        "Launcher derives the standard Archipelago patched ROM path from .apnsmbds",
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        rom_path = Path(temp_dir) / "seed.nds"
        rom_data = bytearray(0x20)
        rom_data[0x0C:0x10] = b"A2DE"
        rom_path.write_bytes(rom_data)
        with rom_path.open("r+b") as rom_file:
            rom_file.seek(launcher_module.PATCH_MARKER_OFFSET)
            rom_file.write(launcher_module.PATCH_MARKER)
        launcher_module.validate_seed_rom(rom_path)
        with rom_path.open("r+b") as rom_file:
            rom_file.seek(0x0C)
            rom_file.write(b"NOPE")
        try:
            launcher_module.validate_seed_rom(rom_path)
        except ValueError:
            rejected = True
        else:
            rejected = False
    check(rejected, "Launcher rejects a selected ROM with the wrong game code")


def test_launcher_starts_bizhawk_with_bootstrap() -> None:
    class FakeProcess:
        def poll(self):
            return None

    captured = {}
    original_find = launcher_module.find_emuhawk
    original_rom = launcher_module.configured_rom_path
    original_runtime = launcher_module.materialize_lua_runtime
    original_remember = launcher_module._remember_rom
    original_popen = launcher_module.subprocess.Popen
    original_utils = sys.modules.get("Utils")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            emuhawk = root / "BizHawk" / "EmuHawk.exe"
            emuhawk.parent.mkdir()
            emuhawk.write_bytes(b"")
            bootstrap = root / "lua" / "nsmbds_bizhawk_bootstrap.lua"
            bootstrap.parent.mkdir()
            bootstrap.write_text("-- test", encoding="utf-8")
            rom = root / "seed.nds"
            rom.write_bytes(b"\0" * 0x20)
            with rom.open("r+b") as rom_file:
                rom_file.seek(0x0C)
                rom_file.write(b"A2DE")
                rom_file.seek(launcher_module.PATCH_MARKER_OFFSET)
                rom_file.write(launcher_module.PATCH_MARKER)

            launcher_module.find_emuhawk = lambda: emuhawk
            launcher_module.configured_rom_path = lambda: rom
            launcher_module.materialize_lua_runtime = lambda: bootstrap
            launcher_module._remember_rom = lambda _path: None
            launcher_module.launch_state.process = None
            fake_utils = types.ModuleType("Utils")
            fake_utils.local_path = lambda *parts: str(root / "Archipelago" / Path(*parts))
            sys.modules["Utils"] = fake_utils

            def fake_popen(args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs
                return FakeProcess()

            launcher_module.subprocess.Popen = fake_popen
            launcher_module.launch_game()
    finally:
        launcher_module.find_emuhawk = original_find
        launcher_module.configured_rom_path = original_rom
        launcher_module.materialize_lua_runtime = original_runtime
        launcher_module._remember_rom = original_remember
        launcher_module.subprocess.Popen = original_popen
        launcher_module.launch_state.process = None
        if original_utils is None:
            sys.modules.pop("Utils", None)
        else:
            sys.modules["Utils"] = original_utils

    check(
        captured["args"] == [str(emuhawk), f"--lua={bootstrap}", str(rom)]
        and captured["kwargs"]["cwd"] == str(emuhawk.parent)
        and captured["kwargs"]["env"]["NSMBDS_AP_LUA_DIR"].endswith(os.path.join("data", "lua")),
        "Launcher starts BizHawk with the patched ROM, bundled bootstrap, and AP Lua path",
    )


def test_launcher_uses_core_world_settings() -> None:
    class FakeSettings:
        def __init__(self):
            self.nsmbds_options = types.SimpleNamespace(
                last_patched_rom="",
                auto_launch_game=False,
                emulator_feed_enabled=True,
                emulator_feed_width=500,
                emulator_feed_position="bottom_left",
                emulator_feed_fade_seconds=0,
            )
            self.save_count = 0

        def save(self):
            self.save_count += 1

    fake_settings = FakeSettings()
    original_settings = launcher_module._settings
    try:
        launcher_module._settings = lambda: fake_settings
        check(not launcher_module.auto_launch_enabled(), "Launcher reads Core world settings")
        launcher_module.set_auto_launch(True)
        launcher_module._remember_rom(Path("seed.nds").resolve())
        launcher_module.set_emulator_feed_enabled(False)
        launcher_module.set_emulator_feed_width(650)
        launcher_module.set_emulator_feed_position("top_right")
        launcher_module.set_emulator_feed_fade_seconds(20)
        persisted_feed_config = launcher_module.emulator_feed_config()
    finally:
        launcher_module._settings = original_settings
    check(
        fake_settings.nsmbds_options.auto_launch_game is True
        and fake_settings.nsmbds_options.last_patched_rom.endswith("seed.nds")
        and launcher_module.EmulatorFeedConfig(False, 650, "top_right", 20)
        == persisted_feed_config
        and fake_settings.save_count == 6,
        "Launcher persists and validates Core world settings",
    )


def test_launcher_accepts_empty_optional_rom_setting() -> None:
    class EmptyRomOptions:
        @property
        def last_patched_rom(self):
            raise FileNotFoundError("an empty OptionalUserFilePath resolved to the working directory")

    fake_settings = types.SimpleNamespace(nsmbds_options=EmptyRomOptions())
    original_settings = launcher_module._settings
    original_rom_file = launcher_module.launch_state.rom_file
    try:
        launcher_module._settings = lambda: fake_settings
        launcher_module.launch_state.rom_file = None
        configured_rom = launcher_module.configured_rom_path()
    finally:
        launcher_module._settings = original_settings
        launcher_module.launch_state.rom_file = original_rom_file
    check(
        configured_rom is None,
        "Launcher treats an empty optional seed-ROM setting as unconfigured",
    )


def test_secret_exit_detection() -> None:
    game_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    for offset, bit_mask in locations.SECRET_EXIT_RAM_REQUIREMENTS["World 1-2 Secret Exit"]:
        game_data[offset] = bit_mask
    check(
        client_module.NSMBDSClient._is_location_completed("World 1-2 Secret Exit", bytes(game_data)),
        "World 1-2 Secret Exit requires all verified persistent flags",
    )
    game_data[0xD2] = 0
    check(
        not client_module.NSMBDSClient._is_location_completed("World 1-2 Secret Exit", bytes(game_data)),
        "World 1-2 Secret Exit rejects an incomplete persistent flag set",
    )

    game_data_w23 = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    for offset, bit_mask in locations.SECRET_EXIT_RAM_REQUIREMENTS["World 2-3 Secret Exit"]:
        game_data_w23[offset] = bit_mask
    check(
        client_module.NSMBDSClient._is_location_completed("World 2-3 Secret Exit", bytes(game_data_w23)),
        "World 2-3 Secret Exit requires verified persistent flag (0x0F1, 0xC0)",
    )
    game_data[0xD4] = 0xC0
    check(
        client_module.NSMBDSClient._is_location_completed("World 1-Tower Secret Exit", bytes(game_data)),
        "World 1-Tower Secret Exit accepts its alpha persistent flag candidate",
    )
    game_data[0xF2] = 0xC0
    game_data[0xF5] = 0xC0
    game_data[0xF6] = 0xC0
    check(
        client_module.NSMBDSClient._is_location_completed("World 2-A Secret Exit", bytes(game_data)),
        "World 2-A Secret Exit accepts its alpha persistent path flag",
    )
    check(
        client_module.NSMBDSClient._is_location_completed("World 2-4 Secret Exit", bytes(game_data)),
        "World 2-4 Secret Exit requires both alpha persistent path flags",
    )

    # Test World 2-Castle Secret Exit validation using stage complete (35, 0x10) + Mini Mario flag (0x2F4, 0x01)
    game_data_w2c = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w2c[35] = 0xD0     # W2-Castle completed
    game_data_w2c[0x2F4] = 0x01  # Mini Mario Castle flag bit 0x01 set by Lua
    check(
        client_module.NSMBDSClient._is_location_completed("World 2-Castle Secret Exit", bytes(game_data_w2c)),
        "World 2-Castle Secret Exit detects Mini Mario clear via (35, 0x10) and (0x2F4, 0x01)",
    )
    game_data_w2c_norm = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w2c_norm[35] = 0xD0  # W2-Castle Normal exit clear (0x2F4 is 0)
    check(
        not client_module.NSMBDSClient._is_location_completed("World 2-Castle Secret Exit", bytes(game_data_w2c_norm)),
        "World 2-Castle Secret Exit rejects normal exit clear without Mini Mario flag",
    )
    game_data_w41_only = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w41_only[0x1C4] = 0x03  # W4-1 map active, but W2-Castle stage complete byte 35 is 0 and 0x2F4 is 0
    check(
        not client_module.NSMBDSClient._is_location_completed("World 2-Castle Secret Exit", bytes(game_data_w41_only)),
        "World 4-1 clear does not trigger World 2-Castle Secret Exit when W2-Castle is incomplete",
    )

    # Test World 5-Castle Secret Exit validation using stage complete (111, 0x10) + Mini Mario flag (0x2F4, 0x02)
    game_data_w5c = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w5c[111] = 0xD0    # W5-Castle completed
    game_data_w5c[0x2F4] = 0x02  # Mini Mario Castle flag bit 0x02 set by Lua
    check(
        client_module.NSMBDSClient._is_location_completed("World 5-Castle Secret Exit", bytes(game_data_w5c)),
        "World 5-Castle Secret Exit detects Mini Mario clear via (111, 0x10) and (0x2F4, 0x02)",
    )
    game_data_w5c_norm = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w5c_norm[111] = 0xD0  # W5-Castle Normal exit clear (0x2F4 is 0)
    check(
        not client_module.NSMBDSClient._is_location_completed("World 5-Castle Secret Exit", bytes(game_data_w5c_norm)),
        "World 5-Castle Secret Exit rejects normal exit clear without Mini Mario flag",
    )
    game_data_w71_only = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data_w71_only[0x1D0] = 0x03  # W7-1 map active, but W5-Castle stage complete byte 111 is 0 and 0x2F4 is 0
    check(
        not client_module.NSMBDSClient._is_location_completed("World 5-Castle Secret Exit", bytes(game_data_w71_only)),
        "World 7-1 clear does not trigger World 5-Castle Secret Exit when W5-Castle is incomplete",
    )


def test_toad_house_detection() -> None:
    game_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data[8] = 0xF0
    check(
        client_module.NSMBDSClient._is_location_completed("World 1 Green Toad House 1 Goal", bytes(game_data)),
        "Toad House Green 1 detects its completed reward flag",
    )
    game_data[8] = 0x80
    check(
        not client_module.NSMBDSClient._is_location_completed("World 1 Green Toad House 1 Goal", bytes(game_data)),
        "Toad House Green 1 rejects an active but uncollected house",
    )


def test_bowser_goal_detection() -> None:
    game_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data[187] = 0x97
    check(
        client_module.NSMBDSClient._is_location_completed("World 8-Bowser's Castle Goal", bytes(game_data)),
        "Bowser victory flag at offset 187 completes World 8 Bowser's Castle Goal",
    )
    check(
        client_module.NSMBDSClient._is_location_completed(
            "World 8-Bowser's Castle Bowser & Bowser Jr. Defeated",
            bytes(game_data),
        ),
        "Final victory also completes the separate Bowser boss check",
    )

    world_two_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    world_two_data[35] = 0xD0
    world_two_data[0x2F4] = 0x01
    check(
        client_module.NSMBDSClient._is_location_completed(
            "World 2-Castle Mummipokey Defeated", bytes(world_two_data)
        ),
        "Mummipokey boss check accepts the Mini-Mario castle exit",
    )


async def test_boss_location_submission() -> None:
    client = client_module.NSMBDSClient()
    context = FakeContext()
    sent_messages = []

    async def send_msgs(messages):
        sent_messages.extend(messages)

    context.send_msgs = send_msgs
    game_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    game_data[35] = 0xD0
    await client._detect_and_send_locations(context, bytes(game_data))

    submitted = set(sent_messages[0]["locations"])
    check(
        {
            locations.LOCATION_TABLE["World 2-Castle Goal"],
            locations.LOCATION_TABLE["World 2-Castle Mummipokey Defeated"],
        } <= submitted,
        "A castle clear submits both its Goal and separate randomized boss check",
    )


def test_death_link_state() -> None:
    check(
        client_module.NSMBDSClient._timer_is_counting(400 * 4096, 399 * 4096),
        "Death Link recognizes a decreasing verified level timer",
    )
    check(
        not client_module.NSMBDSClient._timer_is_counting(399 * 4096, 400 * 4096),
        "Death Link rejects an increasing timer value",
    )
    client = client_module.NSMBDSClient()
    context = FakeContext(death_link=True)
    client.on_package(context, "Bounced", {"tags": ["DeathLink"]})
    check(client._pending_death_link, "Incoming Death Link is queued")


def test_timer_drain_math() -> None:
    drain = client_module.TIMER_DRAIN_UNITS
    check(
        client_module.NSMBDSClient._drained_timer_value(400 * 4096) == 350 * 4096,
        "Timer Drain subtracts 50 visible seconds",
    )
    check(
        client_module.NSMBDSClient._drained_timer_value(drain - 1) == 0,
        "Timer Drain clamps low timer values to zero",
    )


def test_client_feature_layout() -> None:
    check(
        client_module.NSMBDSClient.__module__ == "nsmbds.client",
        "The public client facade remains import-compatible after feature extraction",
    )


async def test_coin_thief_write() -> None:
    writes: list[tuple] = []

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    applied = await client._apply_coin_thief(FakeContext())
    expected_request = (ram_addresses.ADDR_COINS, [0], ram_addresses.MEMORY_DOMAIN)
    check(applied and writes[0][0] == [expected_request]
          and client._pending_coin_thief_notices == 1,
          "Coin Thief guarded-writes zero to the verified coin address")
    check(
        client_module.NSMBDSClient._apply_coin_thief.__module__ == "nsmbds.client.features.traps",
        "Coin Thief is isolated in the trap feature module",
    )

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([42])]

    fake_bizhawk.guarded_read = fake_guarded_read
    writes.clear()
    applied = await client._apply_item(
        FakeContext(),
        client_module.ITEM_TABLE["Coin Tax"][0],
    )
    expected_tax = (ram_addresses.ADDR_COINS, [32], ram_addresses.MEMORY_DOMAIN)
    check(
        applied and writes[0][0] == [expected_tax]
        and client._pending_coin_tax_notices == 1,
        "Coin Tax removes exactly ten coins and queues its Trap notification",
    )

    fake_bizhawk.guarded_read = fake_guarded_read
    writes.clear()
    applied = await client._apply_item(
        FakeContext(),
        client_module.ITEM_TABLE["Power-Up Pickpocket Trap"][0],
    )
    expected_backup_write = (
        ram_addresses.ADDR_INVENTORY_ITEM,
        [0],
        ram_addresses.MEMORY_DOMAIN,
    )
    check(
        applied
        and writes[0][0] == [expected_backup_write]
        and (
            ram_addresses.ADDR_INVENTORY_ITEM,
            [42],
            ram_addresses.MEMORY_DOMAIN,
        ) in writes[0][1]
        and client._pending_powerup_pickpocket_notices == 1,
        "Power-Up Pickpocket Trap exact-guards and empties the reserve slot",
    )

    async def empty_reserve_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([0])]

    fake_bizhawk.guarded_read = empty_reserve_guarded_read
    writes.clear()
    applied = await client._apply_powerup_pickpocket(FakeContext())
    check(
        applied
        and not writes
        and client._pending_powerup_pickpocket_notices == 2,
        "Power-Up Pickpocket Trap is consumed safely when the reserve slot is already empty",
    )


async def test_nothing_item() -> None:
    client = client_module.NSMBDSClient()
    applied = await client._apply_item(
        FakeContext(),
        client_module.ITEM_TABLE["Nothing"][0],
    )
    check(applied, "Nothing advances the received-item cursor without changing game RAM")


async def test_deferred_powerup_does_not_block_later_items() -> None:
    writes: list[tuple] = []

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([0])]

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.slot_data["license_mega_mushroom"] = 1
    context.slot_data["license_touchscreen_pocket"] = 0
    context.items_received = [
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Mega Mushroom"][0]),
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Super Speed"][0]),
    ]

    await client._apply_pending_items(context)
    check(
        client._items_received_index == 2
        and client._deferred_item_ids == [client_module.ITEM_TABLE["Mega Mushroom"][0]]
        and client._pending_hyper_speed_traps == 1,
        "A license-blocked Power-Up no longer blocks later filler and traps",
    )

    context.items_received.append(
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Mega Mushroom Permit"][0])
    )
    await client._apply_pending_items(context)
    check(
        client._items_received_index == 3
        and not client._deferred_item_ids
        and bool(writes),
        "A deferred Power-Up is delivered after its License arrives",
    )


async def test_failed_item_write_does_not_block_later_traps() -> None:
    write_results = iter((False, True))

    async def fake_guarded_write(_bizhawk_ctx, _write_requests, _guards):
        return next(write_results)

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([0])]

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.slot_data["license_mushroom"] = 0
    context.slot_data["license_touchscreen_pocket"] = 0
    mushroom_id = client_module.ITEM_TABLE["Mushroom"][0]
    context.items_received = [
        types.SimpleNamespace(item=mushroom_id),
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Super Speed"][0]),
    ]

    await client._apply_pending_items(context)
    check(
        client._items_received_index == 2
        and client._deferred_item_ids == [mushroom_id]
        and client._pending_hyper_speed_traps == 1,
        "A failed normal-item RAM write does not block a later trap",
    )

    await client._apply_pending_items(context)
    check(
        not client._deferred_item_ids,
        "A normal item whose RAM write failed is retried later",
    )


async def test_deferred_item_retries_are_rate_limited() -> None:
    write_count = 0

    async def fake_guarded_write(_bizhawk_ctx, _write_requests, _guards):
        nonlocal write_count
        write_count += 1
        return False

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([0])]

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.slot_data["license_mushroom"] = 0
    context.slot_data["license_touchscreen_pocket"] = 0
    mushroom_id = client_module.ITEM_TABLE["Mushroom"][0]
    client._deferred_item_ids = [mushroom_id, mushroom_id, mushroom_id]

    await client._apply_pending_items(context)
    check(
        write_count == 1 and len(client._deferred_item_ids) == 3,
        "Only one deferred RAM item is retried per watcher poll",
    )


async def test_powerup_waits_for_empty_reserve_slot() -> None:
    writes: list[tuple] = []
    inventory_values = iter((bytes([2]), bytes([0])))

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [next(inventory_values)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.slot_data["license_mushroom"] = 0
    context.slot_data["license_touchscreen_pocket"] = 0
    mushroom_id = client_module.ITEM_TABLE["Mushroom"][0]
    context.items_received = [types.SimpleNamespace(item=mushroom_id)]

    await client._apply_pending_items(context)
    check(
        client._items_received_index == 1
        and client._deferred_item_ids == [mushroom_id]
        and not writes,
        "A received Power-Up waits instead of replacing the occupied reserve slot",
    )

    await client._apply_pending_items(context)
    expected_write = (
        ram_addresses.ADDR_INVENTORY_ITEM,
        [sys.modules["nsmbds.items"].INVENTORY_RAM_VALUES["Mushroom"]],
        ram_addresses.MEMORY_DOMAIN,
    )
    expected_empty_guard = (
        ram_addresses.ADDR_INVENTORY_ITEM,
        [0],
        ram_addresses.MEMORY_DOMAIN,
    )
    check(
        not client._deferred_item_ids
        and writes[0][0] == [expected_write]
        and expected_empty_guard in writes[0][1],
        "The queued Power-Up is delivered atomically after the reserve slot becomes empty",
    )


async def test_hundred_item_release_burst_is_buffered() -> None:
    client = client_module.NSMBDSClient()
    context = FakeContext()
    nothing_id = client_module.ITEM_TABLE["Nothing"][0]
    trap_id = client_module.ITEM_TABLE["Super Speed"][0]
    context.items_received = [
        types.SimpleNamespace(item=trap_id if index % 10 == 0 else nothing_id)
        for index in range(100)
    ]

    for _ in range(13):
        await client._apply_pending_items(context)

    check(
        client._items_received_index == 100
        and client._pending_hyper_speed_traps == 10
        and not client._deferred_item_ids,
        "A 100-item release burst is consumed in bounded batches without losing queued Traps",
    )


async def test_item_receipt_notifications_and_realtime_core_feed() -> None:
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.slot_data["license_mushroom"] = 0
    context.slot_data["license_touchscreen_pocket"] = 0
    desert_pass_id = client_module.ITEM_TABLE["Desert Pass"][0]
    mushroom_id = client_module.ITEM_TABLE["Mushroom"][0]
    star_coin_id = client_module.ITEM_TABLE["Star Coin"][0]
    one_up_id = client_module.ITEM_TABLE["1-Up Mushroom"][0]
    context.items_received = [
        types.SimpleNamespace(item=desert_pass_id),
        types.SimpleNamespace(item=mushroom_id),
        types.SimpleNamespace(item=star_coin_id),
        types.SimpleNamespace(item=one_up_id),
    ]

    async def occupied_inventory(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([2])]

    fake_bizhawk.guarded_read = occupied_inventory
    await client._apply_pending_items(context)
    check(
        client._pending_ap_notifications == [
            (
                ram_addresses.AP_NOTIFICATION_ITEM_RECEIVED,
                desert_pass_id - sys.modules["nsmbds.items"].BASE_ID,
            ),
            (
                ram_addresses.AP_NOTIFICATION_ITEM_RECEIVED,
                mushroom_id - sys.modules["nsmbds.items"].BASE_ID,
            ),
            (
                ram_addresses.AP_NOTIFICATION_ITEM_RECEIVED,
                star_coin_id - sys.modules["nsmbds.items"].BASE_ID,
            ),
            (
                ram_addresses.AP_NOTIFICATION_ITEM_RECEIVED,
                one_up_id - sys.modules["nsmbds.items"].BASE_ID,
            ),
        ],
        "Progression, useful, and positive filler items queue visible receipt notifications once",
    )
    check(
        not client._pending_emulator_feed,
        "Item application stays independent from the separate feed history cursor",
    )

    requests = []

    class FeedSettings:
        nsmbds_options = types.SimpleNamespace(
            emulator_feed_enabled=True,
            emulator_feed_width=500,
            emulator_feed_position="bottom_left",
            emulator_feed_fade_seconds=0,
        )

    original_settings = launcher_module._settings
    launcher_module._settings = lambda: FeedSettings()

    async def fake_send_requests(_bizhawk_ctx, payload):
        requests.extend(payload)
        return [
            {
                "type": (
                    "NSMBDS_FEED_CONFIG_RESPONSE"
                    if request["type"] == "NSMBDS_FEED_CONFIG"
                    else "NSMBDS_FEED_MESSAGE_RESPONSE"
                ),
                "value": True,
            }
            for request in payload
        ]

    fake_bizhawk.send_requests = fake_send_requests
    context.slot = 1
    context.player_names = {1: "Lemix", 2: "Alice"}
    context.slot_concerns_self = lambda slot: slot == 1
    context.item_names = types.SimpleNamespace(
        lookup_in_slot=lambda item_id, _slot: {
            desert_pass_id: "Desert Pass",
            mushroom_id: "Mushroom",
            one_up_id: "1-Up Mushroom",
        }[item_id]
    )
    location_id = locations.LOCATION_TABLE["World 1-1 Goal"]
    context.location_names = types.SimpleNamespace(
        lookup_in_slot=lambda _location_id, _slot: "World 1-1 Goal"
    )
    received_for_feed = [
        types.SimpleNamespace(
            player=1, item=desert_pass_id, location=location_id, flags=0b001,
        ),
        types.SimpleNamespace(
            player=2, item=one_up_id, location=location_id, flags=0b100,
        ),
    ]
    context.items_received = received_for_feed
    await client._sync_emulator_feed(context, server_connected=True)
    client.on_package(context, "PrintJSON", {
        "type": "ItemSend",
        "receiving": 2,
        "item": types.SimpleNamespace(
            player=1, item=mushroom_id, location=location_id, flags=0b010,
        ),
    })
    await client._emulator_feed_flush_task
    check(
        len(requests) == 5
        and requests[0] == {
            "type": "NSMBDS_FEED_CONFIG",
            "enabled": True,
            "width": 500,
            "position": "bottom_left",
            "fade_seconds": 0,
        }
        and requests[1]["segments"] == [
            {
                "text": "NSMBDS Client connected to the Archipelago server.",
                "color": "success",
            },
        ]
        and requests[2]["segments"] == [
            {"text": "Lemix", "color": "player_self"},
            {"text": " found ", "color": "text"},
            {"text": "Desert Pass", "color": "progression"},
            {"text": " (", "color": "text"},
            {"text": "World 1-1 Goal", "color": "location"},
            {"text": ")", "color": "text"},
        ]
        and any(
            segment == {"text": " sent ", "color": "text"}
            for segment in requests[4]["segments"]
        )
        and requests[4]["segments"][2]["color"] == "useful"
        and requests[3]["segments"][0] == {"text": "Alice", "color": "player"}
        and requests[3]["segments"][2]["color"] == "trap"
        and not client._pending_emulator_feed,
        "Both connection layers and Core ItemSend bursts appear as colored messages",
    )
    request_count = len(requests)
    await client._sync_emulator_feed(context, server_connected=True)
    check(
        len(requests) == request_count,
        "Connection success messages are not repeated while both links stay live",
    )
    context.items_received = []
    await client._sync_emulator_feed(context, server_connected=True)
    context.items_received = received_for_feed
    await client._sync_emulator_feed(context, server_connected=True)
    check(
        len(requests) == request_count,
        "A transient empty item list during reconnect does not replay feed history",
    )
    await client._sync_emulator_feed(context, server_connected=False)
    await client._sync_emulator_feed(context, server_connected=True)
    check(
        len(requests) == request_count + 2
        and requests[-2]["segments"] == [{
            "text": "NSMBDS Client disconnected from the Archipelago server.",
            "color": "warning",
        }]
        and requests[-1]["segments"] == [{
            "text": "NSMBDS Client connected to the Archipelago server.",
            "color": "success",
        }],
        "Archipelago server disconnects and genuine reconnects are each announced once",
    )
    im_stuck_id = client_module.ITEM_TABLE["I'm Stuck"][0]
    cant_stop_id = client_module.ITEM_TABLE["Can't Stop"][0]
    check(
        client._item_color(0b010, im_stuck_id) == "trap"
        and client._item_color(0b010, cant_stop_id) == "trap",
        "Local I'm Stuck and Can't Stop items stay trap-colored despite stale useful flags",
    )
    launcher_module._settings = original_settings


def test_goals() -> None:
    client = client_module.NSMBDSClient()
    bowser_id = client_module.FINAL_BOSS_LOCATION_ID
    star_coin_item_id = client_module.ITEM_TABLE["Star Coin"][0]

    def coin_context(count: int, goal: int, required: int = 80) -> FakeContext:
        context = FakeContext(goal=goal, required_star_coins=required)
        context.items_received = [
            types.SimpleNamespace(item=star_coin_item_id) for _ in range(count)
        ]
        return context

    client._observed_locations = {bowser_id}
    check(client._check_goal(FakeContext(goal=0)), "Bowser goal completes at World 8 Castle")

    client._observed_locations = set(client_module.STAR_COIN_LOCATION_IDS)
    check(
        not client._check_goal(coin_context(79, 1)),
        "Star Coin goal ignores local checks and rejects 79 received items",
    )
    check(
        client._check_goal(coin_context(80, 1)),
        "Star Coin goal accepts 80 received Star Coin items",
    )

    client._observed_locations = set(client_module.BOSS_LOCATION_IDS)
    check(client._check_goal(FakeContext(goal=2)), "World Tour requires all nine Castle bosses")

    client._observed_locations.remove(bowser_id)
    check(
        not client._check_goal(FakeContext(goal=2)),
        "World Tour does not finish before the final Bowser boss check",
    )

    client._observed_locations = set(client_module.BOSS_LOCATION_IDS)
    check(client._check_goal(coin_context(80, 3)), "Completionist requires all bosses and received Star Coin items")

    check(
        not client._check_goal(coin_context(79, 3)),
        "Completionist does not finish with all bosses but too few Star Coins",
    )
    client._observed_locations = set()
    check(
        not client._check_goal(coin_context(80, 3)),
        "Completionist does not finish with enough Star Coins but without all bosses",
    )

    check(
        client._final_castle_gate_should_open(coin_context(240, 1, 240)) is None
        and client._final_castle_gate_should_open(coin_context(240, 3, 240)) is None,
        "Star Coin goals leave the final path under normal map control before World 8-Tower 2",
    )

    tower_two_id = locations.LOCATION_TABLE["World 8-Tower 2 Goal"]
    client._observed_locations = {tower_two_id}
    check(
        client._final_castle_gate_should_open(coin_context(0, 1, 240))
        and client._final_castle_gate_should_open(coin_context(0, 3, 240)),
        "World 8-Tower 2 opens Bowser's Castle without a Star Coin goal gate",
    )
    check(
        client._check_goal(coin_context(240, 1, 240)),
        "Star Coin Hunt still completes at 240 received items independently of the final path",
    )

    client._observed_locations = {tower_two_id}
    check(
        client._final_castle_gate_should_open(FakeContext(goal=2)),
        "World Tour opens final Bowser after Tower 2 regardless of other Castle bosses",
    )
    client._observed_locations = set()
    check(
        client._final_castle_gate_should_open(FakeContext(goal=0)) is None,
        "Defeat Bowser leaves the final path under vanilla map control",
    )


async def test_goal_status_submission() -> None:
    client = client_module.NSMBDSClient()
    context = FakeContext(goal=0)
    bowser_id = client_module.FINAL_BOSS_LOCATION_ID
    client._observed_locations = {bowser_id}
    sent_messages = []

    async def send_msgs(messages):
        sent_messages.append(messages)

    context.send_msgs = send_msgs
    await client._send_goal_if_complete(context)
    check(
        sent_messages == [[{"cmd": "StatusUpdate", "status": 30}]],
        "Completed goal sends CLIENT_GOAL status to Archipelago",
    )
    check(context.finished_game and client._goal_sent, "Successful goal submission is remembered")
    check(
        client._pending_ap_notifications
        == [(ram_addresses.AP_NOTIFICATION_GOAL_COMPLETE, 0)],
        "Successful goal submission queues the in-game victory notification",
    )

    await client._send_goal_if_complete(context)
    check(len(sent_messages) == 1, "Completed goal status is sent only once")

    retry_client = client_module.NSMBDSClient()
    retry_context = FakeContext(goal=0)
    retry_client._observed_locations = {bowser_id}
    attempts = 0

    async def fail_once(messages):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated connection failure")
        sent_messages.append(messages)

    retry_context.send_msgs = fail_once
    previous_log_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        await retry_client._send_goal_if_complete(retry_context)
    finally:
        logging.disable(previous_log_disable)
    check(
        not retry_context.finished_game
        and not retry_client._goal_sent
        and not retry_client._pending_ap_notifications,
        "Failed goal submission remains eligible for retry",
    )
    await retry_client._send_goal_if_complete(retry_context)
    check(
        retry_context.finished_game
        and retry_client._goal_sent
        and attempts == 2
        and retry_client._pending_ap_notifications
        == [(ram_addresses.AP_NOTIFICATION_GOAL_COMPLETE, 0)],
        "Goal submission succeeds on the next watcher retry",
    )


def test_session_reconnect() -> None:
    packet_client = client_module.NSMBDSClient()
    packet_context = FakeContext()
    packet_location = next(iter(locations.LOCATION_TABLE.values()))
    packet_context.missing_locations = set()
    packet_client.on_package(
        packet_context,
        "Connected",
        {"checked_locations": [], "missing_locations": [packet_location]},
    )
    check(
        packet_location in packet_client._active_locations,
        "Connected packet location state wins when the context has not populated missing locations yet",
    )

    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.server_seed_name = None
    client.on_package(context, "Connected", {"checked_locations": []})
    client._items_received_index = 4
    context.server_seed_name = "seed-a"
    client.on_package(context, "Connected", {"checked_locations": []})
    check(client._items_received_index == 4, "Session identity update retains item cursor")
    client.on_package(context, "Connected", {"checked_locations": []})
    check(client._items_received_index == 4, "Same-session reconnect retains item cursor")
    client._gate_purchase_mask = 0x10
    client._gate_purchase_spent_floor = 5
    client.on_package(context, "Connected", {"checked_locations": []})
    check(
        client._gate_purchase_mask == 0
        and client._gate_purchase_spent_floor == 0
        and client._gate_storage_sync_pending,
        "Same-seed reconnect discards local gate purchases until server DataStorage confirms them",
    )

    context.server_seed_name = "seed-b"
    client.on_package(context, "Connected", {"checked_locations": []})
    check(client._items_received_index == 0, "Different session resets item cursor")

    client._items_received_index = 7
    client._deferred_item_ids = [client_module.ITEM_TABLE["Mushroom"][0]]
    context.rom_hash = "different-patched-seed-rom"
    client.on_package(context, "Connected", {"checked_locations": []})
    check(
        client._items_received_index == 7 and bool(client._deferred_item_ids),
        "A ROM hash arriving late cannot reset the same seed's persistent item cursor",
    )


def test_persistent_item_cursor() -> None:
    storage: dict[str, dict[str, object]] = {}
    fake_utils = types.ModuleType("Utils")
    fake_utils.persistent_load = lambda: storage

    def persistent_store(category: str, key: str, value: object) -> None:
        storage.setdefault(category, {})[key] = value

    fake_utils.persistent_store = persistent_store
    previous_utils = sys.modules.get("Utils")
    sys.modules["Utils"] = fake_utils
    try:
        powerup_id = client_module.ITEM_TABLE["Fire Flower"][0]
        trap_id = client_module.ITEM_TABLE["Super Speed"][0]

        first = client_module.NSMBDSClient()
        first._session_identity = ("persistent-seed", 0, 2)
        first._items_received_index = 42
        first._deferred_item_ids = [powerup_id, trap_id]
        first._persist_item_cursor()

        restarted = client_module.NSMBDSClient()
        restarted._session_identity = ("persistent-seed", 0, 2)
        restored_cursor = restarted._load_item_cursor()
        check(
            restored_cursor == 42
            and restarted._deferred_item_ids == [powerup_id],
            "Persistent item cursor restores waiting Power-Ups but never traps",
        )
        restarted._items_received_index = restored_cursor or 0
        restarted._item_cursor_loaded = True

        rollback_context = FakeContext()
        rollback_context.server_seed_name = "persistent-seed"
        restarted.on_package(
            rollback_context,
            "ReceivedItems",
            {"index": 0, "items": [object(), object(), object()]},
        )
        check(
            restarted._items_received_index == 3
            and not restarted._deferred_item_ids,
            "A server-history rollback discards stale waiting Power-Ups",
        )

        corrupt = client_module.NSMBDSClient()
        corrupt._session_identity = ("persistent-seed", 0, 2)
        corrupt_key = corrupt._item_cursor_storage_key()
        storage["nsmbds"][corrupt_key] = {
            "cursor": 3,
            "deferred_powerups": [powerup_id, powerup_id, powerup_id, powerup_id],
        }
        check(
            corrupt._load_item_cursor() == 3
            and not corrupt._deferred_item_ids,
            "An impossible deferred queue larger than its item cursor is discarded",
        )

        fresh = client_module.NSMBDSClient()
        context = FakeContext()
        context.server_seed_name = "previously-running-seed"
        fresh.on_package(context, "Connected", {"checked_locations": []})
        fresh.on_package(
            context,
            "ReceivedItems",
            {"index": 0, "items": [object(), object(), object()]},
        )
        check(
            fresh._items_received_index == 3
            and not fresh._item_cursor_needs_initial_sync,
            "First connection sync baselines server history instead of replaying consumables",
        )
    finally:
        if previous_utils is None:
            sys.modules.pop("Utils", None)
        else:
            sys.modules["Utils"] = previous_utils


async def test_rom_validation() -> None:
    async def valid_read(*_args):
        return [ram_addresses.ROM_GAME_CODE]

    fake_bizhawk.read = valid_read
    client = client_module.NSMBDSClient()
    context = FakeContext()
    check(await client.validate_rom(context), "ROM validation accepts A2DE from the ROM domain")
    check(context.game == client.server_game and context.want_slot_data, "ROM validation configures the client context")

    fallback_calls = 0

    async def fallback_read(*_args):
        nonlocal fallback_calls
        fallback_calls += 1
        if fallback_calls == 1:
            return [b"NOPE"]
        return [ram_addresses.ROM_GAME_CODE]

    fake_bizhawk.read = fallback_read
    check(
        await client.validate_rom(FakeContext()),
        "ROM validation tries later BizHawk domains after a non-matching read",
    )
    check(fallback_calls == 2, "ROM validation stops after the first matching domain")

    async def invalid_read(*_args):
        return [b"ABCD"]

    fake_bizhawk.read = invalid_read
    check(not await client.validate_rom(FakeContext()), "ROM validation rejects another game code")


async def test_dedicated_client_rom_hash_fallback() -> None:
    async def unreadable_header(*_args):
        return [b"NOPE"]

    original_configured_rom_path = launcher_module.configured_rom_path
    original_dedicated_mode = client_module._dedicated_client_mode
    fake_bizhawk.read = unreadable_header

    try:
        with tempfile.TemporaryDirectory() as temporary_directory:
            rom_path = Path(temporary_directory) / "seed.nds"
            with rom_path.open("wb") as rom_file:
                rom_file.seek(launcher_module.ROM_GAME_CODE_OFFSET)
                rom_file.write(launcher_module.ROM_GAME_CODE)
                rom_file.seek(launcher_module.PATCH_MARKER_OFFSET)
                rom_file.write(launcher_module.PATCH_MARKER)

            with rom_path.open("rb") as rom_file:
                rom_hash = hashlib.file_digest(rom_file, "sha1").hexdigest().upper()

            launcher_module.configured_rom_path = lambda: rom_path
            client_module._dedicated_client_mode = True
            context = FakeContext()
            context.rom_hash = rom_hash
            check(
                await client_module.NSMBDSClient().validate_rom(context),
                "Dedicated client accepts the exact locally validated seed ROM by SHA-1 fallback",
            )

            context.rom_hash = "0" * 40
            check(
                not await client_module.NSMBDSClient().validate_rom(context),
                "Dedicated client rejects a running ROM whose SHA-1 differs from the selected seed ROM",
            )
    finally:
        launcher_module.configured_rom_path = original_configured_rom_path
        client_module._dedicated_client_mode = original_dedicated_mode


def test_dedicated_client_handler_isolation() -> None:
    client = client_module.NSMBDSClient()
    sonic_handler = object()
    FakeAutoBizHawkClientRegister.game_handlers = {
        ("NDS",): {"Sonic Rush": sonic_handler},
        ("DS", "NDS", "Nintendo DS"): {
            "New Super Mario Bros. DS": client,
            "Another DS Game": object(),
        },
    }

    client_module.restrict_bizhawk_handlers_to_nsmbds()

    handlers = FakeAutoBizHawkClientRegister.game_handlers
    check(
        list(handlers.values()) == [{"New Super Mario Bros. DS": client}],
        "Dedicated NSMBDS client excludes Sonic Rush and every other BizHawk handler",
    )


async def test_starman_buff() -> None:
    writes: list[tuple] = []

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    client._pending_starman_buffs = 1
    client._in_level_grace_polls = 10

    await client._apply_pending_starman_buffs(FakeContext())
    bytes_val = list(struct.pack("<I", ram_addresses.STARMAN_DURATION_FRAMES))
    expected_request = (ram_addresses.ADDR_STARMAN_TIMER, bytes_val, ram_addresses.MEMORY_DOMAIN)
    check(
        len(writes) == 1 and writes[0][0] == [expected_request] and client._pending_starman_buffs == 0,
        "Starman Buff writes 15s frame count to verified RAM timer when in level",
    )


async def test_positive_filler_bonuses() -> None:
    writes: list[tuple] = []
    reads = iter((
        [struct.pack("<I", 100 * ram_addresses.TIMER_UNITS_PER_SECOND)],
        [struct.pack("<I", 100)],
        [
            struct.pack("<I", 200 * ram_addresses.TIMER_UNITS_PER_SECOND),
            bytes([90]),
            bytes([5]),
        ],
    ))

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return next(reads)

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    client._in_level_grace_polls = 2
    client._pending_time_capsules = 1
    client._pending_starman_lites = 1
    client._pending_care_packages = 1

    await client._apply_pending_filler_bonuses(FakeContext())

    expected_time = 130 * ram_addresses.TIMER_UNITS_PER_SECOND
    check(
        (ram_addresses.ADDR_TIMER, list(struct.pack("<I", expected_time)), ram_addresses.MEMORY_DOMAIN)
        in writes[0][0]
        and not any(guard[0] == ram_addresses.ADDR_TIMER for guard in writes[0][1])
        and client._pending_time_capsules == 0,
        "Time Capsule adds 30 seconds without exact-guarding the volatile countdown",
    )
    check(
        (ram_addresses.ADDR_STARMAN_TIMER, list(struct.pack("<I", 400)), ram_addresses.MEMORY_DOMAIN)
        in writes[1][0]
        and client._pending_starman_lites == 0,
        "Starman Lite adds five seconds without replacing the normal Starman Buff",
    )
    care_writes = writes[2][0]
    check(
        (ram_addresses.ADDR_TIMER, list(struct.pack("<I", 215 * ram_addresses.TIMER_UNITS_PER_SECOND)), ram_addresses.MEMORY_DOMAIN) in care_writes
        and (ram_addresses.ADDR_COINS, [95], ram_addresses.MEMORY_DOMAIN) in care_writes
        and (ram_addresses.ADDR_LIVES, [6], ram_addresses.MEMORY_DOMAIN) in care_writes
        and client._pending_care_packages == 0,
        "Small Care Package atomically grants 15 seconds, five coins, and one life",
    )


async def test_bonus_mailbox_initialization() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, read_requests, _guards):
        expected_by_address = {
            ram_addresses.ADDR_AP_BONUS_STATE_MAGIC_1: ram_addresses.AP_BONUS_STATE_MAGIC_1,
            ram_addresses.ADDR_AP_BONUS_STATE_MAGIC_2: ram_addresses.AP_BONUS_STATE_MAGIC_2,
        }
        return [bytes([expected_by_address.get(address, 0)]) for address, _size, _domain in read_requests]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    client._pending_trap_shields = 99
    client._pending_life_insurance = 77

    await client._initialize_bonus_mailbox(FakeContext())
    await client._initialize_bonus_mailbox(FakeContext())

    expected = [
        (ram_addresses.ADDR_AP_TRAP_SHIELD_COUNT, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_LIFE_INSURANCE_COUNT, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_INSURED_DEATH_SEQUENCE, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_NOTIFICATION_SEQUENCE, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_NOTIFICATION_TYPE, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_NOTIFICATION_DETAIL, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_NOTIFICATION_ACK_SEQUENCE, [0], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_BONUS_STATE_MAGIC_1, [ram_addresses.AP_BONUS_STATE_MAGIC_1], ram_addresses.MEMORY_DOMAIN),
        (ram_addresses.ADDR_AP_BONUS_STATE_MAGIC_2, [ram_addresses.AP_BONUS_STATE_MAGIC_2], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1
        and writes[0][0] == expected
        and client._pending_trap_shields == 0
        and client._pending_life_insurance == 0,
        "A new AP session clears random protection-mailbox bytes exactly once",
    )


async def test_notification_mailbox_queue() -> None:
    writes: list[tuple] = []
    reads = iter((
        [
            bytes([7]),
            bytes([7]),
            bytes([ram_addresses.AP_BONUS_STATE_MAGIC_1]),
            bytes([ram_addresses.AP_BONUS_STATE_MAGIC_2]),
        ],
        [
            bytes([8]),
            bytes([7]),
            bytes([ram_addresses.AP_BONUS_STATE_MAGIC_1]),
            bytes([ram_addresses.AP_BONUS_STATE_MAGIC_2]),
        ],
    ))

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return next(reads)

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    client._queue_ap_notification(ram_addresses.AP_NOTIFICATION_TIME_CAPSULE)
    client._queue_ap_notification(ram_addresses.AP_NOTIFICATION_CARE_PACKAGE)

    await client._publish_next_ap_notification(FakeContext())
    await client._publish_next_ap_notification(FakeContext())

    check(
        len(writes) == 1
        and writes[0][0] == [
            (ram_addresses.ADDR_AP_NOTIFICATION_TYPE, [ram_addresses.AP_NOTIFICATION_TIME_CAPSULE], ram_addresses.MEMORY_DOMAIN),
            (ram_addresses.ADDR_AP_NOTIFICATION_DETAIL, [0], ram_addresses.MEMORY_DOMAIN),
            (ram_addresses.ADDR_AP_NOTIFICATION_SEQUENCE, [8], ram_addresses.MEMORY_DOMAIN),
        ]
        and client._pending_ap_notifications == [(ram_addresses.AP_NOTIFICATION_CARE_PACKAGE, 0)],
        "Notification mailbox publishes in order and waits for Lua acknowledgement",
    )


async def test_trap_shield_and_life_insurance_charges() -> None:
    writes: list[tuple] = []
    reads = iter(([bytes([0])], [bytes([1])], [bytes([0])]))

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return next(reads)

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()

    await client._apply_item(context, client_module.ITEM_TABLE["Trap Shield"][0])
    await client._apply_item(context, client_module.ITEM_TABLE["Super Speed"][0])
    await client._apply_item(context, client_module.ITEM_TABLE["Life Insurance"][0])

    check(
        client._pending_trap_shields == 0
        and client._pending_hyper_speed_traps == 0
        and (ram_addresses.ADDR_AP_TRAP_SHIELD_COUNT, [0], ram_addresses.MEMORY_DOMAIN) in writes[1][0],
        "Trap Shield consumes one visible charge and suppresses the next AP trap",
    )
    check(
        client._pending_ap_notifications[0]
        == (ram_addresses.AP_NOTIFICATION_TRAP_BLOCKED, 5),
        "Trap Shield prioritizes the blocked-Trap notification ahead of filler feedback",
    )
    check(
        client._pending_life_insurance == 1
        and (ram_addresses.ADDR_AP_LIFE_INSURANCE_COUNT, [1], ram_addresses.MEMORY_DOMAIN) in writes[2][0],
        "Life Insurance publishes one stackable Lua-visible charge",
    )
    check(
        buffs_module.TRAP_NOTIFICATION_DETAILS["Spotlight"] == 25
        and buffs_module.TRAP_NOTIFICATION_DETAILS["Pixelation"] == 28,
        "Trap Shield notifications identify the newer visual traps",
    )


async def test_invalid_protection_ram_never_blocks_traps() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes([0xFF])]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    client._pending_trap_shields = 0xFF

    await client._apply_item(FakeContext(), client_module.ITEM_TABLE["Slowness"][0])

    check(
        client._pending_trap_shields == 0
        and client._pending_slow_speed_traps == 1
        and writes[0][0] == [
            (ram_addresses.ADDR_AP_TRAP_SHIELD_COUNT, [0], ram_addresses.MEMORY_DOMAIN),
        ],
        "Corrupt protection RAM is reset and never suppresses a Trap",
    )


async def test_insured_death_still_sends_death_link() -> None:
    sent_deaths: list[str] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([3]),
            struct.pack("<I", 100 * ram_addresses.TIMER_UNITS_PER_SECOND),
            bytes([0]),
            bytes([0]),
            bytes([6]),
            struct.pack("<I", 0),
        ]

    fake_bizhawk.read = fake_read
    client = client_module.NSMBDSClient()
    client._last_lives = 3
    client._last_timer = 101 * ram_addresses.TIMER_UNITS_PER_SECOND
    client._last_insured_death_sequence = 5
    context = FakeContext(death_link=True)

    async def fake_send_death(message):
        sent_deaths.append(message)

    context.send_death = fake_send_death
    await client._handle_death_link(context)
    check(
        sent_deaths == ["Mario died."],
        "An insured death still emits Death Link even though the life counter was restored",
    )


async def test_return_to_map_does_not_send_death_link() -> None:
    sent_deaths: list[str] = []
    states = iter((
        (3, 100, ram_addresses.STAGE_EXIT_RETURN_TO_MAP_MASK),
        (2, 100, 0),
    ))

    async def fake_read(_bizhawk_ctx, _read_requests):
        lives, timer_seconds, exit_flags = next(states)
        return [
            bytes([lives]),
            struct.pack("<I", timer_seconds * ram_addresses.TIMER_UNITS_PER_SECOND),
            bytes([0]),
            bytes([0]),
            bytes([0]),
            struct.pack("<I", exit_flags),
        ]

    fake_bizhawk.read = fake_read
    client = client_module.NSMBDSClient()
    client._last_lives = 3
    client._last_timer = 101 * ram_addresses.TIMER_UNITS_PER_SECOND
    context = FakeContext(death_link=True)

    async def fake_send_death(message):
        sent_deaths.append(message)

    context.send_death = fake_send_death
    await client._handle_death_link(context)
    await client._handle_death_link(context)
    check(
        not sent_deaths and not client._return_to_map_pending,
        "Return to Map life loss is not treated as a local death",
    )


async def test_speed_traps() -> None:
    writes: list[tuple] = []

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()

    for counter_name, trigger, label in (
        ("_pending_coin_tax_notices", 15, "Coin Tax"),
        ("_pending_timer_drain_notices", 16, "Timer Drain"),
        ("_pending_coin_thief_notices", 17, "Coin Thief"),
        ("_pending_powerup_pickpocket_notices", 33, "Power-Up Pickpocket"),
    ):
        writes.clear()
        setattr(client, counter_name, 1)
        await client._apply_pending_speed_traps(FakeContext())
        check(
            len(writes) == 1
            and writes[0][0] == [
                (ram_addresses.ADDR_AP_TRAP_TRIGGER, [trigger], ram_addresses.MEMORY_DOMAIN)
            ]
            and getattr(client, counter_name) == 0,
            f"{label} publishes its short Trap notification with trigger 0x{trigger:02X}",
        )

    writes.clear()
    client._pending_hyper_speed_traps = 1

    await client._apply_pending_speed_traps(FakeContext())
    expected_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [1], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1
        and writes[0][0] == expected_requests
        and (ram_addresses.ADDR_AP_TRAP_TRIGGER, [0], ram_addresses.MEMORY_DOMAIN) in writes[0][1]
        and client._pending_hyper_speed_traps == 0,
        "Hyper Speed Trap uses an idle-mailbox guard without depending on timer polling",
    )

    async def busy_mailbox_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return False

    writes.clear()
    fake_bizhawk.guarded_write = busy_mailbox_guarded_write
    client._pending_slow_speed_traps = 1
    await client._apply_pending_speed_traps(FakeContext())
    check(
        client._pending_slow_speed_traps == 1,
        "A busy trap mailbox keeps the next Trap queued instead of losing it",
    )
    fake_bizhawk.guarded_write = fake_guarded_write
    client._pending_slow_speed_traps = 0

    writes.clear()
    client._pending_walljump_lock_traps = 1
    await client._apply_pending_speed_traps(FakeContext())
    expected_walljump_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [3], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_walljump_requests and client._pending_walljump_lock_traps == 0,
        "Walljump Lock Trap sends trigger code 0x03 to ADDR_AP_TRAP_TRIGGER for the sideloading script",
    )

    writes.clear()
    client._pending_no_jump_traps = 1
    await client._apply_pending_speed_traps(FakeContext())
    expected_no_jump_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [5], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_no_jump_requests and client._pending_no_jump_traps == 0,
        "No-Jump Trap sends trigger code 0x05 to ADDR_AP_TRAP_TRIGGER for the sideloading script",
    )

    writes.clear()
    client._pending_reverse_controls_traps = 1
    await client._apply_pending_speed_traps(FakeContext())
    expected_reverse_controls_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [6], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_reverse_controls_requests and client._pending_reverse_controls_traps == 0,
        "Reverse Controls Trap sends trigger code 0x06 to ADDR_AP_TRAP_TRIGGER for the sideloading script",
    )

    writes.clear()
    await client._apply_item(FakeContext(), client_module.ITEM_TABLE["No Sprint"][0])
    await client._apply_pending_speed_traps(FakeContext())
    expected_no_sprint_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [9], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1
        and writes[0][0] == expected_no_sprint_requests
        and client._pending_no_sprint_traps == 0,
        "No Sprint Trap queues from its item and sends trigger code 0x09",
    )

    writes.clear()
    await client._apply_item(FakeContext(), client_module.ITEM_TABLE["Button Swap"][0])
    await client._apply_pending_speed_traps(FakeContext())
    check(
        len(writes) == 1
        and writes[0][0] == [(ram_addresses.ADDR_AP_TRAP_TRIGGER, [10], ram_addresses.MEMORY_DOMAIN)]
        and client._pending_button_roulette_traps == 0,
        "Button Roulette Trap queues from its item and sends trigger code 0x0A",
    )

    writes.clear()
    await client._apply_item(FakeContext(), client_module.ITEM_TABLE["Ice Shoes"][0])
    await client._apply_pending_speed_traps(FakeContext())
    check(
        len(writes) == 1
        and writes[0][0] == [(ram_addresses.ADDR_AP_TRAP_TRIGGER, [11], ram_addresses.MEMORY_DOMAIN)]
        and client._pending_ice_shoes_traps == 0,
        "Ice Shoes Trap queues from its item and sends trigger code 0x0B",
    )

    for item_name, trigger, counter_name, label in (
        ("Heavy Mario", 12, "_pending_heavy_mario_traps", "Heavy Mario"),
        ("Can't Stop", 13, "_pending_auto_run_traps", "Auto Run"),
        ("Sticky Buttons", 14, "_pending_sticky_buttons_traps", "Sticky Buttons"),
        ("Camera Drift", 19, "_pending_camera_drift_traps", "Camera Drift"),
        ("Screen Flip", 20, "_pending_screen_flip_traps", "Screen Flip"),
        ("Drunk Camera", 21, "_pending_camera_sway_traps", "Camera Sway"),
        ("Boo Curse", 22, "_pending_boo_curse_traps", "Boo Curse"),
        ("I'm Stuck", 23, "_pending_im_stuck_traps", "I'm Stuck"),
        ("Screen Tint", 24, "_pending_screen_tint_traps", "Screen Tint"),
        ("Retro Filter", 25, "_pending_retro_filter_traps", "Retro Filter"),
        ("Spotlight", 26, "_pending_spotlight_traps", "Spotlight"),
        ("Pixelation", 31, "_pending_crazy_pixels_traps", "Crazy Pixels"),
        ("No Turnaround Trap", 32, "_pending_no_turnaround_traps", "No Turnaround"),
    ):
        writes.clear()
        await client._apply_item(FakeContext(), client_module.ITEM_TABLE[item_name][0])
        await client._apply_pending_speed_traps(FakeContext())
        check(
            len(writes) == 1
            and writes[0][0] == [
                (ram_addresses.ADDR_AP_TRAP_TRIGGER, [trigger], ram_addresses.MEMORY_DOMAIN)
            ]
            and getattr(client, counter_name) == 0,
            f"{label} Trap queues from its item and sends trigger code 0x{trigger:02X}",
        )

    writes.clear()
    client._pending_bonk_traps = 1
    client._bonk_trap_can_kill = True
    await client._apply_pending_speed_traps(FakeContext())
    expected_bonk_lethal_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [7], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_bonk_lethal_requests and client._pending_bonk_traps == 0,
        "Bonk Trap sends trigger code 0x07 (Lethal) when bonk_trap_can_kill is True",
    )

    writes.clear()
    client._pending_bonk_traps = 1
    client._bonk_trap_can_kill = False
    await client._apply_pending_speed_traps(FakeContext())
    expected_bonk_nonlethal_requests = [
        (ram_addresses.ADDR_AP_TRAP_TRIGGER, [8], ram_addresses.MEMORY_DOMAIN),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_bonk_nonlethal_requests and client._pending_bonk_traps == 0,
        "Bonk Trap sends trigger code 0x08 (Non-Lethal) when bonk_trap_can_kill is False",
    )

    for item_name, counter_name, lethal_code, safe_code in (
        ("Ground Clap", "_pending_ground_clap_traps", 27, 28),
        ("Head Bonk", "_pending_head_bonk_traps", 29, 30),
    ):
        for can_kill, expected_code in ((True, lethal_code), (False, safe_code)):
            writes.clear()
            client._bonk_trap_can_kill = can_kill
            await client._apply_item(FakeContext(), client_module.ITEM_TABLE[item_name][0])
            await client._apply_pending_speed_traps(FakeContext())
            check(
                len(writes) == 1
                and writes[0][0] == [
                    (ram_addresses.ADDR_AP_TRAP_TRIGGER, [expected_code], ram_addresses.MEMORY_DOMAIN)
                ]
                and getattr(client, counter_name) == 0,
                f"{item_name} sends trigger code 0x{expected_code:02X} (can_kill={can_kill})",
            )


async def test_key_lock_enforcement() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data = {"tower_castle_keys": True}
    ctx.items_received = []

    fake_level_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    fake_level_data[0x00088D18 - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0  # World 1-Tower path gate initially open

    await client._reconcile_overworld_state(ctx, bytes(fake_level_data))
    check(
        len(writes) == 1 and (0x00088D18, [0x00], ram_addresses.MEMORY_DOMAIN) in writes[0][0],
        "Tower & Castle Keys lock unobtained overworld path gate (0x00) in RAM when keys option is enabled",
    )


def test_lua_connector_connection_status_messages() -> None:
    connector_path = (
        Path(NSMBDS_DIR) / "lua_runtime" / "vendor" / "connector_bizhawk_generic.lua"
    )
    connector_source = connector_path.read_text(encoding="utf-8")
    check(
        '"NSMBDS Client connected to BizHawk."' in connector_source
        and '"NSMBDS Client disconnected from BizHawk."' in connector_source,
        "Lua announces BizHawk connection and disconnection inside the emulator feed",
    )


def test_tower_keys_own_verified_entrance_paths() -> None:
    expected_tower_paths = {
        "Grassland Tower Key": (0x00088D18,),
        "Desert Tower Key": (0x00088D36,),
        "Tropical Tower Key": (0x00088D54,),
        # Secret Exit from World 4-1 approaches the Tower from behind the Toad House.
        "Jungle Tower Key": (0x00088D71, 0x00088D7B),
        "Glacier Tower Key": (0x00088D90,),
        # Worlds 6 and 8 each contain two Towers, so both entrance paths stay.
        "Mountain Tower Key": (0x00088DAE, 0x00088DB1),
        # Secret Exit from World 7-Ghost House approaches the Tower from behind the Toad House.
        "Sky Tower Key": (0x00088DCC, 0x00088DD6),
        "Volcano Tower Key": (0x00088DE8, 0x00088DF0),
    }
    actual_tower_paths = {
        name: addresses
        for name, addresses in ram_addresses.KEY_PATH_GATE_ADDRESSES.items()
        if name.endswith("Tower Key")
    }
    check(
        actual_tower_paths == expected_tower_paths,
        "Tower Keys own every verified Tower approach while post-Tower exits remain vanilla-owned",
    )


async def test_star_coin_gate_permit_sync() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data = {"star_coin_gate_mode": 1}
    permit_id = client_module.ITEM_TABLE["Progressive Gate Pass"][0]
    ctx.items_received = [types.SimpleNamespace(item=permit_id) for _ in range(5)]

    level_data = bytes(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    await client._reconcile_overworld_state(ctx, level_data)

    expected_writes = [
        (
            ram_addresses.ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
            [0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            ram_addresses.MEMORY_DOMAIN,
        ),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_writes,
        "Five Progressive Gate Permits span the World-1 and World-2 authorization masks",
    )


async def test_vanilla_star_coin_gate_sync() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data = {"star_coin_gate_mode": 0}
    ctx.items_received = []

    level_data = bytes(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    await client._reconcile_overworld_state(ctx, level_data)

    expected_writes = [
        (
            ram_addresses.ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
            [0x0F, 0x0F, 0x07, 0x1F, 0x1F, 0x1F, 0x07, 0x07],
            ram_addresses.MEMORY_DOMAIN,
        ),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_writes,
        "Vanilla Gate mode authorizes every mapped sign without changing paths",
    )


async def test_individual_star_coin_gate_permit_sync() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data = {"star_coin_gate_mode": 2}
    selected_gates = (client_module.STAR_COIN_GATES[1], client_module.STAR_COIN_GATES[4])
    ctx.items_received = [
        types.SimpleNamespace(item=client_module.ITEM_TABLE[gate.permit_item_name][0])
        for gate in selected_gates
    ]

    level_data = bytes(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    await client._reconcile_overworld_state(ctx, level_data)

    expected_writes = [
        (
            ram_addresses.ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
            [0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
            ram_addresses.MEMORY_DOMAIN,
        ),
    ]
    check(
        len(writes) == 1 and writes[0][0] == expected_writes,
        "Individual Gate Permits publish the assigned bits in separate per-world masks",
    )


async def test_world_two_gate_purchase_is_not_relocked() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data = {"star_coin_gate_mode": 2}
    ctx.items_received = []
    world_two_gate = next(
        gate for gate in client_module.STAR_COIN_GATES if gate.world_number == 2
    )
    level_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    level_data[world_two_gate.path_address - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0

    await client._reconcile_overworld_state(ctx, bytes(level_data))

    check(
        writes == [],
        "Purchased World-2 paths remain open while missing Permits only block new purchases",
    )


async def test_overworld_reconciler_restores_savestate_rollback() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        # Simulate the same old RAM state after loading a savestate twice.
        return [bytes(16), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data.update({
        "tower_castle_keys": True,
        "star_coin_gate_mode": 2,
    })
    ctx.items_received = [
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Desert Pass"][0]),
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Grassland Tower Key"][0]),
    ]
    level_data = bytes(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)

    await client._reconcile_overworld_state(ctx, level_data)
    await client._reconcile_overworld_state(ctx, level_data)

    world_two_write = (
        ram_addresses.ADDR_WORLD_FLAGS_BASE + 2,
        list(struct.pack("<H", ram_addresses.WORLD_ENABLED_VALUE)),
        ram_addresses.MEMORY_DOMAIN,
    )
    tower_gate_write = (
        ram_addresses.KEY_PATH_GATE_ADDRESSES["Grassland Tower Key"][0],
        [0xC0],
        ram_addresses.MEMORY_DOMAIN,
    )
    check(
        len(writes) == 2
        and all(world_two_write in batch[0] and tower_gate_write in batch[0] for batch in writes),
        "The reconciler restores World Access and key paths again after a savestate rollback",
    )


async def test_overworld_reconciler_skips_matching_state() -> None:
    writes: list[tuple] = []
    world_flags = bytearray(16)
    world_flags[2:4] = struct.pack("<H", ram_addresses.WORLD_ENABLED_VALUE)

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(world_flags), bytes(8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data.update({
        "tower_castle_keys": True,
        "star_coin_gate_mode": 2,
    })
    ctx.items_received = [
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Desert Pass"][0]),
        types.SimpleNamespace(item=client_module.ITEM_TABLE["Grassland Tower Key"][0]),
    ]
    level_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    tower_gate = ram_addresses.KEY_PATH_GATE_ADDRESSES["Grassland Tower Key"][0]
    level_data[tower_gate - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0

    await client._reconcile_overworld_state(ctx, bytes(level_data))
    check(not writes, "The reconciler performs no RAM write when every owned value already matches")


async def test_star_coin_item_currency_reconciliation() -> None:
    writes: list[tuple] = []

    async def fake_guarded_read(_bizhawk_ctx, read_requests, _guards):
        check(
            read_requests[-1] == (
                ram_addresses.ADDR_AP_STAR_COIN_CURRENCY_MAILBOX,
                8,
                ram_addresses.MEMORY_DOMAIN,
            ),
            "Star Coin item mode reads the native hook currency mailbox",
        )
        return [
            bytes(16),
            bytes([0xFF] * 8),
            bytes(8),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data.update({
        "tower_castle_keys": False,
        "star_coin_gate_mode": 0,
        "star_coin_items": True,
    })
    star_coin_id = client_module.ITEM_TABLE["Star Coin"][0]
    ctx.items_received = [types.SimpleNamespace(item=star_coin_id) for _ in range(12)]
    first_gate = client_module.STAR_COIN_GATES[0]
    client._gate_purchase_mask = 0b11
    level_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    second_gate = client_module.STAR_COIN_GATES[1]
    level_data[second_gate.path_address - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0

    await client._reconcile_overworld_state(ctx, bytes(level_data))

    expected_currency_write = (
        ram_addresses.ADDR_AP_STAR_COIN_CURRENCY_MAILBOX,
        list(ram_addresses.AP_STAR_COIN_CURRENCY_MAGIC) + [2, 0, 0, 0],
        ram_addresses.MEMORY_DOMAIN,
    )
    check(
        client._star_coin_lifetime == 12
        and client._star_coin_spent == 10
        and client._star_coin_available == 2
        and expected_currency_write in writes[-1][0],
        "The native hook receives AP Star Coins minus confirmed purchases",
    )
    check(
        all(write[0] != 0x00088BDC for write in writes[-1][0]),
        "Currency sync never overwrites the vanilla Star-Coin state structure",
    )
    check(
        (
            first_gate.path_address,
            [0xC0],
            ram_addresses.MEMORY_DOMAIN,
        ) in writes[-1][0],
        "A server-confirmed sign purchase reopens after loading an older savestate",
    )

    all_gates_client = client_module.NSMBDSClient()
    all_gates_client._gate_purchase_mask = (1 << len(client_module.STAR_COIN_GATES)) - 1
    all_gates_context = FakeContext()
    all_gates_context.items_received = [
        types.SimpleNamespace(item=star_coin_id) for _ in range(160)
    ]
    check(
        all_gates_client._star_coin_balances(all_gates_context) == (160, 160, 0),
        "160 received Star Coins pay for all 32 signs in any purchase order",
    )

async def test_star_coin_currency_ignores_dynamic_map_heap() -> None:
    writes: list[list[tuple[int, list[int], str]]] = []

    async def fake_guarded_read(_bizhawk_ctx, _read_requests, _guards):
        return [bytes(16), bytes([0xFF] * 8), bytes(8)]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, _guards):
        writes.append(write_requests)
        return True

    fake_bizhawk.guarded_read = fake_guarded_read
    fake_bizhawk.guarded_write = fake_guarded_write

    client = client_module.NSMBDSClient()
    ctx = FakeContext()
    ctx.slot_data.update({
        "tower_castle_keys": False,
        "star_coin_gate_mode": 0,
        "star_coin_items": True,
    })
    star_coin_id = client_module.ITEM_TABLE["Star Coin"][0]
    ctx.items_received = [types.SimpleNamespace(item=star_coin_id) for _ in range(12)]
    client._gate_purchase_mask = 0b11
    level_data = bytes(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)

    await client._reconcile_overworld_state(ctx, level_data)
    check(
        any(
            write[0] == ram_addresses.ADDR_AP_STAR_COIN_CURRENCY_MAILBOX
            and write[1][-4:] == [2, 0, 0, 0]
            for batch in writes for write in batch
        ),
        "Currency synchronization is independent of transient map heap objects",
    )


async def test_star_coin_gate_purchase_location() -> None:
    sent_messages: list[dict] = []

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    client = client_module.NSMBDSClient()
    client._session_identity = ("seed-a", 1, 1)
    ctx = FakeContext()
    ctx.slot_data["star_coin_items"] = True
    ctx.send_msgs = fake_send_msgs
    gate = client_module.STAR_COIN_GATES[0]
    level_data = bytearray(ram_addresses.LEVEL_AND_SECRET_FLAG_READ_SIZE)
    level_data[gate.path_address - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0

    await client._detect_and_store_gate_purchases(ctx, bytes(level_data))
    check(
        not sent_messages,
        "Already-open save paths are baselined instead of charged as purchases",
    )

    level_data[gate.path_address - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0x00
    await client._detect_and_store_gate_purchases(ctx, bytes(level_data))
    level_data[gate.path_address - ram_addresses.ADDR_LEVEL_DATA_BASE] = 0xC0

    await client._detect_and_store_gate_purchases(ctx, bytes(level_data))
    check(
        len(sent_messages) == 1
        and sent_messages[0]["cmd"] == "Set"
        and sent_messages[0]["operations"] == [{
            "operation": "or",
            "value": client._gate_purchase_payload(),
        }],
        "Buying a native Star Coin sign stores an invisible DataStorage bit",
    )
    check(
        client._gate_purchase_mask == 1,
        "A stored sign purchase is retained in the local purchase mask",
    )

    sync_messages: list[dict] = []

    async def fake_sync_send(messages):
        sync_messages.extend(messages)

    ctx.send_msgs = fake_sync_send
    client._gate_storage_sync_pending = True
    await client._sync_gate_purchase_storage(ctx)
    check(
        [message["cmd"] for message in sync_messages]
        == ["SetNotify", "Get"],
        "A reconnect reads authoritative gate purchases without uploading a local fallback",
    )
    storage_key = client._gate_purchase_storage_key()
    check(
        client._handle_gate_storage_packet(
            "Retrieved", {"keys": {storage_key: 0b100}}
        )
        and client._gate_purchase_mask == 0b101,
        "Retrieved server purchase bits merge with purchases from the current session",
    )

    retry_messages: list[dict] = []

    async def fake_retry_send(messages):
        retry_messages.extend(messages)

    ctx.send_msgs = fake_retry_send
    client._gate_storage_write_pending = True
    await client._sync_gate_purchase_storage(ctx)
    check(
        [message["cmd"] for message in retry_messages] == ["Set"]
        and retry_messages[0]["operations"] == [{
            "operation": "or",
            "value": client._gate_purchase_payload(),
        }]
        and not client._gate_storage_write_pending,
        "A failed current-session gate purchase is retried without restoring legacy local data",
    )



async def test_red_coin_mailbox() -> None:
    writes: list[tuple] = []
    sent_messages: list[dict] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([12]),
            bytes([ram_addresses.AP_EVENT_TYPE_RED_COIN_COMPLETE]),
            struct.pack("<I", 0),
            struct.pack("<I", 1),
            struct.pack("<I", 0),
            struct.pack("<i", 50),
            bytes([1]),
            bytes([11]),
            bytes([12]),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    fake_bizhawk.read = fake_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = fake_send_msgs
    client._active_location_set_known = True
    expected_location = locations.LOCATION_TABLE["World 1-1 Red Coin Challenge"]
    client._active_locations = {expected_location}

    await client._detect_and_send_red_coin_challenge(context)
    check(
        sent_messages == [{"cmd": "LocationChecks", "locations": [expected_location]}],
        "Red Coin mailbox resolves World 1-1 and submits its one AP check",
    )
    check(
        writes and writes[0][0] == [
            (ram_addresses.ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, [12], ram_addresses.MEMORY_DOMAIN)
        ],
        "Red Coin mailbox event is acknowledged after successful submission",
    )
    check(
        expected_location in client._sent_locations,
        "Red Coin completion updates the local sent-location cache",
    )


async def test_one_up_block_mailbox() -> None:
    writes: list[tuple] = []
    sent_messages: list[dict] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([13]),
            bytes([ram_addresses.AP_EVENT_TYPE_BLOCK_BUMP]),
            struct.pack("<I", 0),
            struct.pack("<I", 1),
            struct.pack("<I", 0),
            struct.pack("<i", 105),
            struct.pack("<i", -14),
            bytes([12]),
            bytes([13]),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    fake_bizhawk.read = fake_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = fake_send_msgs
    client._active_location_set_known = True
    expected_location = locations.LOCATION_TABLE["World 1-1 1-Up Block"]
    client._active_locations = {expected_location}

    await client._detect_and_send_block_check(context)
    check(
        sent_messages == [{"cmd": "LocationChecks", "locations": [expected_location]}],
        "Block mailbox resolves the verified World 1-1 brick and submits one AP check",
    )
    check(
        writes and writes[0][0] == [
            (ram_addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, [13], ram_addresses.MEMORY_DOMAIN)
        ],
        "Block mailbox event is acknowledged after successful submission",
    )
    check(
        expected_location in client._sent_locations,
        "1-Up completion updates the local sent-location cache",
    )


async def test_block_mailbox_send_failure_keeps_event_pending() -> None:
    writes: list[tuple] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([14]),
            bytes([ram_addresses.AP_EVENT_TYPE_BLOCK_BUMP]),
            struct.pack("<I", 0),
            struct.pack("<I", 1),
            struct.pack("<I", 0),
            struct.pack("<i", 18),
            struct.pack("<i", -27),
            bytes([13]),
            bytes([14]),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def failing_send_msgs(_messages):
        raise ConnectionError("test disconnect")

    fake_bizhawk.read = fake_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = failing_send_msgs
    expected_location = locations.LOCATION_TABLE["World 1-1 Blocksanity Block 1"]
    client._active_location_set_known = True
    client._active_locations = {expected_location}

    await client._detect_and_send_block_check(context)
    check(
        not writes and expected_location not in client._sent_locations,
        "A failed Blocksanity submission leaves the current mailbox event pending for retry",
    )


async def test_blocksanity_mailbox() -> None:
    writes: list[tuple] = []
    sent_messages: list[dict] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([14]),
            bytes([ram_addresses.AP_EVENT_TYPE_BLOCK_BUMP]),
            struct.pack("<I", 0),
            struct.pack("<I", 1),
            struct.pack("<I", 0),
            struct.pack("<i", 18),
            struct.pack("<i", -27),
            bytes([13]),
            bytes([14]),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    fake_bizhawk.read = fake_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = fake_send_msgs
    client._active_location_set_known = True
    expected_location = locations.LOCATION_TABLE["World 1-1 Blocksanity Block 1"]
    client._active_locations = {expected_location}

    await client._detect_and_send_block_check(context)
    check(
        sent_messages == [{"cmd": "LocationChecks", "locations": [expected_location]}],
        "Block mailbox resolves a World 1-1 static Blocksanity source and submits its AP check",
    )
    check(
        writes and writes[0][0] == [
            (ram_addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, [14], ram_addresses.MEMORY_DOMAIN)
        ],
        "Blocksanity mailbox event is acknowledged after successful submission",
    )
    check(
        expected_location in client._sent_locations,
        "Blocksanity completion updates the local sent-location cache",
    )


async def test_moving_block_mailboxes() -> None:
    async def run_case(
        *,
        world: int,
        level: int,
        area: int,
        tile_x: int,
        tile_y: int,
        location_name: str,
    ) -> tuple[list[dict], list[tuple], int]:
        writes: list[tuple] = []
        sent_messages: list[dict] = []

        async def fake_read(_bizhawk_ctx, _read_requests):
            return [
                bytes([22]),
                bytes([ram_addresses.AP_EVENT_TYPE_MOVING_BLOCK_OPEN]),
                struct.pack("<I", world),
                struct.pack("<I", level),
                struct.pack("<I", area),
                struct.pack("<i", tile_x),
                struct.pack("<i", tile_y),
                bytes([21]),
                bytes([22]),
            ]

        async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
            writes.append((write_requests, guards))
            return True

        async def fake_send_msgs(messages):
            sent_messages.extend(messages)

        fake_bizhawk.read = fake_read
        fake_bizhawk.guarded_write = fake_guarded_write
        client = client_module.NSMBDSClient()
        context = FakeContext()
        context.send_msgs = fake_send_msgs
        expected_location = locations.LOCATION_TABLE[location_name]
        client._active_location_set_known = True
        client._active_locations = {expected_location}

        await client._detect_and_send_block_check(context)
        return sent_messages, writes, expected_location

    flying_one_up_messages, flying_one_up_writes, flying_one_up_id = await run_case(
        world=6,
        level=1,
        area=129,
        tile_x=104,
        tile_y=-37,
        location_name="World 7-1 Flying 1-Up Block",
    )
    check(
        flying_one_up_messages == [{"cmd": "LocationChecks", "locations": [flying_one_up_id]}],
        "Moving-block mailbox resolves the live-verified World 7-1 flying 1-Up",
    )
    check(
        flying_one_up_writes and flying_one_up_writes[0][0] == [
            (ram_addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, [22], ram_addresses.MEMORY_DOMAIN)
        ],
        "Flying 1-Up event is acknowledged after successful submission",
    )

    blocksanity_messages, _blocksanity_writes, blocksanity_id = await run_case(
        world=4,
        level=1,
        area=88,
        tile_x=191,
        tile_y=-25,
        location_name="World 5-1 Blocksanity Flying Block 1",
    )
    check(
        blocksanity_messages == [{"cmd": "LocationChecks", "locations": [blocksanity_id]}],
        "Moving-block mailbox resolves a Sprite-290 Blocksanity source",
    )

    world_6_2_messages, _world_6_2_writes, world_6_2_id = await run_case(
        world=5,
        level=2,
        area=109,
        tile_x=49,
        tile_y=-7,
        location_name="World 6-2 Blocksanity Flying Block 1",
    )
    check(
        world_6_2_messages == [{"cmd": "LocationChecks", "locations": [world_6_2_id]}],
        "Moving-block mailbox resolves the live-probed first World 6-2 flying block",
    )

    bonus_coin_messages, _bonus_coin_writes, bonus_coin_id = await run_case(
        world=5,
        level=2,
        area=110,
        tile_x=32,
        tile_y=-20,
        location_name="World 6-2 Bonus Area Blocksanity Flying Block 1",
    )
    check(
        bonus_coin_messages == [{"cmd": "LocationChecks", "locations": [bonus_coin_id]}],
        "Moving-block mailbox resolves a World 6-2 bonus-area flying Coin Block",
    )

    bonus_one_up_messages, _bonus_one_up_writes, bonus_one_up_id = await run_case(
        world=5,
        level=2,
        area=110,
        tile_x=33,
        tile_y=-20,
        location_name="World 6-2 Bonus Area Flying 1-Up Block 1",
    )
    check(
        bonus_one_up_messages == [{"cmd": "LocationChecks", "locations": [bonus_one_up_id]}],
        "Moving-block mailbox resolves a World 6-2 bonus-area flying 1-Up Block",
    )

    early_open_messages, _early_open_writes, early_open_id = await run_case(
        world=5,
        level=2,
        area=109,
        tile_x=51,
        tile_y=-8,
        location_name="World 6-2 Blocksanity Flying Block 1",
    )
    check(
        early_open_messages == [{"cmd": "LocationChecks", "locations": [early_open_id]}],
        "An early World 6-2 block opened before baseline resolves to its nearby immutable spawn",
    )


async def test_blocksanity_ground_pound_mailbox() -> None:
    writes: list[tuple] = []
    sent_messages: list[dict] = []

    async def fake_read(_bizhawk_ctx, _read_requests):
        return [
            bytes([16]),
            bytes([ram_addresses.AP_EVENT_TYPE_BLOCK_GROUND_POUND]),
            struct.pack("<I", 0),
            struct.pack("<I", 1),
            struct.pack("<I", 0),
            struct.pack("<i", 18),
            struct.pack("<i", -26),
            bytes([15]),
            bytes([16]),
        ]

    async def fake_guarded_write(_bizhawk_ctx, write_requests, guards):
        writes.append((write_requests, guards))
        return True

    async def fake_send_msgs(messages):
        sent_messages.extend(messages)

    fake_bizhawk.read = fake_read
    fake_bizhawk.guarded_write = fake_guarded_write
    client = client_module.NSMBDSClient()
    context = FakeContext()
    context.send_msgs = fake_send_msgs
    client._active_location_set_known = True
    expected_location = locations.LOCATION_TABLE["World 1-1 Blocksanity Block 1"]
    client._active_locations = {expected_location}

    await client._detect_and_send_block_check(context)
    check(
        sent_messages == [{"cmd": "LocationChecks", "locations": [expected_location]}],
        "Ground-pound mailbox resolves the unique block one tile below Mario",
    )
    check(
        writes and writes[0][0] == [
            (ram_addresses.ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, [16], ram_addresses.MEMORY_DOMAIN)
        ],
        "Ground-pound Blocksanity event is acknowledged after successful submission",
    )


def test_block_resolution_never_selects_vertical_neighbor() -> None:
    client = client_module.NSMBDSClient()
    location_name = client._resolve_block_location(
        (0, 1, 0, 18, -26),
        ram_addresses.AP_EVENT_TYPE_BLOCK_BUMP,
    )
    check(
        location_name is None,
        "A hit below a catalogued block never checks the vertical neighbour",
    )


def test_block_resolution_never_selects_horizontal_neighbor() -> None:
    client = client_module.NSMBDSClient()
    bump_location = client._resolve_block_location(
        (0, 1, 0, 17, -27),
        ram_addresses.AP_EVENT_TYPE_BLOCK_BUMP,
    )
    ground_pound_location = client._resolve_block_location(
        (0, 1, 0, 17, -26),
        ram_addresses.AP_EVENT_TYPE_BLOCK_GROUND_POUND,
    )
    check(
        bump_location is None and ground_pound_location is None,
        "Breaking a block beside a catalogued block never checks its horizontal neighbour",
    )


def main() -> None:
    tests = [
        test
        for name, test in tuple(globals().items())
        if name.startswith("test_") and callable(test)
    ]
    for test in tests:
        result = test()
        if inspect.isawaitable(result):
            asyncio.run(result)
    print(f"All {len(tests)} client logic test groups passed.")


if __name__ == "__main__":
    main()
