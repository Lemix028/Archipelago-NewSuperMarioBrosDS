"""Queued client-to-Lua notifications for short in-game feedback."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_AP_BONUS_STATE_MAGIC_1,
    ADDR_AP_BONUS_STATE_MAGIC_2,
    ADDR_AP_NOTIFICATION_ACK_SEQUENCE,
    ADDR_AP_NOTIFICATION_DETAIL,
    ADDR_AP_NOTIFICATION_SEQUENCE,
    ADDR_AP_NOTIFICATION_TYPE,
    AP_BONUS_STATE_MAGIC_1,
    AP_BONUS_STATE_MAGIC_2,
    MEMORY_DOMAIN,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


class NotificationHandlingMixin:
    """Publish one queued notification whenever Lua's mailbox is idle."""

    def _queue_ap_notification(self, notification_type: int, detail: int = 0) -> None:
        self._pending_ap_notifications.append((notification_type, detail))

    async def _publish_next_ap_notification(self, ctx: "BizHawkClientContext") -> None:
        if not self._pending_ap_notifications:
            return

        from worlds._bizhawk import guarded_read, guarded_write

        result = await guarded_read(
            ctx.bizhawk_ctx,
            [
                (ADDR_AP_NOTIFICATION_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_NOTIFICATION_ACK_SEQUENCE, 1, MEMORY_DOMAIN),
                (ADDR_AP_BONUS_STATE_MAGIC_1, 1, MEMORY_DOMAIN),
                (ADDR_AP_BONUS_STATE_MAGIC_2, 1, MEMORY_DOMAIN),
            ],
            self._game_data_guards(),
        )
        if result is None or len(result) != 4 or any(len(value) != 1 for value in result):
            return

        sequence, acknowledged, magic_1, magic_2 = (value[0] for value in result)
        if (magic_1, magic_2) != (AP_BONUS_STATE_MAGIC_1, AP_BONUS_STATE_MAGIC_2):
            return
        if sequence != acknowledged:
            return

        notification_type, detail = self._pending_ap_notifications[0]
        next_sequence = (sequence + 1) % 256
        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [
                (ADDR_AP_NOTIFICATION_TYPE, [notification_type], MEMORY_DOMAIN),
                (ADDR_AP_NOTIFICATION_DETAIL, [detail], MEMORY_DOMAIN),
                (ADDR_AP_NOTIFICATION_SEQUENCE, [next_sequence], MEMORY_DOMAIN),
            ],
            [
                *self._game_data_guards(),
                (ADDR_AP_NOTIFICATION_SEQUENCE, [sequence], MEMORY_DOMAIN),
                (ADDR_AP_NOTIFICATION_ACK_SEQUENCE, [acknowledged], MEMORY_DOMAIN),
                (ADDR_AP_BONUS_STATE_MAGIC_1, [AP_BONUS_STATE_MAGIC_1], MEMORY_DOMAIN),
                (ADDR_AP_BONUS_STATE_MAGIC_2, [AP_BONUS_STATE_MAGIC_2], MEMORY_DOMAIN),
            ],
        )
        if applied:
            self._pending_ap_notifications.pop(0)
