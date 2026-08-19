"""Goal evaluation behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...locations import LOCATION_TABLE
from ...items import ITEM_TABLE
from ...data.ram_addresses import AP_NOTIFICATION_GOAL_COMPLETE

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

CASTLE_GOAL_LOCATION_NAMES = tuple(
    [f"World {world}-Castle Goal" for world in range(1, 8)]
    + ["World 8-Bowser's Castle Goal"]
)
CASTLE_GOAL_LOCATION_IDS = frozenset(LOCATION_TABLE[name] for name in CASTLE_GOAL_LOCATION_NAMES)
BOWSER_LOCATION_ID = LOCATION_TABLE["World 8-Bowser's Castle Goal"]
W8_TOWER2_GOAL_LOCATION_ID = LOCATION_TABLE["World 8-Tower 2 Goal"]


class GoalHandlingMixin:
    """Evaluate configured goals and notify the Archipelago server once."""

    @staticmethod
    def _received_star_coin_count(ctx: "BizHawkClientContext") -> int:
        """Return the permanent lifetime total owned by the AP server."""
        star_coin_id = ITEM_TABLE["Star Coin"][0]
        return sum(item.item == star_coin_id for item in ctx.items_received)

    def _final_castle_gate_should_open(self, ctx: "BizHawkClientContext") -> bool | None:
        """Return a forced-open final path, or ``None`` for normal map control."""
        goal = ctx.slot_data.get("goal", 0) if ctx.slot_data else 0
        if goal in (0, 1, 3):
            if W8_TOWER2_GOAL_LOCATION_ID in self._observed_locations:
                return True
            return None
        if goal == 2:
            return (CASTLE_GOAL_LOCATION_IDS - {BOWSER_LOCATION_ID}) <= self._observed_locations
        logger.error("Received unsupported NSMBDS goal value %s for the final castle gate.", goal)
        return None

    async def _send_goal_if_complete(self, ctx: "BizHawkClientContext") -> None:
        """Send CLIENT_GOAL at most once after the local goal condition is done."""
        if self._goal_sent or ctx.finished_game or not self._check_goal(ctx):
            return
        try:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": 30}])
        except Exception:
            logger.exception("Failed to submit NSMBDS goal completion.")
            return
        ctx.finished_game = True
        self._goal_sent = True
        self._queue_ap_notification(AP_NOTIFICATION_GOAL_COMPLETE)

    def _check_goal(self, ctx: "BizHawkClientContext") -> bool:
        """Evaluate the selected local goal from observed RAM-backed locations."""
        goal = ctx.slot_data.get("goal", 0) if ctx.slot_data else 0
        if goal == 0:
            return BOWSER_LOCATION_ID in self._observed_locations
        if goal == 1:
            required = ctx.slot_data.get("required_star_coins", 80)
            return self._received_star_coin_count(ctx) >= required
        if goal == 2:
            return CASTLE_GOAL_LOCATION_IDS <= self._observed_locations
        if goal == 3:
            required = ctx.slot_data.get("required_star_coins", 80)
            return (
                BOWSER_LOCATION_ID in self._observed_locations
                and self._received_star_coin_count(ctx) >= required
            )
        logger.error("Received unsupported NSMBDS goal value %s.", goal)
        return False
