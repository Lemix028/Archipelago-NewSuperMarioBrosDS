"""Transient Red Coin Challenge detection through the Lua event mailbox."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ...locations import LOCATION_TABLE, resolve_red_coin_location_name
from ...data.ram_addresses import (
    ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE,
    ADDR_AP_RED_COIN_EVENT_AREA,
    ADDR_AP_RED_COIN_EVENT_COUNTER,
    ADDR_AP_RED_COIN_EVENT_LEVEL,
    ADDR_AP_RED_COIN_EVENT_PLAYER_X,
    ADDR_AP_RED_COIN_EVENT_SEQUENCE,
    ADDR_AP_RED_COIN_EVENT_TYPE,
    ADDR_AP_RED_COIN_EVENT_WORLD,
    AP_EVENT_TYPE_RED_COIN_COMPLETE,
    MEMORY_DOMAIN,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")


class RedCoinTrackingMixin:
    """Consume Lua-latched Red Coin completion events exactly once."""

    async def _detect_and_send_red_coin_challenge(self, ctx: "BizHawkClientContext") -> None:
        """Resolve one pending Lua event and acknowledge it after safe handling."""
        from worlds._bizhawk import guarded_write, read

        result = await read(
            ctx.bizhawk_ctx,
            [
                (ADDR_AP_RED_COIN_EVENT_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_TYPE, 1, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_WORLD, 4, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_LEVEL, 4, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_AREA, 4, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_PLAYER_X, 4, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_COUNTER, 1, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_RED_COIN_EVENT_SEQUENCE, 1, MEMORY_DOMAIN),
            ],
        )
        expected_sizes = (1, 1, 4, 4, 4, 4, 1, 1, 1)
        if len(result) != len(expected_sizes) or any(
            len(value) != size for value, size in zip(result, expected_sizes)
        ):
            logger.warning("Received an invalid Red Coin event mailbox read from BizHawk.")
            return

        (
            sequence,
            event_type,
            world_raw,
            level_raw,
            area_raw,
            player_x_raw,
            counter_raw,
            acknowledged,
            sequence_after,
        ) = result
        sequence_value = sequence[0]
        if sequence_value != sequence_after[0] or sequence_value == acknowledged[0]:
            return

        world = struct.unpack("<I", world_raw)[0]
        level = struct.unpack("<I", level_raw)[0]
        area = struct.unpack("<I", area_raw)[0]
        player_x = struct.unpack("<i", player_x_raw)[0]
        counter_index = counter_raw[0]
        if event_type[0] != AP_EVENT_TYPE_RED_COIN_COMPLETE:
            logger.warning("Discarded unknown AP Lua mailbox event type 0x%02X.", event_type[0])
            await self._acknowledge_red_coin_event(ctx, sequence_value, guarded_write)
            return

        location_name = resolve_red_coin_location_name(
            world, level, area, player_x, counter_index
        )
        if location_name is None:
            logger.warning(
                "Discarded Red Coin completion for unknown runtime course "
                "(world=%d, level=0x%X, area=%d, player_x=%d, counter=%d).",
                world,
                level,
                area,
                player_x,
                counter_index,
            )
            await self._acknowledge_red_coin_event(ctx, sequence_value, guarded_write)
            return

        location_id = LOCATION_TABLE[location_name]
        if location_id in self._sent_locations:
            logger.info("Ignored already checked Red Coin Challenge: %s.", location_name)
            await self._acknowledge_red_coin_event(ctx, sequence_value, guarded_write)
            return
        if not self._is_location_active(ctx, location_name, location_id):
            logger.warning(
                "Ignored Red Coin Challenge %r because it is not active in this seed. "
                "Generate a new seed with red_coin_checks enabled.",
                location_name,
            )
            await self._acknowledge_red_coin_event(ctx, sequence_value, guarded_write)
            return

        try:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": [location_id]}])
        except Exception:
            logger.exception("Failed to submit Red Coin Challenge %r; the Lua event remains pending.", location_name)
            return

        self._observed_locations.add(location_id)
        self._sent_locations.add(location_id)
        logger.debug("Submitted Red Coin Challenge: %s.", location_name)
        await self._acknowledge_red_coin_event(ctx, sequence_value, guarded_write)

    async def _acknowledge_red_coin_event(self, ctx: "BizHawkClientContext", sequence: int, guarded_write) -> None:
        """Acknowledge a mailbox event only if it is still the same sequence."""
        guards = [
            *self._game_data_guards(),
            (ADDR_AP_RED_COIN_EVENT_SEQUENCE, [sequence], MEMORY_DOMAIN),
        ]
        acknowledged = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE, [sequence], MEMORY_DOMAIN)],
            guards,
        )
        if not acknowledged:
            logger.debug("Deferred Red Coin mailbox acknowledgement for sequence %d.", sequence)
