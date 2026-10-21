"""Goal evaluation behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...data.level_randomization import mapping_from_slot_data
from ...data.ram_addresses import AP_NOTIFICATION_GOAL_COMPLETE
from ...items import FINAL_CASTLE_KEY_NAME, ITEM_TABLE
from ...locations import (
    BOSS_LOCATION_NAMES,
    LOCATION_TABLE,
    build_boss_location_completion_sources,
    build_mapped_location_ram_map,
    build_secret_exit_ram_requirements,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS.Goal")

BOSS_LOCATION_IDS = frozenset(LOCATION_TABLE[name] for name in BOSS_LOCATION_NAMES)
FINAL_BOSS_LOCATION_ID = LOCATION_TABLE[BOSS_LOCATION_NAMES[-1]]
W8_TOWER2_GOAL_LOCATION_ID = LOCATION_TABLE["World 8-Tower 2 Goal"]


class GoalHandlingMixin:
    """Evaluate configured goals and notify the Archipelago server once."""

    @staticmethod
    def _received_star_coin_count(ctx: "BizHawkClientContext") -> int:
        """Return the permanent lifetime total owned by the AP server."""
        star_coin_id = ITEM_TABLE["Star Coin"][0]
        return sum(item.item == star_coin_id for item in ctx.items_received)

    def _final_castle_gate_should_open(self, ctx: "BizHawkClientContext") -> bool | None:
        """Return the AP-owned final-path state, or ``None`` for vanilla map control."""
        slot_data = ctx.slot_data or {}
        goal = slot_data.get("goal", 0)
        if goal in (0, 1, 2, 3):
            level_mapping = mapping_from_slot_data(slot_data)
            tower_two_goal_id = LOCATION_TABLE[
                f"{level_mapping['World 8-Tower 2']} Goal"
            ]
            tower_two_complete = tower_two_goal_id in self._observed_locations
            keys_enabled = bool(slot_data.get("tower_castle_keys", True))
            if keys_enabled:
                received_ids = {item.item for item in ctx.items_received}
                final_key_received = ITEM_TABLE[FINAL_CASTLE_KEY_NAME][0] in received_ids
                return tower_two_complete and final_key_received
            if tower_two_complete:
                return True
            return None
        logger.error("Received unsupported NSMBDS goal value %s for the final castle gate.", goal)
        return None

    async def _send_goal_if_complete(
        self, ctx: "BizHawkClientContext", level_data: bytes
    ) -> None:
        """Send CLIENT_GOAL at most once after the local goal condition is done."""
        if self._goal_sent or ctx.finished_game or not self._check_goal(ctx, level_data):
            return
        try:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": 30}])
        except Exception:
            logger.exception("Failed to submit NSMBDS goal completion.")
            return
        ctx.finished_game = True
        self._goal_sent = True
        logger.info("Submitted goal completion (goal=%s).", (ctx.slot_data or {}).get("goal", 0))
        self._queue_ap_notification(AP_NOTIFICATION_GOAL_COMPLETE)

    def _check_goal(self, ctx: "BizHawkClientContext", level_data: bytes) -> bool:
        """Evaluate boss victories from the current save and coins from AP items."""
        goal = ctx.slot_data.get("goal", 0) if ctx.slot_data else 0
        if goal == 1:
            required = ctx.slot_data.get("required_star_coins", 80)
            return self._received_star_coin_count(ctx) >= required
        if goal not in (0, 2, 3):
            logger.error("Received unsupported NSMBDS goal value %s.", goal)
            return False

        # Another player's !collect can check a boss's randomized item while
        # this slot is offline. Imported AP checks are not proof of a victory
        # in this save, so never use _observed_locations for boss goals.
        level_mapping = mapping_from_slot_data(ctx.slot_data)
        boss_sources = build_boss_location_completion_sources(level_mapping)
        secret_requirements = build_secret_exit_ram_requirements(level_mapping)
        location_ram_map = build_mapped_location_ram_map(level_mapping)
        required_bosses = BOSS_LOCATION_NAMES[-1:] if goal == 0 else BOSS_LOCATION_NAMES
        if not all(
            self._is_location_completed(
                name, level_data, boss_sources, secret_requirements, location_ram_map
            )
            for name in required_bosses
        ):
            return False
        return goal != 3 or self._received_star_coin_count(ctx) >= ctx.slot_data.get(
            "required_star_coins", 80
        )
