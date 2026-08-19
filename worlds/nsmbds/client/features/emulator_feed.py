"""Real-time Archipelago PrintJSON activity for the BizHawk overlay."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ...items import ITEM_TABLE, TRAP_ITEM_NAMES, item_id_to_name
from ...locations import LOCATION_TABLE

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")
LOCATION_ID_TO_NAME = {location_id: name for name, location_id in LOCATION_TABLE.items()}
FEED_HISTORY_BATCH_SIZE = 40


def _network_value(item: object, name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


class EmulatorFeedMixin:
    """Mirror relevant Core ItemSend messages to BizHawk without polling delay."""

    @staticmethod
    def _item_color(flags: int, item_id: int | None = None) -> str:
        # Prefer local catalog classification if item_id is known (e.g. server/cheat given items)
        if item_id is not None:
            name = item_id_to_name.get(item_id)
            if name in TRAP_ITEM_NAMES:
                return "trap"
            if name in ITEM_TABLE:
                classification = int(ITEM_TABLE[name][1])
                if classification & 0b0001:
                    return "progression"
                if classification & 0b0010:
                    return "useful"
                if classification & 0b1000:
                    return "trap"

        if flags & 0b100:
            return "trap"
        if flags & 0b001:
            return "progression"
        if flags & 0b010:
            return "useful"
        return "filler"

    @staticmethod
    def _slot_concerns_self(ctx: "BizHawkClientContext", slot: int) -> bool:
        predicate = getattr(ctx, "slot_concerns_self", None)
        if callable(predicate):
            return bool(predicate(slot))
        return slot == getattr(ctx, "slot", None)

    @classmethod
    def _player_color(cls, ctx: "BizHawkClientContext", slot: int) -> str:
        return "player_self" if cls._slot_concerns_self(ctx, slot) else "player"

    @staticmethod
    def _player_name(ctx: "BizHawkClientContext", slot: int) -> str:
        return str(getattr(ctx, "player_names", {}).get(slot, f"Player {slot}"))

    @staticmethod
    def _item_name(ctx: "BizHawkClientContext", item_id: int, receiving: int) -> str:
        lookup = getattr(ctx, "item_names", None)
        try:
            if lookup is not None:
                return str(lookup.lookup_in_slot(item_id, receiving))
        except (AttributeError, KeyError, TypeError):
            pass
        return item_id_to_name.get(item_id, f"Unknown Item ({item_id})")

    @staticmethod
    def _location_name(ctx: "BizHawkClientContext", location_id: int, finder: int) -> str:
        lookup = getattr(ctx, "location_names", None)
        try:
            if lookup is not None:
                return str(lookup.lookup_in_slot(location_id, finder))
        except (AttributeError, KeyError, TypeError):
            pass
        return LOCATION_ID_TO_NAME.get(location_id, f"Unknown Location ({location_id})")

    def _queue_core_item_send(self, ctx: "BizHawkClientContext", args: dict) -> None:
        if args.get("type") != "ItemSend":
            return
        network_item = args.get("item")
        if network_item is None:
            return

        finder = int(_network_value(network_item, "player", -1))
        receiving = int(args.get("receiving", -1))
        # ReceivedItems is authoritative for everything delivered to this
        # client. PrintJSON remains the source for items this player sends out.
        if self._slot_concerns_self(ctx, receiving):
            return
        if not (
            self._slot_concerns_self(ctx, finder)
            or self._slot_concerns_self(ctx, receiving)
        ):
            return

        self._queue_emulator_item_message(ctx, network_item, receiving)

    def _queue_emulator_item_message(
        self,
        ctx: "BizHawkClientContext",
        network_item: object,
        receiving: int,
    ) -> None:
        finder = int(_network_value(network_item, "player", -1))

        item_id = int(_network_value(network_item, "item", -1))
        location_id = int(_network_value(network_item, "location", -1))
        flags = int(_network_value(network_item, "flags", 0))
        finder_name = self._player_name(ctx, finder)
        item_name = self._item_name(ctx, item_id, receiving)
        location_name = self._location_name(ctx, location_id, finder)
        segments: list[dict[str, str]] = [
            {"text": finder_name, "color": self._player_color(ctx, finder)},
        ]
        if finder == receiving:
            segments.extend((
                {"text": " found ", "color": "text"},
                {"text": item_name, "color": self._item_color(flags, item_id)},
            ))
        else:
            segments.extend((
                {"text": " sent ", "color": "text"},
                {"text": item_name, "color": self._item_color(flags, item_id)},
                {"text": " to ", "color": "text"},
                {"text": self._player_name(ctx, receiving),
                 "color": self._player_color(ctx, receiving)},
            ))
        segments.extend((
            {"text": " (", "color": "text"},
            {"text": location_name, "color": "location"},
            {"text": ")", "color": "text"},
        ))
        self._pending_emulator_feed.append(tuple(
            (segment["text"], segment["color"]) for segment in segments
        ))
        self._schedule_emulator_feed_flush(ctx)

    def _queue_emulator_system_message(
        self,
        ctx: "BizHawkClientContext",
        text: str,
        color: str = "text",
    ) -> None:
        self._pending_emulator_feed.append(((text, color),))
        self._schedule_emulator_feed_flush(ctx)

    async def _sync_emulator_feed(
        self,
        ctx: "BizHawkClientContext",
        *,
        server_connected: bool = True,
    ) -> None:
        """Announce both connection layers and backfill server item history."""
        if not server_connected:
            if self._emulator_feed_server_announced:
                self._queue_emulator_system_message(
                    ctx,
                    "NSMBDS Client disconnected from the Archipelago server.",
                    "warning",
                )
                self._emulator_feed_server_announced = False
            await self._flush_emulator_feed(ctx)
            return

        if not self._emulator_feed_server_announced:
            self._queue_emulator_system_message(
                ctx,
                "NSMBDS Client connected to the Archipelago server.",
                "success",
            )
            self._emulator_feed_server_announced = True

        received_items = getattr(ctx, "items_received", ())
        history_end = min(
            len(received_items),
            self._emulator_feed_received_index + FEED_HISTORY_BATCH_SIZE,
        )
        for network_item in received_items[self._emulator_feed_received_index:history_end]:
            self._queue_emulator_item_message(ctx, network_item, int(ctx.slot))
            self._emulator_feed_received_index += 1

        await self._flush_emulator_feed(ctx)

    def _schedule_emulator_feed_flush(self, ctx: "BizHawkClientContext") -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        task = getattr(self, "_emulator_feed_flush_task", None)
        if task is None or task.done():
            self._emulator_feed_flush_task = loop.create_task(
                self._flush_emulator_feed(ctx),
                name="NSMBDS emulator feed",
            )

    async def _flush_emulator_feed(self, ctx: "BizHawkClientContext") -> None:
        async with self._emulator_feed_flush_lock:
            if not self._pending_emulator_feed:
                return

            from worlds._bizhawk import send_requests

            # Keep late-connect history from monopolizing one watcher tick.
            queued = list(self._pending_emulator_feed)[:FEED_HISTORY_BATCH_SIZE]
            requests = [{
                "type": "NSMBDS_FEED_MESSAGE",
                "segments": [
                    {"text": text, "color": color}
                    for text, color in segments
                ],
            } for segments in queued]
            try:
                responses = await send_requests(ctx.bizhawk_ctx, requests)
            except Exception:
                logger.debug("BizHawk feed delivery deferred until the next watcher tick.", exc_info=True)
                return
            if len(responses) != len(requests) or any(
                response.get("type") != "NSMBDS_FEED_MESSAGE_RESPONSE"
                or response.get("value") is not True
                for response in responses
            ):
                logger.warning("BizHawk returned an invalid NSMBDS feed response; retrying next tick.")
                return
            for _ in queued:
                self._pending_emulator_feed.popleft()
