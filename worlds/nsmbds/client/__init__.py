"""BizHawk client facade for New Super Mario Bros. DS."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from collections import deque
from time import perf_counter
from typing import TYPE_CHECKING, Sequence

from worlds._bizhawk.client import BizHawkClient

from .features.buffs import BuffHandlingMixin
from .features.emulator_feed import EmulatorFeedMixin
from .features.death_link import DeathLinkMixin
from .features.goals import (
    BOSS_LOCATION_IDS,
    FINAL_BOSS_LOCATION_ID,
    GoalHandlingMixin,
)
from .features.items import ItemHandlingMixin
from .features.notifications import NotificationHandlingMixin
from .features.locations import LocationTrackingMixin, STAR_COIN_LOCATION_IDS
from .features.block_checks import BlockCheckTrackingMixin
from .features.overworld import OverworldStateReconcilerMixin
from .features.red_coins import RedCoinTrackingMixin
from .features.traps import TIMER_DRAIN_UNITS, TrapHandlingMixin
from .features.tracker_sync import PopTrackerWorldSyncMixin
from ..items import ITEM_TABLE
from ..locations import LOCATION_TABLE
from ..data.star_coin_gates import STAR_COIN_GATES
from ..data.powerup_licenses import (
    BLUE_SHELL_LICENSE,
    FIRE_FLOWER_LICENSE,
    MEGA_MUSHROOM_LICENSE,
    MINI_MUSHROOM_LICENSE,
    MUSHROOM_LICENSE,
    TOUCHSCREEN_RESERVE_LICENSE,
    active_license_items,
    native_license_mode,
)
from ..data.ram_addresses import (
    ADDR_AP_MINI_CASTLE_FLAGS_PERM,
    ADDR_AP_POWERUP_LICENSE_MASK,
    ADDR_AP_POWERUP_LICENSE_MODE,
    ADDR_LEVEL_DATA_BASE,
    LEVEL_AND_SECRET_FLAG_READ_SIZE,
    LOCATION_DATA_SNAPSHOT_SIZE,
    LEVEL_DATA_WORLD_HEADER_MASK,
    LEVEL_DATA_WORLD_HEADER_MAX_STATE,
    LEVEL_DATA_WORLD_HEADER_OFFSETS,
    LEVEL_DATA_WORLD_HEADER_VALUE,
    MEMORY_DOMAIN,
    ROM_GAME_CODE,
    ROM_GAME_CODE_SIZE,
    ROM_GAME_CODE_LOCATIONS,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")
network_logger = logger.getChild("Network")
bridge_logger = logger.getChild("Bridge")
sync_logger = logger.getChild("Sync")
_dedicated_client_mode = False
# The bridge answers on emulator frames. Several sequential requests routinely
# put a complete watcher pass near 150 ms without any individual stall.
WATCHER_OPERATION_SLOW_SECONDS = 0.200
WATCHER_TOTAL_SLOW_SECONDS = 0.300
MEDIUM_POLL_TICKS = 3
SLOW_POLL_TICKS = 10
WATCHER_SLOW_LOG_COOLDOWN_SECONDS = 5.0
WATCHER_ISSUE_LOG_COOLDOWN_SECONDS = 30.0


def _selected_seed_rom_matches_hash(ctx: "BizHawkClientContext") -> bool:
    """Verify the running ROM against the exact seed ROM selected by this client."""
    from .launcher import configured_rom_path, validate_seed_rom

    rom_path = configured_rom_path()
    rom_hash = getattr(ctx, "rom_hash", None)
    if rom_path is None or not rom_hash:
        return False

    try:
        validate_seed_rom(rom_path)
        with rom_path.open("rb") as rom_file:
            selected_hash = hashlib.file_digest(rom_file, "sha1").hexdigest()
    except (OSError, ValueError):
        return False

    return selected_hash.casefold() == str(rom_hash).casefold()

class NSMBDSClient(
    EmulatorFeedMixin,
    BlockCheckTrackingMixin,
    RedCoinTrackingMixin,
    LocationTrackingMixin,
    ItemHandlingMixin,
    NotificationHandlingMixin,
    BuffHandlingMixin,
    TrapHandlingMixin,
    DeathLinkMixin,
    GoalHandlingMixin,
    OverworldStateReconcilerMixin,
    PopTrackerWorldSyncMixin,
    BizHawkClient,
):
    """Bridge verified NSMBDS RAM state to an Archipelago server."""

    system = ("NDS", "DS", "Nintendo DS")
    patch_suffix = ".apnsmbds"
    game = "New Super Mario Bros. DS"
    server_game = "New Super Mario Bros. DS"

    @classmethod
    def make_gui(cls, ctx: "BizHawkClientContext") -> type:
        from .ui import install_kivy_hover_density_guard
        from .ui.tracker.view import make_tracker_gui

        install_kivy_hover_density_guard()
        return make_tracker_gui(ctx)

    def run_gui(self, ctx: "BizHawkClientContext") -> None:
        from .ui import install_kivy_hover_density_guard
        from .ui.tracker.view import make_tracker_gui

        install_kivy_hover_density_guard()
        make_tracker_gui(ctx)

    def __init__(self) -> None:
        super().__init__()
        self._observed_locations: set[int] = set()
        self._pending_emulator_feed: deque[tuple[tuple[str, str], ...]] = deque(maxlen=2000)
        self._emulator_feed_flush_lock = asyncio.Lock()
        self._emulator_feed_flush_task: asyncio.Task[None] | None = None
        self._emulator_feed_received_index = 0
        self._emulator_feed_server_announced = False
        self._emulator_feed_config_sent: tuple[bool, int, str, int] | None = None
        self._star_coin_tracking_mode_sent: int | None = None
        self._sent_locations: set[int] = set()
        self._active_locations: set[int] = set()
        self._active_location_set_known = False
        self._items_received_index = 0
        self._pending_item_transaction = None
        self._item_transaction_owner = "network"
        self._next_powerup_id: int | None = None
        self._item_cursor_loaded = False
        self._item_cursor_needs_initial_sync = False
        self._awaiting_item_history = False
        self._deferred_item_ids: list[int] = []
        self._goal_sent = False
        self._session_identity: tuple[object, ...] | None = None
        self._last_not_ready_logged = False
        self._game_data_header_values: tuple[int, ...] | None = None
        self._death_link_enabled: bool | None = None
        self._pending_death_link = False
        self._pending_death_link_effect: int | None = None
        self._death_link_rng = random.Random()
        self._death_link_cooldown_until = 0.0
        self._death_link_amnesty_count = 0
        self._suppress_next_local_death = False
        self._last_lives: int | None = None
        self._last_timer: int | None = None
        self._in_level_grace_polls = 0
        self._return_to_map_pending = False
        self._pending_timer_drains = 0
        self._pending_starman_buffs = 0
        self._pending_time_capsules = 0
        self._pending_starman_lites = 0
        self._pending_care_packages = 0
        self._pending_trap_shields = 0
        self._pending_life_insurance = 0
        self._pending_ap_notifications: list[tuple[int, int]] = []
        self._last_insured_death_sequence: int | None = None
        self._last_return_to_map_death_sequence: int | None = None
        self._bonus_mailbox_needs_reset = True
        self._pending_hyper_speed_traps = 0
        self._pending_slow_speed_traps = 0
        self._pending_walljump_lock_traps = 0
        self._pending_no_jump_traps = 0
        self._pending_reverse_controls_traps = 0
        self._pending_no_sprint_traps = 0
        self._pending_button_roulette_traps = 0
        self._pending_ice_shoes_traps = 0
        self._pending_heavy_mario_traps = 0
        self._pending_auto_run_traps = 0
        self._pending_sticky_buttons_traps = 0
        self._pending_camera_drift_traps = 0
        self._pending_screen_flip_traps = 0
        self._pending_camera_sway_traps = 0
        self._pending_boo_curse_traps = 0
        self._pending_im_stuck_traps = 0
        self._pending_screen_tint_traps = 0
        self._pending_retro_filter_traps = 0
        self._pending_spotlight_traps = 0
        self._pending_ground_clap_traps = 0
        self._pending_head_bonk_traps = 0
        self._pending_crazy_pixels_traps = 0
        self._pending_no_turnaround_traps = 0
        self._pending_coin_tax_notices = 0
        self._pending_timer_drain_notices = 0
        self._pending_coin_thief_notices = 0
        self._pending_powerup_pickpocket_notices = 0
        self._pending_bonk_traps = 0
        self._bonk_trap_can_kill = True
        self._speed_trap_end_time = 0.0
        self._active_speed_multiplier = 1.0
        self._held_powerup_log_key: tuple[str, str] | None = None
        self._star_coin_lifetime = 0
        self._star_coin_spent = 0
        self._star_coin_available = 0
        self._gate_path_open_states: dict[int, bool] = {}
        self._gate_purchase_mask = 0
        self._gate_purchase_spent_floor = 0
        self._gate_storage_sync_pending = False
        self._gate_storage_write_pending = False
        self._last_published_poptracker_view: str | None = None
        self._watcher_tick = 0
        self._native_block_configuration_ready = False
        self._watcher_slow_log_times: dict[str, float] = {}
        self._watcher_issue_log_times: dict[str, float] = {}
        self._watcher_diagnostics = None
        self._logged_unmatched_block_events: set[tuple[int, ...]] = set()

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        """Accept only the verified NSMBDS USA ROM header code."""
        from worlds._bizhawk import read

        matched_location: tuple[int, str] | None = None
        observations: list[str] = []
        for address, domain in ROM_GAME_CODE_LOCATIONS:
            try:
                rom_data = await read(
                    ctx.bizhawk_ctx,
                    [(address, ROM_GAME_CODE_SIZE, domain)],
                )
                game_code = rom_data[0] if rom_data else b""
                observations.append(f"{domain}@0x{address:X}={game_code!r}")
                if game_code == ROM_GAME_CODE:
                    matched_location = (address, domain)
                    break
            except Exception as exc:
                observations.append(f"{domain}@0x{address:X}=unavailable ({exc})")

        verified_by_selected_rom = (
            matched_location is None
            and _dedicated_client_mode
            and _selected_seed_rom_matches_hash(ctx)
        )
        if matched_location is None and not verified_by_selected_rom:
            logger.warning(
                "NSMBDS handler rejected the loaded ROM: expected game code %r; "
                "BizHawk reads: %s (hash: %s). Another game handler may be tried next.",
                ROM_GAME_CODE,
                "; ".join(observations) or "no readable ROM domains",
                getattr(ctx, "rom_hash", None),
            )
            return False

        ctx.game = getattr(self, "server_game", self.game)
        ctx.server_game = getattr(self, "server_game", self.game)
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        self._install_death_link_log_filter(ctx)
        if matched_location is not None:
            address, domain = matched_location
            logger.info(
                "Verified NSMB DS USA ROM (code: %s, domain: %s@0x%X, hash: %s).",
                ROM_GAME_CODE.decode("ascii"),
                domain,
                address,
                getattr(ctx, "rom_hash", None),
            )
        else:
            logger.warning(
                "Verified NSMBDS through the exact selected seed-ROM SHA-1 because this "
                "BizHawk installation did not expose a matching ROM-header domain (hash: %s).",
                getattr(ctx, "rom_hash", None),
            )
        self._emulator_feed_server_announced = False
        self._emulator_feed_config_sent = None
        self._star_coin_tracking_mode_sent = None
        self._native_block_configuration_ready = False
        return True

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        """Poll verified game data, submit checks, and apply pending features."""
        from worlds._bizhawk import NotConnectedError, RequestFailedError

        self._watcher_diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
        watcher_started = perf_counter()
        try:
            await self._run_game_watcher(ctx)
        except (RequestFailedError, NotConnectedError) as exc:
            observe_bridge = getattr(ctx, "observe_bridge", None)
            if observe_bridge is not None:
                state = "DISCONNECTED" if isinstance(exc, NotConnectedError) else "ERROR"
                observe_bridge(state, str(exc), type(exc).__name__)
            if self._should_log_watcher_issue("bridge:connection"):
                bridge_logger.info("BizHawk connection lost; retrying on the next watcher tick: %s", exc)
        finally:
            elapsed = perf_counter() - watcher_started
            if elapsed >= WATCHER_TOTAL_SLOW_SECONDS:
                self._log_slow_watcher_operation("total", elapsed)

    def _log_slow_watcher_operation(self, operation_name: str, elapsed: float) -> None:
        """Rate-limit diagnostics so a persistent stall cannot create a log storm."""
        now = perf_counter()
        previous = self._watcher_slow_log_times.get(operation_name, -WATCHER_SLOW_LOG_COOLDOWN_SECONDS)
        if now - previous < WATCHER_SLOW_LOG_COOLDOWN_SECONDS:
            return
        self._watcher_slow_log_times[operation_name] = now
        if operation_name == "total":
            logger.warning("Slow NSMBDS game_watcher: %.1f ms.", elapsed * 1000)
        else:
            logger.warning(
                "Slow NSMBDS watcher operation %s: %.1f ms.",
                operation_name,
                elapsed * 1000,
            )

    def _should_log_watcher_issue(self, issue: str) -> bool:
        now = perf_counter()
        previous = self._watcher_issue_log_times.get(issue, -WATCHER_ISSUE_LOG_COOLDOWN_SECONDS)
        if now - previous < WATCHER_ISSUE_LOG_COOLDOWN_SECONDS:
            return False
        self._watcher_issue_log_times[issue] = now
        return True

    async def _run_watcher_operation(self, operation_name: str, operation):
        """Run one watcher operation and report only meaningful stalls."""
        started = perf_counter()
        try:
            return await operation
        except Exception as exc:
            if self._should_log_watcher_issue(f"operation:{operation_name}:{type(exc).__name__}"):
                logger.exception("NSMBDS %s failed; the watcher will retry next tick.", operation_name)
                if self._watcher_diagnostics is not None:
                    self._watcher_diagnostics.error(operation_name, exc)
        finally:
            elapsed = perf_counter() - started
            if elapsed >= WATCHER_OPERATION_SLOW_SECONDS:
                self._log_slow_watcher_operation(operation_name, elapsed)

    async def _submit_pending_mailbox_checks(
        self,
        ctx: "BizHawkClientContext",
        pending_checks: list[tuple[str, int, int]],
    ) -> None:
        """Submit simultaneous Lua mailbox checks in one AP message, then acknowledge them."""
        if not pending_checks:
            return
        location_ids = list(dict.fromkeys(
            location_id for _kind, location_id, _sequence in pending_checks
        ))
        diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
        if diagnostics is not None:
            names = {identifier: name for name, identifier in LOCATION_TABLE.items()}
            for location_id in location_ids:
                if location_id not in self._observed_locations:
                    diagnostics.last_detected_location = location_id
                    diagnostics.counters["locations_detected"] += 1
                    diagnostics.event("LOCATION", "detected", names.get(location_id, f"id={location_id}"))
        if not await self._send_location_checks(ctx, location_ids):
            return
        self._observed_locations.update(location_ids)
        self._sent_locations.update(location_ids)
        if diagnostics is not None:
            diagnostics.last_submitted_location = location_ids[-1]
            diagnostics.event("LOCATION", "submitted", f"count={len(location_ids)}")

        from worlds._bizhawk import guarded_write

        for kind, _location_id, sequence in pending_checks:
            if kind == "block":
                await self._acknowledge_block_event(ctx, sequence, guarded_write)
            else:
                await self._acknowledge_red_coin_event(ctx, sequence, guarded_write)

    async def _run_game_watcher(self, ctx: "BizHawkClientContext") -> None:
        """Prioritize event-sensitive work and stagger maintenance polling."""
        server_connected = (
            ctx.server is not None
            and not ctx.server.socket.closed
            and ctx.slot is not None
            and ctx.slot_data is not None
        )

        await self._run_watcher_operation(
            "emulator feed synchronization",
            self._sync_emulator_feed(ctx, server_connected=server_connected),
        )

        if not server_connected:
            self._last_published_poptracker_view = None
            return

        self._watcher_tick += 1
        medium_due = self._watcher_tick == 1 or self._watcher_tick % MEDIUM_POLL_TICKS == 0
        slow_due = self._watcher_tick == 1 or self._watcher_tick % SLOW_POLL_TICKS == 0

        if self._star_coin_tracking_mode_sent is None or slow_due:
            await self._run_watcher_operation(
                "Star Coin tracking configuration", self._sync_star_coin_tracking(ctx)
            )

        if not self._native_block_configuration_ready or slow_due:
            configuration_ready = await self._run_watcher_operation(
                "native Blocksanity configuration",
                self._sync_native_block_configuration(ctx),
            )
            if configuration_ready is False:
                self._native_block_configuration_ready = False
                return
            if configuration_ready is True:
                self._native_block_configuration_ready = True
            elif not self._native_block_configuration_ready:
                return

        level_data = await self._run_watcher_operation(
            "level data read", self._read_level_data(ctx)
        )
        diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
        if level_data is None:
            if diagnostics is not None:
                diagnostics.game_status("Read unavailable")
            return
        if not self._is_game_data_ready(level_data):
            if diagnostics is not None:
                diagnostics.game_status("Not ready")
            if not self._last_not_ready_logged:
                header_values = tuple(
                    level_data[offset] for offset in LEVEL_DATA_WORLD_HEADER_OFFSETS
                )
                logger.info(
                    "NSMBDS game data is not ready; item writes are deferred "
                    "(world headers: %s).",
                    " ".join(f"{value:02X}" for value in header_values),
                )
                self._last_not_ready_logged = True
            return
        if diagnostics is not None:
            diagnostics.game_status("Ready")
        self._last_not_ready_logged = False
        self._game_data_header_values = tuple(
            level_data[offset] for offset in LEVEL_DATA_WORLD_HEADER_OFFSETS
        )

        # Fast path: gameplay-affecting deliveries and transient mailboxes must
        # remain responsive even when maintenance work is deferred.
        await self._run_watcher_operation("item application", self._apply_pending_items(ctx))
        await self._run_watcher_operation("Death Link synchronization", self._sync_death_link(ctx))
        mailbox_checks: list[tuple[str, int, int]] = []
        await self._run_watcher_operation(
            "Red Coin detection", self._detect_and_send_red_coin_challenge(ctx, mailbox_checks)
        )
        await self._run_watcher_operation(
            "Block check detection", self._detect_and_send_block_check(ctx, mailbox_checks)
        )
        await self._run_watcher_operation(
            "mailbox check submission", self._submit_pending_mailbox_checks(ctx, mailbox_checks)
        )
        await self._run_watcher_operation(
            "location detection", self._detect_and_send_locations(ctx, level_data)
        )
        for operation_name, operation in (
            ("Death Link", self._handle_death_link(ctx)),
            ("Timer Drain", self._apply_pending_timer_drains(ctx)),
            ("Starman Buff", self._apply_pending_starman_buffs(ctx)),
            ("positive filler bonuses", self._apply_pending_filler_bonuses(ctx)),
            ("Speed Traps", self._apply_pending_speed_traps(ctx)),
            ("in-game notifications", self._publish_next_ap_notification(ctx)),
            ("emulator feed", self._flush_emulator_feed(ctx)),
        ):
            await self._run_watcher_operation(operation_name, operation)

        if medium_due:
            for operation_name, operation in (
                ("Star Coin gate detection", self._detect_and_store_gate_purchases(ctx, level_data)),
                ("overworld state reconciliation", self._reconcile_overworld_state(ctx, level_data)),
                ("goal detection", self._send_goal_if_complete(ctx)),
            ):
                await self._run_watcher_operation(operation_name, operation)

        if self._gate_storage_sync_pending or self._gate_storage_write_pending or slow_due:
            await self._run_watcher_operation(
                "gate purchase storage sync", self._sync_gate_purchase_storage(ctx)
            )
        if self._bonus_mailbox_needs_reset or slow_due:
            await self._run_watcher_operation(
                "bonus mailbox initialization", self._initialize_bonus_mailbox(ctx)
            )
        if slow_due:
            await self._run_watcher_operation(
                "PopTracker world synchronization", self._sync_poptracker_world(ctx)
            )
            await self._run_watcher_operation(
                "Power-Up License sync", self._sync_powerup_licenses(ctx)
            )

    async def _read_level_data(self, ctx: "BizHawkClientContext") -> bytes | None:
        """Read the world-map block plus the native Mini-Castle flags."""
        from worlds._bizhawk import read

        try:
            result = await read(
                ctx.bizhawk_ctx,
                [
                    (ADDR_LEVEL_DATA_BASE, LEVEL_AND_SECRET_FLAG_READ_SIZE, MEMORY_DOMAIN),
                    (ADDR_AP_MINI_CASTLE_FLAGS_PERM, 4, MEMORY_DOMAIN),
                ],
            )
        except Exception as exc:
            if self._should_log_watcher_issue(f"level-read:{type(exc).__name__}"):
                logger.exception("Failed to read the NSMBDS level-data block.")
                diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
                if diagnostics is not None:
                    diagnostics.error("game data", exc)
            return None

        if (
            not result
            or len(result) != 2
            or len(result[0]) != LEVEL_AND_SECRET_FLAG_READ_SIZE
            or len(result[1]) != 4
        ):
            if self._should_log_watcher_issue("invalid-level-snapshot"):
                logger.warning("Received an invalid NSMBDS location-data snapshot from BizHawk.")
                diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
                if diagnostics is not None:
                    diagnostics.error("game data", "invalid snapshot")
            return None
        flags, sequence, source, destination = result[1]
        trace = bytes(result[1])
        if trace != getattr(self, "_mini_castle_trace", None):
            self._mini_castle_trace = trace
            if sequence or flags:
                logger.info(
                    "Native castle route: W%d -> W%d; secret flags=0x%02X; event=%d",
                    source + 1, destination + 1, flags, sequence,
                )
        location_data = result[0] + result[1][:1]
        if len(location_data) != LOCATION_DATA_SNAPSHOT_SIZE:
            if self._should_log_watcher_issue("incomplete-level-snapshot"):
                logger.warning("Received an incomplete NSMBDS location-data snapshot from BizHawk.")
                diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
                if diagnostics is not None:
                    diagnostics.error("game data", "incomplete snapshot")
            return None
        return location_data

    @staticmethod
    def _is_game_data_ready(level_data: bytes) -> bool:
        """Accept initial D-prefixed headers and progressed low state IDs."""
        header_values = tuple(
            level_data[offset] for offset in LEVEL_DATA_WORLD_HEADER_OFFSETS
        )
        return any(header_values) and all(
            value <= LEVEL_DATA_WORLD_HEADER_MAX_STATE
            or value & LEVEL_DATA_WORLD_HEADER_MASK == LEVEL_DATA_WORLD_HEADER_VALUE
            for value in header_values
        )

    def _game_data_guards(self) -> list[tuple[int, Sequence[int], str]]:
        """Guard RAM writes with the current verified world-header bytes."""
        values = self._game_data_header_values or tuple(
            LEVEL_DATA_WORLD_HEADER_VALUE for _offset in LEVEL_DATA_WORLD_HEADER_OFFSETS
        )
        return [
            (
                ADDR_LEVEL_DATA_BASE + offset,
                [value],
                MEMORY_DOMAIN,
            )
            for offset, value in zip(LEVEL_DATA_WORLD_HEADER_OFFSETS, values)
        ]

    async def _sync_powerup_licenses(self, ctx: "BizHawkClientContext") -> None:
        """Publish enabled and received Licenses for the native ROM hook."""
        mode = native_license_mode(ctx.slot_data)
        enabled_licenses = set(active_license_items(ctx.slot_data))
        received_ids = {item.item for item in ctx.items_received}
        license_bits = (
            (MINI_MUSHROOM_LICENSE, 0),
            (BLUE_SHELL_LICENSE, 1),
            (MEGA_MUSHROOM_LICENSE, 2),
            (TOUCHSCREEN_RESERVE_LICENSE, 3),
            (MUSHROOM_LICENSE, 4),
            (FIRE_FLOWER_LICENSE, 5),
        )
        mask = 0
        for item_name, bit in license_bits:
            # Disabled Licenses are marked satisfied so higher native tiers can
            # represent arbitrary combinations of the individual YAML toggles.
            if item_name not in enabled_licenses or ITEM_TABLE[item_name][0] in received_ids:
                mask |= 1 << bit

        from worlds._bizhawk import guarded_write

        await guarded_write(
            ctx.bizhawk_ctx,
            [
                (ADDR_AP_POWERUP_LICENSE_MODE, [mode], MEMORY_DOMAIN),
                (ADDR_AP_POWERUP_LICENSE_MASK, [mask], MEMORY_DOMAIN),
            ],
            self._game_data_guards(),
        )

    def on_package(self, ctx: "BizHawkClientContext", cmd: str, args: dict) -> None:
        """Synchronize server state without replaying items on a same-session reconnect."""
        if cmd == "PrintJSON":
            self._queue_core_item_send(ctx, args)
            return
        if cmd in ("Retrieved", "SetReply"):
            if cmd == "Retrieved" and self._awaiting_item_history:
                # Core requests this key on Connected. Its reply follows the
                # connection's optional ReceivedItems packet on the same socket.
                # No history before this reply means the room has ZERO items;
                # the next index-0 delivery is new, not a history baseline.
                hints_key = f"_read_hints_{getattr(ctx, 'team', 0)}_{ctx.slot}"
                if hints_key in args.get("keys", {}):
                    self._awaiting_item_history = False
                    self._items_received_index = 0
                    self._pending_item_transaction = None
                    self._deferred_item_ids.clear()
                    self._next_powerup_id = None
                    self._item_cursor_loaded = True
                    self._item_cursor_needs_initial_sync = False
                    self._persist_item_cursor()
                    logger.info("Synchronized empty server item history; waiting for new items.")
            self._handle_gate_storage_packet(cmd, args)
            return
        if cmd == "Bounced" and "DeathLink" in args.get("tags", ()):
            source = args.get("data", {}).get("source")
            my_name = ctx.player_names.get(ctx.slot) if hasattr(ctx, "player_names") and ctx.slot in getattr(ctx, "player_names", {}) else getattr(ctx, "auth", None)
            if source and my_name and source == my_name: #Ignore own bounced Death Link
                return
            self._queue_incoming_death_link(ctx, source)
            return
        if cmd == "ReceivedItems":
            diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
            if diagnostics is not None:
                start = int(args.get("index", 0))
                for offset, item in enumerate(args.get("items", ())):
                    index = start + offset
                    if diagnostics.last_received_index is None or index > diagnostics.last_received_index:
                        diagnostics.last_received_index = index
                        diagnostics.counters["items_received"] += 1
                        diagnostics.event("ITEM", "received", f"index={index}")
                        sync_logger.debug("Item received index=%d item=%s", index, item.item)
                    else:
                        sync_logger.debug("Ignoring already observed item index=%d", index)
            self._awaiting_item_history = False
            if self._item_cursor_needs_initial_sync:
                # CommonClient has already appended this packet before calling
                # the game handler. With no saved cursor, the first packet is
                # server history and must not replay consumables.
                packet_end = int(args.get("index", 0)) + len(args.get("items", ()))
                self._items_received_index = max(self._items_received_index, packet_end)
                self._item_cursor_needs_initial_sync = False
                self._item_cursor_loaded = True
                self._persist_item_cursor()
                logger.info(
                    "Initialized the NSMBDS item cursor at %d received item(s); "
                    "historical filler and traps will not replay.",
                    self._items_received_index,
                )
            elif int(args.get("index", 0)) == 0:
                packet_end = len(args.get("items", ()))
                pending_transaction = self._pending_item_transaction
                if pending_transaction is not None and pending_transaction["owner"] == "network" and (
                    self._items_received_index >= packet_end
                    or ctx.items_received[self._items_received_index].item != pending_transaction["item_id"]
                ):
                    self._pending_item_transaction = None
                # ReceivedItems index 0 is the authoritative history boundary.
                # Only this packet may shorten the emulator-feed cursor. The
                # transport clears ctx.items_received briefly during every
                # reconnect, which is not itself a history rollback.
                self._emulator_feed_received_index = min(
                    self._emulator_feed_received_index,
                    packet_end,
                )
                if self._items_received_index > packet_end:
                    stale_deferred_count = len(self._deferred_item_ids)
                    self._items_received_index = packet_end
                    self._pending_item_transaction = None
                    # A shorter authoritative history means the room was
                    # rolled back or replaced. Deferred consumables from the
                    # discarded tail no longer belong to this server state.
                    self._deferred_item_ids.clear()
                    self._next_powerup_id = None
                    self._persist_item_cursor()
                    logger.info(
                        "Rebased the NSMBDS item cursor to %d and discarded %d "
                        "stale deferred Power-Up(s) after a server-history rollback.",
                        packet_end,
                        stale_deferred_count,
                    )
            return
        if cmd != "Connected":
            return

        identity = (
            getattr(ctx, "server_seed_name", None) or getattr(ctx, "seed_name", None),
            args.get("team", getattr(ctx, "team", None)),
            args.get("slot", getattr(ctx, "slot", None)),
        )
        if identity[0] is not None:
            if (
                self._session_identity is not None
                and self._session_identity[0] is not None
                and identity != self._session_identity
            ):
                self._reset_session_state()
                diagnostics = getattr(ctx, "nsmbds_diagnostics", None)
                if diagnostics is not None:
                    diagnostics.reset_slot()
            self._session_identity = identity
        elif self._session_identity is None:
            self._session_identity = identity

        # Server DataStorage is authoritative. Never upload a local fallback
        # here: restarting a room with the same seed must not resurrect gate
        # purchases from an older test run.
        self._gate_path_open_states.clear()
        self._gate_purchase_mask = 0
        self._gate_purchase_spent_floor = 0
        self._gate_storage_sync_pending = True
        self._gate_storage_write_pending = False

        if not self._item_cursor_loaded:
            restored_cursor = self._load_item_cursor()
            if restored_cursor is not None:
                self._items_received_index = restored_cursor
                self._item_cursor_loaded = True
                self._item_cursor_needs_initial_sync = False
                # Rewrite the record after loading so any sanitized legacy
                # deferred queue is also removed from persistent storage.
                self._persist_item_cursor()
                logger.info("Restored the NSMBDS item cursor at %d.", restored_cursor)
            elif ctx.items_received:
                self._items_received_index = len(ctx.items_received)
                self._item_cursor_loaded = True
                self._persist_item_cursor()
            else:
                self._item_cursor_needs_initial_sync = True

        self._awaiting_item_history = True

        checked_locations = set(args.get("checked_locations", ()))
        checked_locations.update(getattr(ctx, "checked_locations", ()))
        missing_locations = args.get("missing_locations")
        if missing_locations is None:
            missing_locations = getattr(ctx, "missing_locations", None)
        if missing_locations is not None:
            self._active_locations = checked_locations | set(missing_locations)
            self._active_location_set_known = True
        else:
            self._active_locations.clear()
            self._active_location_set_known = False
        self._sent_locations = checked_locations
        self._observed_locations.update(checked_locations)
        logger.info(
            "Synchronized AP location state: %d checked, %d active.",
            len(checked_locations),
            len(self._active_locations) if self._active_location_set_known else -1,
        )

    def _reset_session_state(self) -> None:
        """Clear local progress only after connecting to a different AP session."""
        self._logged_unmatched_block_events.clear()
        self._observed_locations.clear()
        self._pending_emulator_feed.clear()
        self._emulator_feed_received_index = 0
        self._emulator_feed_server_announced = False
        self._emulator_feed_config_sent = None
        self._star_coin_tracking_mode_sent = None
        self._sent_locations.clear()
        self._active_locations.clear()
        self._active_location_set_known = False
        self._items_received_index = 0
        self._pending_item_transaction = None
        self._item_cursor_loaded = False
        self._item_cursor_needs_initial_sync = False
        self._deferred_item_ids.clear()
        self._next_powerup_id = None
        self._awaiting_item_history = False
        self._goal_sent = False
        self._death_link_enabled = None
        self._pending_death_link = False
        self._pending_death_link_effect = None
        self._death_link_cooldown_until = 0.0
        self._death_link_amnesty_count = 0
        self._suppress_next_local_death = False
        self._last_lives = None
        self._last_timer = None
        self._in_level_grace_polls = 0
        self._return_to_map_pending = False
        self._pending_timer_drains = 0
        self._pending_starman_buffs = 0
        self._pending_time_capsules = 0
        self._pending_starman_lites = 0
        self._pending_care_packages = 0
        self._pending_trap_shields = 0
        self._pending_life_insurance = 0
        self._pending_ap_notifications.clear()
        self._last_insured_death_sequence = None
        self._last_return_to_map_death_sequence = None
        self._bonus_mailbox_needs_reset = True
        self._pending_hyper_speed_traps = 0
        self._pending_slow_speed_traps = 0
        self._pending_walljump_lock_traps = 0
        self._pending_no_jump_traps = 0
        self._pending_reverse_controls_traps = 0
        self._pending_no_sprint_traps = 0
        self._pending_button_roulette_traps = 0
        self._pending_ice_shoes_traps = 0
        self._pending_heavy_mario_traps = 0
        self._pending_auto_run_traps = 0
        self._pending_sticky_buttons_traps = 0
        self._pending_camera_drift_traps = 0
        self._pending_screen_flip_traps = 0
        self._pending_camera_sway_traps = 0
        self._pending_boo_curse_traps = 0
        self._pending_im_stuck_traps = 0
        self._pending_screen_tint_traps = 0
        self._pending_retro_filter_traps = 0
        self._pending_spotlight_traps = 0
        self._pending_ground_clap_traps = 0
        self._pending_head_bonk_traps = 0
        self._pending_crazy_pixels_traps = 0
        self._pending_no_turnaround_traps = 0
        self._pending_coin_tax_notices = 0
        self._pending_timer_drain_notices = 0
        self._pending_coin_thief_notices = 0
        self._pending_powerup_pickpocket_notices = 0
        self._pending_bonk_traps = 0
        self._held_powerup_log_key = None
        self._last_not_ready_logged = False
        self._game_data_header_values = None
        self._gate_path_open_states.clear()
        self._gate_purchase_mask = 0
        self._gate_purchase_spent_floor = 0
        self._gate_storage_sync_pending = False
        self._gate_storage_write_pending = False
        self._last_published_poptracker_view = None
        self._watcher_tick = 0
        self._native_block_configuration_ready = False


def restrict_bizhawk_handlers_to_nsmbds() -> None:
    """Keep this dedicated client process from selecting another NDS game."""
    from worlds._bizhawk.client import AutoBizHawkClientRegister
    global _dedicated_client_mode

    nsmbds_handlers: dict[tuple[str, ...], dict[str, BizHawkClient]] = {}
    for systems, handlers in AutoBizHawkClientRegister.game_handlers.items():
        matching_handlers = {
            game: handler
            for game, handler in handlers.items()
            if isinstance(handler, NSMBDSClient)
        }
        if matching_handlers:
            nsmbds_handlers[systems] = matching_handlers

    if not nsmbds_handlers:
        raise RuntimeError("The NSMBDS BizHawk handler was not registered.")

    AutoBizHawkClientRegister.game_handlers = nsmbds_handlers
    _dedicated_client_mode = True
    logger.info("Dedicated NSMBDS client restricted BizHawk detection to the NSMBDS handler.")


def _make_tracker_gui_after_patching(_ctx):
    """Import Kivy only after a startup patch operation has finished."""
    # Core's kvui module must configure Kivy before any direct Kivy import.
    import kvui

    from .ui import install_kivy_hover_density_guard

    install_kivy_hover_density_guard()

    from .ui.tracker.view import make_tracker_gui

    return make_tracker_gui(_ctx)


def install_patch_startup_guard(bizhawk_context, configure_launch_from_args) -> None:
    """Stop startup after patch cancellation/failure and publish only valid output paths."""
    original_patch = bizhawk_context._patch_and_run_game
    if getattr(original_patch, "_nsmbds_startup_guard", False):
        return

    def patch_and_prepare_client(patch_file: str):
        metadata = original_patch(patch_file)
        if not metadata:
            raise SystemExit(1)
        configure_launch_from_args((patch_file,))
        return metadata

    patch_and_prepare_client._nsmbds_startup_guard = True
    bizhawk_context._patch_and_run_game = patch_and_prepare_client


def main(*args: str) -> None:
    """Launch the NSMBDS BizHawk client GUI executable."""
    from worlds._bizhawk import context as bizhawk_context
    from MultiServer import mark_raw
    from .launcher import configure_launch_from_args
    from .diagnostics import DiagnosticState, build_diagnostic_snapshot, format_full, format_short, parse_diagnostic_mode
    from .transport import NSMBDSBizHawkContext

    class NSMBDSCommandProcessor(bizhawk_context.BizHawkClientCommandProcessor):
        @mark_raw
        def _cmd_nsmbds_debug(self, mode: str = "") -> bool:
            """Toggle detailed NSMBDS logging: /nsmbds_debug [on|off]"""
            mode = mode.strip().lower()
            if mode not in {"", "on", "off"}:
                self.output("Usage: /nsmbds_debug [on|off]")
                return False
            if mode:
                logger.setLevel(logging.DEBUG if mode == "on" else logging.INFO)
                if mode == "on" and isinstance(self.ctx.client_handler, NSMBDSClient):
                    self.ctx.client_handler._logged_unmatched_block_events = set()
                logger.info("NSMBDS debug logging %s.", "enabled" if mode == "on" else "disabled")
            self.output("NSMBDS debug logging: " + ("on" if logger.isEnabledFor(logging.DEBUG) else "off"))
            return True

        @mark_raw
        def _cmd_nsmbds_diag(self, mode: str = "") -> bool:
            """Show NSMBDS support diagnostics: /nsmbds_diag [short|full]"""
            mode = parse_diagnostic_mode(mode)
            if mode is None:
                self.output("Usage: /nsmbds_diag [short|full]")
                return False
            snapshot = build_diagnostic_snapshot(self.ctx)
            logger.getChild("Diag").debug("Generated %s diagnostic snapshot", mode)
            self.output(format_full(snapshot) if mode == "full" else format_short(snapshot))
            return True

    class NSMBDSContext(bizhawk_context.BizHawkClientContext):
        command_processor = NSMBDSCommandProcessor

        def __init__(self, server_address, password):
            super().__init__(server_address, password)
            self.bizhawk_ctx = NSMBDSBizHawkContext()
            self.nsmbds_diagnostics = DiagnosticState()
            logger.info("NSMBDS client started; version %s; session %s.",
                        DISPLAY_VERSION, self.nsmbds_diagnostics.session_id)
            self.nsmbds_diagnostics.event("CLIENT", "started")

        def on_package(self, cmd, args):
            if cmd == "Connected":
                history = self.nsmbds_diagnostics.network
                if history.change(True):
                    network_logger.info("%s to Archipelago.", "Reconnected" if history.reconnect_count else "Connected")
                    self.nsmbds_diagnostics.event("NETWORK", "connected")
            super().on_package(cmd, args)

        async def disconnect(self, allow_autoreconnect=False):
            await super().disconnect(allow_autoreconnect)
            self.observe_network()

        def observe_network(self):
            server = getattr(self, "server", None)
            socket = getattr(server, "socket", None)
            connected = socket is not None and not getattr(socket, "closed", True)
            history = self.nsmbds_diagnostics.network
            if history.change(connected) and not connected:
                network_logger.info("Archipelago connection lost.")
                self.nsmbds_diagnostics.event("NETWORK", "disconnected")

        async def observe_bridge_handshake(self, script_version: int):
            """Cache connector metadata once per connection, never during diagnostics."""
            from worlds._bizhawk import send_requests

            diagnostics = self.nsmbds_diagnostics
            diagnostics.connector_script_version = script_version
            diagnostics.bizhawk_version = None
            diagnostics.lua_runtime_version = None
            try:
                replies = await send_requests(self.bizhawk_ctx, [{"type": "NSMBDS_DIAGNOSTICS"}])
            except Exception:
                bridge_logger.debug("BizHawk connector does not provide version metadata.", exc_info=True)
                return
            if len(replies) != 1 or replies[0].get("type") != "NSMBDS_DIAGNOSTICS_RESPONSE":
                return
            reply = replies[0]
            version = re.search(r"\d+\.\d+(?:\.\d+)?", str(reply.get("bizhawk_version", "")))
            if version:
                diagnostics.bizhawk_version = version.group(0)
            runtime = str(reply.get("runtime_version") or "")
            if re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?", runtime):
                diagnostics.lua_runtime_version = runtime

        def observe_bridge(self, state: str, reason: str | None = None, error_type: str | None = None):
            diagnostics = self.nsmbds_diagnostics
            previous = diagnostics.bridge_state
            if previous == state:
                return
            diagnostics.bridge_state = state
            if state != "READY":
                diagnostics.game_data_status = "Not read"
                diagnostics.last_ready_at = None
            bridge_logger.debug("%s -> %s", previous, state)
            diagnostics.event("BRIDGE", state.lower())
            if state == "ERROR":
                diagnostics.error("bridge", error_type or "RequestFailedError")
            history = diagnostics.bridge
            connected = state == "READY"
            safe_reason = reason if reason in {"Connection closed", "Connection timed out", "Connection reset"} else None
            if history.change(connected, safe_reason):
                if connected:
                    bridge_logger.info("BizHawk %s.", "reconnected" if history.reconnect_count else "connected")
                else:
                    bridge_logger.info("BizHawk connection lost%s.", f": {safe_reason}" if safe_reason else "")

    from ..version import DISPLAY_VERSION

    # Do not publish the expected output path until patching has succeeded.
    configure_launch_from_args(())
    restrict_bizhawk_handlers_to_nsmbds()
    install_patch_startup_guard(bizhawk_context, configure_launch_from_args)

    # This subprocess is dedicated to NSMBDS, so replacing the generic context
    # factory here cannot affect other BizHawk clients in the launcher process.
    NSMBDSContext.make_gui = _make_tracker_gui_after_patching
    bizhawk_context.BizHawkClientContext = NSMBDSContext

    # The core launcher would otherwise start BizHawk with only Archipelago's
    # generic connector. NSMBDS needs its bootstrap and side-loading runtime, so
    # its own launch panel handles this after the normal core patch step.
    async def defer_game_launch_to_nsmbds_panel(_rom: str) -> None:
        return None

    bizhawk_context._run_game = defer_game_launch_to_nsmbds_panel
    bizhawk_context.launch(*args)


if __name__ == "__main__":
    main()
