"""Item receipt behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
import hashlib
from typing import TYPE_CHECKING

from ...items import (
    BASE_ID,
    INVENTORY_RAM_VALUES,
    ITEM_TABLE,
    KEY_ITEM_NAMES,
    TRAP_ITEM_NAMES,
    item_id_to_name,
)
from ...data.powerup_licenses import (
    BLUE_SHELL_LICENSE,
    FIRE_FLOWER_LICENSE,
    MEGA_MUSHROOM_LICENSE,
    MINI_MUSHROOM_LICENSE,
    MUSHROOM_LICENSE,
    TOUCHSCREEN_RESERVE_LICENSE,
    license_is_enabled,
    required_license_for_powerup,
)
from ...data.ram_addresses import (
    ADDR_COINS,
    ADDR_INVENTORY_ITEM,
    ADDR_LIVES,
    AP_NOTIFICATION_ITEM_RECEIVED,
    MEMORY_DOMAIN,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

LIFE_ITEMS = {
    "1-Up Mushroom": 1,
    "3-Up Moon": 3,
}

COIN_ITEMS = {
    "Coin Bundle": 50,
}

MAX_NEW_ITEMS_PER_POLL = 8
RECEIVED_NOTIFICATION_ITEM_IDS = frozenset(
    item_id
    for item_name, (item_id, classification) in ITEM_TABLE.items()
    if item_name != "Nothing"
    and (
        int(classification) & 0b0011
        or item_name in {"1-Up Mushroom", "3-Up Moon", "Coin Bundle"}
    )
)


class ItemHandlingMixin:
    """Apply received inventory, life, filler, and verified trap items."""

    async def _apply_pending_items(self, ctx: "BizHawkClientContext") -> None:
        """Apply pending items without letting one failed RAM write block the queue."""
        await self._retry_one_deferred_item(ctx)

        start_index = self._items_received_index
        pending_items = ctx.items_received[
            self._items_received_index:self._items_received_index + MAX_NEW_ITEMS_PER_POLL
        ]
        for network_item in pending_items:
            if network_item.item in RECEIVED_NOTIFICATION_ITEM_IDS:
                self._queue_ap_notification(
                    AP_NOTIFICATION_ITEM_RECEIVED,
                    network_item.item - BASE_ID,
                )
            missing_license = self._missing_powerup_license(ctx, network_item.item)
            if missing_license is not None:
                self._deferred_item_ids.append(network_item.item)
                self._log_held_powerup(network_item.item, missing_license)
                self._items_received_index += 1
                continue
            try:
                applied = await self._apply_item(ctx, network_item.item)
            except Exception:
                logger.exception("Failed to apply received item ID %s.", network_item.item)
                applied = False
            if not applied:
                # RAM can be temporarily unavailable during transitions. Keep this
                # item for a retry, but do not starve later filler or trap items.
                self._deferred_item_ids.append(network_item.item)
                logger.info(
                    "Deferred received item %s (ID %s) after a failed RAM write.",
                    item_id_to_name.get(network_item.item, "Unknown"),
                    network_item.item,
                )
            self._items_received_index += 1

        if self._items_received_index != start_index:
            self._persist_item_cursor()

    def _item_cursor_storage_key(self) -> str | None:
        """Return a stable, non-sensitive key for this seed/team/slot."""
        identity = getattr(self, "_session_identity", None)
        if not identity or identity[0] is None or identity[2] is None:
            return None
        digest = hashlib.sha256(repr(tuple(identity)).encode("utf-8")).hexdigest()
        return f"received_items_{digest}"

    def _load_item_cursor(self) -> int | None:
        """Load the last consumed network-item index from Archipelago storage."""
        key = self._item_cursor_storage_key()
        if key is None:
            return None
        try:
            import Utils
            value = Utils.persistent_load().get("nsmbds", {}).get(key)
            if isinstance(value, dict):
                cursor_value = value.get("cursor")
                cursor = max(0, int(cursor_value)) if cursor_value is not None else None
                deferred = value.get("deferred_powerups", ())
                inventory_item_ids = {
                    ITEM_TABLE[item_name][0] for item_name in INVENTORY_RAM_VALUES
                }
                restored_deferred = [
                    int(item_id) for item_id in deferred
                    if int(item_id) in inventory_item_ids
                ]
                # Every deferred item must originate from one already consumed
                # network entry. A queue larger than the cursor can only be a
                # stale/corrupt queue left by an earlier history rollback.
                if cursor is not None and len(restored_deferred) > cursor:
                    logger.warning(
                        "Discarded %d impossible deferred Power-Up(s) for item cursor %d.",
                        len(restored_deferred),
                        cursor,
                    )
                    restored_deferred.clear()
                self._deferred_item_ids = restored_deferred
                return cursor
            return max(0, int(value)) if value is not None else None
        except (ImportError, OSError, TypeError, ValueError):
            logger.debug("Could not load the persistent NSMBDS item cursor.", exc_info=True)
            return None

    def _persist_item_cursor(self) -> None:
        """Persist consumed items so emulator/client restarts cannot replay them."""
        key = self._item_cursor_storage_key()
        if key is None:
            return
        try:
            import Utils
            inventory_item_ids = {
                ITEM_TABLE[item_name][0] for item_name in INVENTORY_RAM_VALUES
            }
            Utils.persistent_store(
                "nsmbds",
                key,
                {
                    "cursor": int(self._items_received_index),
                    # Only unapplied reserve power-ups survive a restart.
                    # Filler and traps are intentionally never replayed.
                    "deferred_powerups": [
                        item_id for item_id in self._deferred_item_ids
                        if item_id in inventory_item_ids
                    ],
                },
            )
        except (ImportError, OSError, TypeError, ValueError):
            logger.debug("Could not persist the NSMBDS item cursor.", exc_info=True)

    async def _retry_one_deferred_item(self, ctx: "BizHawkClientContext") -> None:
        """Retry one queued item per poll so BizHawk cannot be flooded with RAM calls."""
        if not self._deferred_item_ids:
            return

        item_id = self._deferred_item_ids.pop(0)
        if self._missing_powerup_license(ctx, item_id) is not None:
            self._deferred_item_ids.append(item_id)
            return

        try:
            applied = await self._apply_item(ctx, item_id)
        except Exception:
            logger.exception("Failed to apply deferred received item ID %s.", item_id)
            applied = False
        if not applied:
            # Rotate failures to the back so every deferred item gets a chance.
            self._deferred_item_ids.append(item_id)
        self._persist_item_cursor()

    def _missing_powerup_license(self, ctx: "BizHawkClientContext", item_id: int) -> str | None:
        """Return the missing license that should defer an inventory power-up."""
        item_name = item_id_to_name.get(item_id)
        if item_name not in INVENTORY_RAM_VALUES:
            return None

        received_ids = {item.item for item in ctx.items_received}
        required_license = required_license_for_powerup(ctx.slot_data, item_name)
        if required_license and ITEM_TABLE[required_license][0] not in received_ids:
            return required_license
        if (
            license_is_enabled(ctx.slot_data, TOUCHSCREEN_RESERVE_LICENSE)
            and ITEM_TABLE[TOUCHSCREEN_RESERVE_LICENSE][0] not in received_ids
        ):
            return TOUCHSCREEN_RESERVE_LICENSE
        return None

    def _log_held_powerup(self, item_id: int, required_license: str) -> None:
        item_name = item_id_to_name[item_id]
        diagnostic = (item_name, required_license)
        if self._held_powerup_log_key != diagnostic:
            logger.info("Holding %s until %s is received.", item_name, required_license)
            self._held_powerup_log_key = diagnostic

    async def _apply_item(self, ctx: "BizHawkClientContext", item_id: int) -> bool:
        """Apply one received item and return whether it is safe to advance the cursor."""
        from worlds._bizhawk import guarded_read, guarded_write

        item_name = item_id_to_name.get(item_id)
        if item_name is None:
            logger.warning("Ignoring unknown NSMBDS item ID %s.", item_id)
            return True

        if item_name in INVENTORY_RAM_VALUES:
            missing_license = self._missing_powerup_license(ctx, item_id)
            if missing_license is not None:
                self._log_held_powerup(item_id, missing_license)
                return False
            inventory_result = await guarded_read(
                ctx.bizhawk_ctx,
                [(ADDR_INVENTORY_ITEM, 1, MEMORY_DOMAIN)],
                self._game_data_guards(),
            )
            if (
                inventory_result is None
                or len(inventory_result) != 1
                or len(inventory_result[0]) != 1
            ):
                return False
            current_inventory = inventory_result[0][0]
            if current_inventory != 0:
                diagnostic = (item_name, "occupied reserve slot")
                if self._held_powerup_log_key != diagnostic:
                    logger.info(
                        "Holding %s until the current reserve Power-Up is used.",
                        item_name,
                    )
                    self._held_powerup_log_key = diagnostic
                return False
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_INVENTORY_ITEM, [INVENTORY_RAM_VALUES[item_name]], MEMORY_DOMAIN)],
                [
                    *self._game_data_guards(),
                    (ADDR_INVENTORY_ITEM, [0], MEMORY_DOMAIN),
                ],
            )
            if applied:
                self._held_powerup_log_key = None
            return applied

        if item_name in LIFE_ITEMS:
            return await self._adjust_byte(ctx, ADDR_LIVES, LIFE_ITEMS[item_name], 99)

        if item_name in COIN_ITEMS:
            return await self._adjust_byte(ctx, ADDR_COINS, COIN_ITEMS[item_name], 99)

        if item_name in ("Nothing", "Star Coin"):
            # Star Coin currency is reconciled from the complete server item
            # history, not incremented through the consumable item cursor.
            return True

        if item_name == "Time Capsule":
            self._queue_time_capsule()
            return True

        if item_name == "Starman Lite":
            self._queue_starman_lite()
            return True

        if item_name == "Trap Shield":
            return await self._add_trap_shield(ctx)

        if item_name == "Small Care Package":
            self._queue_care_package()
            return True

        if item_name == "Life Insurance":
            return await self._add_life_insurance(ctx)

        if item_name in TRAP_ITEM_NAMES and self._pending_trap_shields:
            shielded = await self._consume_trap_shield(ctx, item_name)
            if shielded is None:
                return False
            if shielded:
                return True

        if item_name == "Coin Tax":
            return await self._apply_coin_tax(ctx)

        if item_name == "Time Drain":
            self._queue_timer_drain()
            return True

        if item_name == "Starman Buff":
            self._queue_starman_buff()
            return True

        if item_name == "Coin Thief":
            return await self._apply_coin_thief(ctx)

        if item_name == "Power-Up Pickpocket Trap":
            return await self._apply_powerup_pickpocket(ctx)

        if item_name == "Super Speed":
            self._queue_speed_trap(1.6)
            return True

        if item_name == "Slowness":
            self._queue_speed_trap(0.5)
            return True

        if item_name == "Slippery Gloves":
            self._queue_walljump_lock_trap()
            return True

        if item_name == "Ground Bound":
            self._queue_no_jump_trap()
            return True

        if item_name == "Hyper Confusion":
            self._queue_reverse_controls_trap()
            return True

        if item_name == "No Sprint":
            self._queue_no_sprint_trap()
            return True

        if item_name == "Button Swap":
            self._queue_button_roulette_trap()
            return True

        if item_name == "Ice Shoes":
            self._queue_ice_shoes_trap()
            return True

        if item_name == "Heavy Mario":
            self._queue_heavy_mario_trap()
            return True

        if item_name == "Can't Stop":
            self._queue_auto_run_trap()
            return True

        if item_name == "Sticky Buttons":
            self._queue_sticky_buttons_trap()
            return True

        if item_name == "Camera Drift":
            self._queue_camera_drift_trap()
            return True

        if item_name == "Screen Flip":
            self._queue_screen_flip_trap()
            return True

        if item_name == "Drunk Camera":
            self._queue_camera_sway_trap()
            return True

        if item_name == "Boo Curse":
            self._queue_boo_curse_trap()
            return True

        if item_name == "I'm Stuck":
            self._queue_im_stuck_trap()
            return True

        if item_name == "Screen Tint":
            self._queue_screen_tint_trap()
            return True

        if item_name == "Retro Filter":
            self._queue_retro_filter_trap()
            return True

        if item_name == "Spotlight":
            self._queue_spotlight_trap()
            return True

        if item_name == "Ground Clap":
            self._queue_ground_clap_trap()
            return True

        if item_name == "Head Bonk":
            self._queue_head_bonk_trap()
            return True

        if item_name == "Pixelation":
            self._queue_crazy_pixels_trap()
            return True

        if item_name == "No Turnaround Trap":
            self._queue_no_turnaround_trap()
            return True

        if item_name == "Bonk Trap":
            self._queue_bonk_trap()
            return True

        if item_name in KEY_ITEM_NAMES:
            return await self._apply_key_item(ctx, item_name)

        # Progression keys, licenses, and unhandled items advance the cursor safely.
        return True

    async def _apply_key_item(self, ctx: "BizHawkClientContext", key_name: str) -> bool:
        """Acknowledge a key; the central reconciler applies its full path state."""
        return True

    async def _adjust_byte(
        self, ctx: "BizHawkClientContext", address: int, delta: int, upper_bound: int
    ) -> bool:
        """Read, clamp, and guarded-write a one-byte game value."""
        from worlds._bizhawk import guarded_read, guarded_write

        current_result = await guarded_read(
            ctx.bizhawk_ctx,
            [(address, 1, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if current_result is None:
            return False
        new_value = max(0, min(upper_bound, current_result[0][0] + delta))
        return await guarded_write(
            ctx.bizhawk_ctx,
            [(address, [new_value], MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
