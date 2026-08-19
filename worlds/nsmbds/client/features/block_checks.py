"""Static and moving block-check detection through the Lua block mailbox."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ...locations import (
    BLOCKSANITY_LOCATION_IDS,
    LOCATION_TABLE,
    RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME,
    RUNTIME_BLOCK_TO_ONE_UP_LOCATION_NAME,
    RUNTIME_MOVING_BLOCK_TO_BLOCKSANITY_LOCATION_NAME,
    RUNTIME_MOVING_BLOCK_TO_ONE_UP_LOCATION_NAME,
)
from ...data.ram_addresses import (
    ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE,
    ADDR_AP_BLOCK_EVENT_AREA,
    ADDR_AP_BLOCK_EVENT_LEVEL,
    ADDR_AP_BLOCK_EVENT_SEQUENCE,
    ADDR_AP_BLOCK_EVENT_TILE_X,
    ADDR_AP_BLOCK_EVENT_TILE_Y,
    ADDR_AP_BLOCK_EVENT_TYPE,
    ADDR_AP_BLOCK_EVENT_WORLD,
    AP_EVENT_TYPE_BLOCK_BUMP,
    AP_EVENT_TYPE_BLOCK_GROUND_POUND,
    AP_EVENT_TYPE_MOVING_BLOCK_OPEN,
    MEMORY_DOMAIN,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")


class BlockCheckTrackingMixin:
    """Resolve Lua-observed static bumps and moving-block openings."""

    async def _detect_and_send_block_check(self, ctx: "BizHawkClientContext") -> None:
        """Consume and acknowledge one pending bumped-block event."""
        from worlds._bizhawk import guarded_write, read

        sizes = (1, 1, 4, 4, 4, 4, 4, 1, 1)
        result = await read(
            ctx.bizhawk_ctx,
            [
                (ADDR_AP_BLOCK_EVENT_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_TYPE, 1, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_WORLD, 4, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_LEVEL, 4, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_AREA, 4, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_TILE_X, 4, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_TILE_Y, 4, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_BLOCK_EVENT_SEQUENCE, 1, MEMORY_DOMAIN),
            ],
        )
        if len(result) != len(sizes) or any(len(value) != size for value, size in zip(result, sizes)):
            logger.warning("Received an invalid block mailbox read from BizHawk.")
            return

        sequence, event_type, world_raw, level_raw, area_raw, x_raw, y_raw, acknowledged, sequence_after = result
        sequence_value = sequence[0]
        if sequence_value != sequence_after[0] or sequence_value == acknowledged[0]:
            return

        if event_type[0] not in (
            AP_EVENT_TYPE_BLOCK_BUMP,
            AP_EVENT_TYPE_BLOCK_GROUND_POUND,
            AP_EVENT_TYPE_MOVING_BLOCK_OPEN,
        ):
            logger.warning("Discarded unknown block mailbox event type 0x%02X.", event_type[0])
            await self._acknowledge_block_event(ctx, sequence_value, guarded_write)
            return

        world = struct.unpack("<I", world_raw)[0]
        level = struct.unpack("<I", level_raw)[0]
        area = struct.unpack("<I", area_raw)[0]
        tile_x = struct.unpack("<i", x_raw)[0]
        tile_y = struct.unpack("<i", y_raw)[0]
        runtime_key = (world, level, area, tile_x, tile_y)
        location_name = self._resolve_block_location(runtime_key, event_type[0])
        if location_name is None:
            unmatched_key = (event_type[0], *runtime_key)
            logged_unmatched = getattr(self, "_logged_unmatched_block_events", set())
            if unmatched_key not in logged_unmatched and len(logged_unmatched) < 25:
                logged_unmatched.add(unmatched_key)
                self._logged_unmatched_block_events = logged_unmatched
                logger.warning(
                    "Unmatched block event type=0x%02X "
                    "(world=%d, level=0x%X, area=%d, tile=(%d,%d)).",
                    event_type[0], world, level, area, tile_x, tile_y,
                )
            else:
                logger.debug("Ignored ordinary unmatched block event %r.", unmatched_key)
            await self._acknowledge_block_event(ctx, sequence_value, guarded_write)
            return

        location_id = LOCATION_TABLE[location_name]
        category = "Blocksanity" if location_id in BLOCKSANITY_LOCATION_IDS else "1-Up Block"
        if location_id in self._sent_locations:
            logger.info("Ignored already checked %s: %s.", category, location_name)
            await self._acknowledge_block_event(ctx, sequence_value, guarded_write)
            return
        if not self._is_location_active(ctx, location_name, location_id):
            logger.warning("Ignored %s %r because it is not active in this seed.", category, location_name)
            await self._acknowledge_block_event(ctx, sequence_value, guarded_write)
            return

        try:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": [location_id]}])
        except Exception:
            logger.exception("Failed to submit %s %r; the Lua event remains pending.", category, location_name)
            return

        self._observed_locations.add(location_id)
        self._sent_locations.add(location_id)
        logger.debug("Submitted %s: %s.", category, location_name)
        await self._acknowledge_block_event(ctx, sequence_value, guarded_write)

    @staticmethod
    def _resolve_block_location(runtime_key: tuple[int, int, int, int, int], event_type: int) -> str | None:
        """Resolve an exact actor hit or an unambiguous ground-pound player position."""
        if event_type == AP_EVENT_TYPE_MOVING_BLOCK_OPEN:
            location_name = RUNTIME_MOVING_BLOCK_TO_BLOCKSANITY_LOCATION_NAME.get(runtime_key)
            if location_name is None:
                location_name = RUNTIME_MOVING_BLOCK_TO_ONE_UP_LOCATION_NAME.get(runtime_key)
            if location_name is not None:
                return location_name

            world, level, area, tile_x, tile_y = runtime_key
            nearby: list[tuple[int, str]] = []
            for source_map in (
                RUNTIME_MOVING_BLOCK_TO_BLOCKSANITY_LOCATION_NAME,
                RUNTIME_MOVING_BLOCK_TO_ONE_UP_LOCATION_NAME,
            ):
                for (candidate_world, candidate_level, candidate_area, candidate_x, candidate_y), name in source_map.items():
                    if (
                        candidate_world == world
                        and candidate_level == level
                        and candidate_area == area
                    ):
                        distance = max(
                            abs(candidate_x - tile_x),
                            abs(candidate_y - tile_y),
                        )
                        if distance <= 3:
                            nearby.append((distance, name))
            if not nearby:
                return None
            nearest_distance = min(distance for distance, _name in nearby)
            nearest_names = {
                name for distance, name in nearby if distance == nearest_distance
            }
            return next(iter(nearest_names)) if len(nearest_names) == 1 else None

        location_name = RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME.get(runtime_key)
        if location_name is None:
            location_name = RUNTIME_BLOCK_TO_ONE_UP_LOCATION_NAME.get(runtime_key)
        if location_name is not None:
            return location_name

        # Ordinary bump actors report their exact tile. Resolving a horizontal
        # neighbour here would let an irrelevant breakable brick check the
        # Blocksanity source beside it.
        if event_type != AP_EVENT_TYPE_BLOCK_GROUND_POUND:
            return None

        # The Ground-Pound position fallback reports Mario's impact row. Lua
        # already expands Mario's collision width into exact tile columns, so
        # only the block directly one row above may be selected here.
        world, level, area, tile_x, tile_y = runtime_key
        above_key = (world, level, area, tile_x, tile_y - 1)
        location_name = RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME.get(above_key)
        if location_name is None:
            location_name = RUNTIME_BLOCK_TO_ONE_UP_LOCATION_NAME.get(above_key)
        return location_name

    async def _acknowledge_block_event(self, ctx: "BizHawkClientContext", sequence: int, guarded_write) -> None:
        """Acknowledge a block event only if the sequence remains unchanged."""
        guards = [
            *self._game_data_guards(),
            (ADDR_AP_BLOCK_EVENT_SEQUENCE, [sequence], MEMORY_DOMAIN),
        ]
        acknowledged = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE, [sequence], MEMORY_DOMAIN)],
            guards,
        )
        if not acknowledged:
            logger.debug("Deferred block mailbox acknowledgement for sequence %d.", sequence)
