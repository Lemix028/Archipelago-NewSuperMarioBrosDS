"""BizHawk client facade for New Super Mario Bros. DS."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import deque
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
    ADDR_AP_POWERUP_LICENSE_MASK,
    ADDR_AP_POWERUP_LICENSE_MODE,
    ADDR_LEVEL_DATA_BASE,
    LEVEL_AND_SECRET_FLAG_READ_SIZE,
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
_dedicated_client_mode = False


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
        self._sent_locations: set[int] = set()
        self._active_locations: set[int] = set()
        self._active_location_set_known = False
        self._items_received_index = 0
        self._item_cursor_loaded = False
        self._item_cursor_needs_initial_sync = False
        self._deferred_item_ids: list[int] = []
        self._goal_sent = False
        self._session_identity: tuple[object, ...] | None = None
        self._last_not_ready_logged = False
        self._game_data_header_values: tuple[int, ...] | None = None
        self._death_link_enabled: bool | None = None
        self._pending_death_link = False
        self._last_lives: int | None = None
        self._last_timer: int | None = None
        self._in_level_grace_polls = 0
        self._return_to_map_pending = False
        self._suppress_local_death_polls = 0
        self._pending_timer_drains = 0
        self._pending_starman_buffs = 0
        self._pending_time_capsules = 0
        self._pending_starman_lites = 0
        self._pending_care_packages = 0
        self._pending_trap_shields = 0
        self._pending_life_insurance = 0
        self._pending_ap_notifications: list[tuple[int, int]] = []
        self._last_insured_death_sequence: int | None = None
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
        return True
    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        """Poll verified game data, submit checks, and apply pending features."""
        server_connected = (
            ctx.server is not None
            and not ctx.server.socket.closed
            and ctx.slot is not None
            and ctx.slot_data is not None
        )

        try:
            await self._sync_emulator_feed(ctx, server_connected=server_connected)
        except Exception:
            logger.exception("NSMBDS emulator feed synchronization failed; retrying next tick.")

        if not server_connected:
            self._last_published_poptracker_view = None
            return

        level_data = await self._read_level_data(ctx)
        if level_data is None:
            return
        if not self._is_game_data_ready(level_data):
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
        self._last_not_ready_logged = False
        self._game_data_header_values = tuple(
            level_data[offset] for offset in LEVEL_DATA_WORLD_HEADER_OFFSETS
        )

        try:
            await self._sync_death_link(ctx)
        except Exception:
            logger.exception("NSMBDS Death Link synchronization failed; the watcher will retry next tick.")

        for operation_name, operation in (
            ("location detection", self._detect_and_send_locations(ctx, level_data)),
            ("gate purchase storage sync", self._sync_gate_purchase_storage(ctx)),
            ("Star Coin gate detection", self._detect_and_store_gate_purchases(ctx, level_data)),
            ("Red Coin detection", self._detect_and_send_red_coin_challenge(ctx)),
            ("Block check detection", self._detect_and_send_block_check(ctx)),
            ("overworld state reconciliation", self._reconcile_overworld_state(ctx, level_data)),
            ("PopTracker world synchronization", self._sync_poptracker_world(ctx)),
            ("Power-Up License sync", self._sync_powerup_licenses(ctx)),
            ("bonus mailbox initialization", self._initialize_bonus_mailbox(ctx)),
            ("item application", self._apply_pending_items(ctx)),
            ("Death Link", self._handle_death_link(ctx)),
            ("Timer Drain", self._apply_pending_timer_drains(ctx)),
            ("Starman Buff", self._apply_pending_starman_buffs(ctx)),
            ("positive filler bonuses", self._apply_pending_filler_bonuses(ctx)),
            ("Speed Traps", self._apply_pending_speed_traps(ctx)),
            ("in-game notifications", self._publish_next_ap_notification(ctx)),
            ("emulator feed", self._flush_emulator_feed(ctx)),
            ("goal detection", self._send_goal_if_complete(ctx)),
        ):
            try:
                await operation
            except Exception:
                logger.exception("NSMBDS %s failed; the watcher will retry next tick.", operation_name)

    async def _read_level_data(self, ctx: "BizHawkClientContext") -> bytes | None:
        """Read the full location block and report connector failures."""
        from worlds._bizhawk import read

        try:
            result = await read(
                ctx.bizhawk_ctx,
                [(ADDR_LEVEL_DATA_BASE, LEVEL_AND_SECRET_FLAG_READ_SIZE, MEMORY_DOMAIN)],
            )
        except Exception:
            logger.exception("Failed to read the NSMBDS level-data block.")
            return None

        if not result or len(result[0]) != LEVEL_AND_SECRET_FLAG_READ_SIZE:
            logger.warning("Received an invalid NSMBDS level-data block from BizHawk.")
            return None
        return result[0]

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
            self._handle_gate_storage_packet(cmd, args)
            return
        if cmd == "Bounced" and "DeathLink" in args.get("tags", ()):
            source = args.get("data", {}).get("source")
            my_name = ctx.player_names.get(ctx.slot) if hasattr(ctx, "player_names") and ctx.slot in getattr(ctx, "player_names", {}) else getattr(ctx, "auth", None)
            if source and my_name and source == my_name: #Ignore own bounced Death Link
                return
            if ctx.slot_data and ctx.slot_data.get("death_link", False):
                self._pending_death_link = True
                logger.info("Queued incoming Death Link from %s until the level timer is active.", source)
            return
        if cmd == "ReceivedItems":
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
                    # A shorter authoritative history means the room was
                    # rolled back or replaced. Deferred consumables from the
                    # discarded tail no longer belong to this server state.
                    self._deferred_item_ids.clear()
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
        self._sent_locations.update(checked_locations)
        self._observed_locations.update(checked_locations)
        logger.info(
            "Synchronized AP location state: %d checked, %d active.",
            len(checked_locations),
            len(self._active_locations) if self._active_location_set_known else -1,
        )

    def _reset_session_state(self) -> None:
        """Clear local progress only after connecting to a different AP session."""
        self._observed_locations.clear()
        self._pending_emulator_feed.clear()
        self._emulator_feed_received_index = 0
        self._emulator_feed_server_announced = False
        self._emulator_feed_config_sent = None
        self._sent_locations.clear()
        self._active_locations.clear()
        self._active_location_set_known = False
        self._items_received_index = 0
        self._item_cursor_loaded = False
        self._item_cursor_needs_initial_sync = False
        self._deferred_item_ids.clear()
        self._goal_sent = False
        self._death_link_enabled = None
        self._pending_death_link = False
        self._last_lives = None
        self._last_timer = None
        self._in_level_grace_polls = 0
        self._return_to_map_pending = False
        self._suppress_local_death_polls = 0
        self._pending_timer_drains = 0
        self._pending_starman_buffs = 0
        self._pending_time_capsules = 0
        self._pending_starman_lites = 0
        self._pending_care_packages = 0
        self._pending_trap_shields = 0
        self._pending_life_insurance = 0
        self._pending_ap_notifications.clear()
        self._last_insured_death_sequence = None
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
    from .launcher import configure_launch_from_args

    # Do not publish the expected output path until patching has succeeded.
    configure_launch_from_args(())
    restrict_bizhawk_handlers_to_nsmbds()
    install_patch_startup_guard(bizhawk_context, configure_launch_from_args)

    # This subprocess is dedicated to NSMBDS, so replacing the generic context
    # factory here cannot affect other BizHawk clients in the launcher process.
    bizhawk_context.BizHawkClientContext.make_gui = _make_tracker_gui_after_patching

    # The core launcher would otherwise start BizHawk with only Archipelago's
    # generic connector. NSMBDS needs its bootstrap and side-loading runtime, so
    # its own launch panel handles this after the normal core patch step.
    async def defer_game_launch_to_nsmbds_panel(_rom: str) -> None:
        return None

    bizhawk_context._run_game = defer_game_launch_to_nsmbds_panel
    bizhawk_context.launch(*args)


if __name__ == "__main__":
    main()
