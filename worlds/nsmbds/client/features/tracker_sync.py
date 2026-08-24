"""Publish the current game view for companion trackers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_AP_STAR_COIN_GATE_HOOK_MARKER,
    ADDR_CURRENT_COURSE_LEVEL,
    ADDR_CURRENT_COURSE_WORLD,
    AP_STAR_COIN_GATE_HOOK_MARKER,
    MEMORY_DOMAIN,
)
from ...locations import RUNTIME_COURSE_TO_STAGE_NAME

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


class PopTrackerWorldSyncMixin:
    """Mirror the Worldmap or active course through room-local DataStorage."""

    @staticmethod
    def _poptracker_view_storage_key(ctx: "BizHawkClientContext") -> str | None:
        team = getattr(ctx, "team", None)
        slot = getattr(ctx, "slot", None)
        if team is None or slot is None:
            return None
        return f"nsmbds_current_view_{int(team)}_{int(slot)}"

    async def _sync_poptracker_world(self, ctx: "BizHawkClientContext") -> None:
        """Publish the exact Worldmap/course tab only when the view changes."""
        from worlds._bizhawk import read

        result = await read(
            ctx.bizhawk_ctx,
            [
                (ADDR_CURRENT_COURSE_WORLD, 1, MEMORY_DOMAIN),
                (ADDR_CURRENT_COURSE_LEVEL, 1, MEMORY_DOMAIN),
                (
                    ADDR_AP_STAR_COIN_GATE_HOOK_MARKER,
                    len(AP_STAR_COIN_GATE_HOOK_MARKER),
                    MEMORY_DOMAIN,
                ),
            ],
        )
        if (
            len(result) != 3
            or len(result[0]) != 1
            or len(result[1]) != 1
            or len(result[2]) != len(AP_STAR_COIN_GATE_HOOK_MARKER)
        ):
            return

        world_index = result[0][0]
        if not 0 <= world_index < 8:
            return
        world_number = world_index + 1

        if bytes(result[2]) == AP_STAR_COIN_GATE_HOOK_MARKER:
            tab_title = f"W{world_number} Overworld"
        else:
            stage_name = RUNTIME_COURSE_TO_STAGE_NAME.get((world_index, result[1][0]))
            if stage_name is None:
                return
            tab_title = stage_name.replace("World ", "W", 1)

        view = f"{world_number}|{tab_title}"
        key = self._poptracker_view_storage_key(ctx)
        if key is None:
            return

        published_state = (key, view)

        if getattr(self, "_last_published_poptracker_view", None) == published_state:
            return
        await ctx.send_msgs(
            [
                {
                    "cmd": "Set",
                    "key": key,
                    "default": "",
                    "want_reply": False,
                    "operations": [{"operation": "replace", "value": view}],
                }
            ]
        )
        self._last_published_poptracker_view = published_state
