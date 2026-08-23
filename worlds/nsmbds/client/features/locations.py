"""Location detection behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
import hashlib
from typing import TYPE_CHECKING

from ...locations import (
    BLOCKSANITY_LOCATION_IDS,
    BOSS_LOCATION_COMPLETION_SOURCES,
    LOCATION_RAM_MAP,
    LOCATION_TABLE,
    ONE_UP_BLOCK_LOCATION_IDS,
    RED_COIN_LOCATION_IDS,
    SECRET_EXIT_RAM_REQUIREMENTS,
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES,
)
from ...items import ITEM_TABLE
from ...data.ram_addresses import (
    ADDR_LEVEL_DATA_BASE,
)
from ...data.star_coin_gates import STAR_COIN_GATES

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

STAR_COIN_LOCATION_IDS = frozenset(
    location_id for name, location_id in LOCATION_TABLE.items() if "Star Coin" in name
)

GATE_PURCHASE_MASK_BITS = (1 << len(STAR_COIN_GATES)) - 1
GATE_PURCHASE_SPENT_SHIFT = len(STAR_COIN_GATES)
GATE_PURCHASE_COST = 5


class LocationTrackingMixin:
    """Read RAM-backed locations and submit newly completed checks."""

    def _is_location_active(
        self, ctx: "BizHawkClientContext", location_name: str, location_id: int
    ) -> bool:
        """Return whether a local location is enabled in the current seed."""
        if self._active_location_set_known:
            return location_id in self._active_locations
        if (
            location_name in WORLD_6_2_BONUS_AREA_LOCATION_NAMES
            and ctx.slot_data
            and ctx.slot_data.get("world_6_2_bonus_area", 1) == 0
        ):
            return False
        if location_id in RED_COIN_LOCATION_IDS:
            return bool(ctx.slot_data and ctx.slot_data.get("red_coin_checks", False))
        if location_id in ONE_UP_BLOCK_LOCATION_IDS:
            return bool(ctx.slot_data and ctx.slot_data.get("one_up_block_checks", True))
        if location_id in BLOCKSANITY_LOCATION_IDS:
            return bool(ctx.slot_data and ctx.slot_data.get("blocksanity", False))
        if "Star Coin" in location_name:
            return bool(ctx.slot_data and ctx.slot_data.get("star_coin_checks", True))
        return True

    @staticmethod
    def _is_location_completed(location_name: str, game_data: bytes) -> bool:
        """Return whether a location's RAM condition is currently met."""
        completion_sources = BOSS_LOCATION_COMPLETION_SOURCES.get(location_name)
        if completion_sources is not None:
            return any(
                LocationTrackingMixin._is_location_completed(source_name, game_data)
                for source_name in completion_sources
            )

        secret_requirements = SECRET_EXIT_RAM_REQUIREMENTS.get(location_name)
        if secret_requirements is not None:
            return all(
                (game_data[offset] & bit_mask) == bit_mask
                for offset, bit_mask in secret_requirements
            )

        byte_offset, bit_mask = LOCATION_RAM_MAP[location_name]
        flag_byte = game_data[byte_offset]
        return bool(flag_byte & 0x80 and (flag_byte & bit_mask) == bit_mask)

    async def _detect_and_send_locations(
        self, ctx: "BizHawkClientContext", level_data: bytes
    ) -> None:
        """Observe completed local checks and submit only active, unsent locations."""
        new_checks: list[int] = []
        for location_name, location_id in LOCATION_TABLE.items():
            # Red Coin Challenges are transient events supplied by the Lua hook.
            if (
                location_name not in LOCATION_RAM_MAP
                and location_name not in BOSS_LOCATION_COMPLETION_SOURCES
            ):
                continue
            if not self._is_location_completed(location_name, level_data):
                continue

            self._observed_locations.add(location_id)
            if (
                location_id not in self._sent_locations
                and self._is_location_active(ctx, location_name, location_id)
            ):
                new_checks.append(location_id)

        if not new_checks:
            return

        try:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": new_checks}])
        except Exception:
            logger.exception("Failed to submit %d NSMBDS location check(s).", len(new_checks))
            return
        self._sent_locations.update(new_checks)

    def _gate_purchase_storage_key(self) -> str | None:
        identity = getattr(self, "_session_identity", None)
        if not identity or identity[0] is None or identity[2] is None:
            return None
        digest = hashlib.sha256(repr(tuple(identity)).encode("utf-8")).hexdigest()
        return f"nsmbds_gate_purchases_{digest}"

    def _gate_purchase_payload(self) -> int:
        """Encode gate bits plus a monotone unary spent-coin floor."""
        spent_count = max(0, self._gate_purchase_spent_floor // GATE_PURCHASE_COST)
        spent_bits = (1 << spent_count) - 1 if spent_count else 0
        return (
            (self._gate_purchase_mask & GATE_PURCHASE_MASK_BITS)
            | (spent_bits << GATE_PURCHASE_SPENT_SHIFT)
        )

    def _merge_gate_purchase_payload(self, value: object) -> None:
        """Merge an OR-safe purchase payload from local or AP storage."""
        try:
            payload = max(0, int(value))
        except (TypeError, ValueError):
            return
        self._gate_purchase_mask |= payload & GATE_PURCHASE_MASK_BITS
        spent_bits = payload >> GATE_PURCHASE_SPENT_SHIFT
        self._gate_purchase_spent_floor = max(
            self._gate_purchase_spent_floor,
            spent_bits.bit_count() * GATE_PURCHASE_COST,
        )

    def _handle_gate_storage_packet(self, cmd: str, args: dict) -> bool:
        """Merge authoritative server DataStorage replies into this session."""
        key = self._gate_purchase_storage_key()
        if key is None:
            return False
        value = None
        if cmd == "Retrieved":
            value = args.get("keys", {}).get(key)
        elif cmd == "SetReply" and args.get("key") == key:
            value = args.get("value")
        if value is None:
            return False
        try:
            self._merge_gate_purchase_payload(value)
        except (TypeError, ValueError):
            logger.warning("Ignored invalid NSMBDS gate DataStorage value %r.", value)
            return True
        return True

    async def _sync_gate_purchase_storage(self, ctx: "BizHawkClientContext") -> None:
        """Subscribe to and merge the invisible server-side purchase mask."""
        if not self._gate_storage_sync_pending and not self._gate_storage_write_pending:
            return
        key = self._gate_purchase_storage_key()
        if key is None:
            return
        messages: list[dict] = []
        if self._gate_storage_sync_pending:
            messages.extend([
                {"cmd": "SetNotify", "keys": [key]},
                {"cmd": "Get", "keys": [key]},
            ])
        if self._gate_storage_write_pending:
            messages.append({
                "cmd": "Set",
                "key": key,
                "default": 0,
                "want_reply": True,
                "operations": [{"operation": "or", "value": self._gate_purchase_payload()}],
            })
        await ctx.send_msgs(messages)
        self._gate_storage_sync_pending = False
        self._gate_storage_write_pending = False

    async def _detect_and_store_gate_purchases(
        self, ctx: "BizHawkClientContext", level_data: bytes
    ) -> None:
        """Persist newly purchased signs without creating visible AP checks."""
        if not ctx.slot_data.get("star_coin_items", False):
            return

        current_states: dict[int, bool] = {}
        for gate_index, gate in enumerate(STAR_COIN_GATES):
            offset = gate.path_address - ADDR_LEVEL_DATA_BASE
            if 0 <= offset < len(level_data):
                path_value = level_data[offset]
                current_states[gate_index] = path_value & 0xC0 == 0xC0

        # Existing save files can already contain open paths. Treat the first
        # observation as a baseline instead of charging those paths by itself.
        if not self._gate_path_open_states:
            self._gate_path_open_states = current_states
            return

        detected_mask = 0
        for gate_index, _gate in enumerate(STAR_COIN_GATES):
            was_open = self._gate_path_open_states.get(gate_index, False)
            is_open = current_states.get(gate_index, was_open)
            if was_open or not is_open or self._gate_purchase_mask & (1 << gate_index):
                continue
            detected_mask |= 1 << gate_index

        if not detected_mask:
            self._gate_path_open_states = current_states
            return

        self._gate_purchase_mask |= detected_mask
        self._gate_purchase_spent_floor = max(
            self._gate_purchase_spent_floor,
            sum(
                gate.star_coin_cost
                for gate_index, gate in enumerate(STAR_COIN_GATES)
                if self._gate_purchase_mask & (1 << gate_index)
            ),
        )
        key = self._gate_purchase_storage_key()
        self._gate_storage_write_pending = key is not None
        try:
            if key is not None:
                await ctx.send_msgs([{
                    "cmd": "Set",
                    "key": key,
                    "default": 0,
                    "want_reply": True,
                    "operations": [{
                        "operation": "or",
                        "value": self._gate_purchase_payload(),
                    }],
                }])
                self._gate_storage_write_pending = False
        except Exception:
            self._gate_storage_write_pending = True
            logger.exception("Failed to store the Star Coin gate purchase mask.")
        self._gate_path_open_states = current_states
