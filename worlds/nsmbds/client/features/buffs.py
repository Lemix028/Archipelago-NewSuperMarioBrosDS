"""Live-verified positive buff and filler behavior."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_AP_BONUS_STATE_MAGIC_1,
    ADDR_AP_BONUS_STATE_MAGIC_2,
    ADDR_AP_LIFE_INSURANCE_COUNT,
    ADDR_AP_NOTIFICATION_ACK_SEQUENCE,
    ADDR_AP_NOTIFICATION_DETAIL,
    ADDR_AP_NOTIFICATION_SEQUENCE,
    ADDR_AP_NOTIFICATION_TYPE,
    ADDR_AP_TRAP_SHIELD_COUNT,
    ADDR_COINS,
    ADDR_LIVES,
    ADDR_STARMAN_TIMER,
    ADDR_TIMER,
    AP_BONUS_STATE_MAGIC_1,
    AP_BONUS_STATE_MAGIC_2,
    AP_NOTIFICATION_CARE_PACKAGE,
    AP_NOTIFICATION_LIFE_INSURANCE,
    AP_NOTIFICATION_STARMAN_LITE,
    AP_NOTIFICATION_STARMAN_BUFF,
    AP_NOTIFICATION_TIME_CAPSULE,
    AP_NOTIFICATION_TRAP_BLOCKED,
    AP_NOTIFICATION_TRAP_SHIELD,
    MEMORY_DOMAIN,
    STARMAN_DURATION_FRAMES,
    TIMER_UNITS_PER_SECOND,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

TIME_CAPSULE_SECONDS = 30
CARE_PACKAGE_SECONDS = 15
CARE_PACKAGE_COINS = 5
CARE_PACKAGE_LIVES = 1
STARMAN_LITE_FRAMES = 300
MAX_LEVEL_TIME_UNITS = 999 * TIMER_UNITS_PER_SECOND
MAX_BONUS_CHARGES = 99

TRAP_NOTIFICATION_DETAILS = {
    "Time Drain": 2,
    "Coin Thief": 3,
    "Bonk Trap": 4,
    "Super Speed": 5,
    "Slowness": 6,
    "Slippery Gloves": 7,
    "Ground Bound": 8,
    "Hyper Confusion": 9,
    "No Sprint": 10,
    "Button Swap": 11,
    "Ice Shoes": 12,
    "Heavy Mario": 13,
    "Can't Stop": 14,
    "Sticky Buttons": 15,
    "Coin Tax": 16,
    "Camera Drift": 18,
    "Screen Flip": 19,
    "Drunk Camera": 20,
    "Boo Curse": 21,
    "I'm Stuck": 22,
    "Screen Tint": 23,
    "Retro Filter": 24,
    "Spotlight": 25,
    "Ground Clap": 26,
    "Head Bonk": 27,
    "Pixelation": 28,
}


class BuffHandlingMixin:
    """Apply verified positive buffs."""

    def _queue_starman_buff(self) -> None:
        """Queue one Starman Buff for the next active level."""
        self._pending_starman_buffs += 1
        logger.debug("Queued Starman Buff until the player is inside an active level.")

    def _queue_time_capsule(self) -> None:
        self._pending_time_capsules += 1

    def _queue_starman_lite(self) -> None:
        self._pending_starman_lites += 1

    def _queue_care_package(self) -> None:
        self._pending_care_packages += 1

    async def _add_shared_bonus_charge(
        self,
        ctx: "BizHawkClientContext",
        address: int,
        attribute: str,
        label: str,
    ) -> bool:
        """Atomically add one Lua-visible shield or insurance charge."""
        from worlds._bizhawk import guarded_read, guarded_write

        result = await guarded_read(
            ctx.bizhawk_ctx,
            [(address, 1, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if result is None or len(result) != 1 or len(result[0]) != 1:
            return False
        observed_current = result[0][0]
        current = observed_current
        if observed_current > MAX_BONUS_CHARGES:
            logger.warning("Reset invalid %s RAM value %d before adding a charge.", label, observed_current)
            current = 0
        target = min(MAX_BONUS_CHARGES, current + 1)
        if target != current:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(address, [target], MEMORY_DOMAIN)],
                [*self._game_data_guards(), (address, [observed_current], MEMORY_DOMAIN)],
            )
            if not applied:
                return False
        setattr(self, attribute, target)
        notification_type = (
            AP_NOTIFICATION_TRAP_SHIELD
            if address == ADDR_AP_TRAP_SHIELD_COUNT
            else AP_NOTIFICATION_LIFE_INSURANCE
        )
        self._queue_ap_notification(notification_type)
        logger.info("Received %s charge; %d available.", label, target)
        return True

    async def _add_trap_shield(self, ctx: "BizHawkClientContext") -> bool:
        return await self._add_shared_bonus_charge(
            ctx,
            ADDR_AP_TRAP_SHIELD_COUNT,
            "_pending_trap_shields",
            "Trap Shield",
        )

    async def _add_life_insurance(self, ctx: "BizHawkClientContext") -> bool:
        return await self._add_shared_bonus_charge(
            ctx,
            ADDR_AP_LIFE_INSURANCE_COUNT,
            "_pending_life_insurance",
            "Life Insurance",
        )

    async def _initialize_bonus_mailbox(self, ctx: "BizHawkClientContext") -> None:
        """Clear uninitialized protection bytes once for each AP session."""
        if not self._bonus_mailbox_needs_reset:
            return
        from worlds._bizhawk import guarded_read, guarded_write
        from ...data.ram_addresses import ADDR_AP_INSURED_DEATH_SEQUENCE

        state_writes = [
            (ADDR_AP_TRAP_SHIELD_COUNT, [0], MEMORY_DOMAIN),
            (ADDR_AP_LIFE_INSURANCE_COUNT, [0], MEMORY_DOMAIN),
            (ADDR_AP_INSURED_DEATH_SEQUENCE, [0], MEMORY_DOMAIN),
            (ADDR_AP_NOTIFICATION_SEQUENCE, [0], MEMORY_DOMAIN),
            (ADDR_AP_NOTIFICATION_TYPE, [0], MEMORY_DOMAIN),
            (ADDR_AP_NOTIFICATION_DETAIL, [0], MEMORY_DOMAIN),
            (ADDR_AP_NOTIFICATION_ACK_SEQUENCE, [0], MEMORY_DOMAIN),
            (ADDR_AP_BONUS_STATE_MAGIC_1, [AP_BONUS_STATE_MAGIC_1], MEMORY_DOMAIN),
            (ADDR_AP_BONUS_STATE_MAGIC_2, [AP_BONUS_STATE_MAGIC_2], MEMORY_DOMAIN),
        ]
        applied = await guarded_write(
            ctx.bizhawk_ctx,
            state_writes,
            self._game_data_guards(),
        )
        if not applied:
            return
        readback = await guarded_read(
            ctx.bizhawk_ctx,
            [(address, 1, domain) for address, _value, domain in state_writes],
            self._game_data_guards(),
        )
        expected = [value[0] for _address, value, _domain in state_writes]
        observed = [value[0] for value in readback] if readback and all(len(value) == 1 for value in readback) else []
        if observed != expected:
            logger.warning(
                "Protection state initialization did not persist (expected=%s, observed=%s); retrying.",
                expected,
                observed,
            )
            return
        self._pending_trap_shields = 0
        self._pending_life_insurance = 0
        self._last_insured_death_sequence = 0
        self._pending_ap_notifications.clear()
        self._bonus_mailbox_needs_reset = False
        logger.info("Initialized Trap Shield and Life Insurance state for this AP session.")

    async def _consume_trap_shield(
        self,
        ctx: "BizHawkClientContext",
        trap_name: str,
    ) -> bool | None:
        """Consume one shared charge; return None while RAM is unavailable."""
        from worlds._bizhawk import guarded_read, guarded_write

        result = await guarded_read(
            ctx.bizhawk_ctx,
            [(ADDR_AP_TRAP_SHIELD_COUNT, 1, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if result is None or len(result) != 1 or len(result[0]) != 1:
            return None
        current = result[0][0]
        if current > MAX_BONUS_CHARGES:
            logger.warning("Reset invalid Trap Shield RAM value %d without blocking the Trap.", current)
            await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_SHIELD_COUNT, [0], MEMORY_DOMAIN)],
                [
                    *self._game_data_guards(),
                    (ADDR_AP_TRAP_SHIELD_COUNT, [current], MEMORY_DOMAIN),
                ],
            )
            self._pending_trap_shields = 0
            return False
        self._pending_trap_shields = current
        if current == 0:
            return False
        target = current - 1
        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_AP_TRAP_SHIELD_COUNT, [target], MEMORY_DOMAIN)],
            [
                *self._game_data_guards(),
                (ADDR_AP_TRAP_SHIELD_COUNT, [current], MEMORY_DOMAIN),
            ],
        )
        if not applied:
            return None
        self._pending_trap_shields = target
        # A blocked Trap is immediate feedback, not an ordinary filler notice.
        self._pending_ap_notifications.insert(
            0,
            (AP_NOTIFICATION_TRAP_BLOCKED, TRAP_NOTIFICATION_DETAILS.get(trap_name, 0)),
        )
        logger.info("Trap Shield blocked %s; %d charge(s) remain.", trap_name, target)
        return True

    async def _apply_pending_starman_buffs(self, ctx: "BizHawkClientContext") -> None:
        """Apply one queued Starman Buff while inside an active level."""
        if not getattr(self, "_pending_starman_buffs", 0) or not getattr(self, "_in_level_grace_polls", 0):
            return

        from worlds._bizhawk import guarded_write

        bytes_val = list(struct.pack("<I", STARMAN_DURATION_FRAMES))
        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_STARMAN_TIMER, bytes_val, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if not applied:
            logger.debug("Deferred Starman Buff until the RAM write succeeds.")
            return

        self._pending_starman_buffs -= 1
        self._queue_ap_notification(AP_NOTIFICATION_STARMAN_BUFF)
        logger.info(
            "Applied Starman Buff: granted %d frames (~15s) of invincibility.",
            STARMAN_DURATION_FRAMES,
        )

    async def _apply_pending_filler_bonuses(self, ctx: "BizHawkClientContext") -> None:
        """Apply at most one queued bonus of each kind during a safe level tick."""
        if not getattr(self, "_in_level_grace_polls", 0):
            return
        await self._apply_one_time_capsule(ctx)
        await self._apply_one_starman_lite(ctx)
        await self._apply_one_care_package(ctx)

    async def _apply_one_time_capsule(self, ctx: "BizHawkClientContext") -> None:
        if not self._pending_time_capsules:
            return
        current = await self._read_u32(ctx, ADDR_TIMER)
        if current is None or current == 0:
            return
        target = min(MAX_LEVEL_TIME_UNITS, current + TIME_CAPSULE_SECONDS * TIMER_UNITS_PER_SECOND)
        if await self._write_guarded_values(ctx, [(ADDR_TIMER, current, target, 4)]):
            self._pending_time_capsules -= 1
            self._queue_ap_notification(AP_NOTIFICATION_TIME_CAPSULE)
            logger.info("Applied Time Capsule: +%d level seconds.", TIME_CAPSULE_SECONDS)

    async def _apply_one_starman_lite(self, ctx: "BizHawkClientContext") -> None:
        if not self._pending_starman_lites:
            return
        current = await self._read_u32(ctx, ADDR_STARMAN_TIMER)
        if current is None:
            return
        target = current if current >= STARMAN_DURATION_FRAMES else min(
            STARMAN_DURATION_FRAMES,
            current + STARMAN_LITE_FRAMES,
        )
        if await self._write_guarded_values(ctx, [(ADDR_STARMAN_TIMER, current, target, 4)]):
            self._pending_starman_lites -= 1
            self._queue_ap_notification(AP_NOTIFICATION_STARMAN_LITE)
            logger.info("Applied Starman Lite: +%d invincibility frames.", STARMAN_LITE_FRAMES)

    async def _apply_one_care_package(self, ctx: "BizHawkClientContext") -> None:
        if not self._pending_care_packages:
            return
        from worlds._bizhawk import guarded_read

        result = await guarded_read(
            ctx.bizhawk_ctx,
            [
                (ADDR_TIMER, 4, MEMORY_DOMAIN),
                (ADDR_COINS, 1, MEMORY_DOMAIN),
                (ADDR_LIVES, 1, MEMORY_DOMAIN),
            ],
            self._game_data_guards(),
        )
        if result is None or [len(value) for value in result] != [4, 1, 1]:
            return
        timer = struct.unpack("<I", bytes(result[0]))[0]
        if timer == 0:
            return
        coins = result[1][0]
        lives = result[2][0]
        changes = [
            (ADDR_TIMER, timer, min(MAX_LEVEL_TIME_UNITS, timer + CARE_PACKAGE_SECONDS * TIMER_UNITS_PER_SECOND), 4),
            (ADDR_COINS, coins, min(99, coins + CARE_PACKAGE_COINS), 1),
            (ADDR_LIVES, lives, min(99, lives + CARE_PACKAGE_LIVES), 1),
        ]
        if await self._write_guarded_values(ctx, changes):
            self._pending_care_packages -= 1
            self._queue_ap_notification(AP_NOTIFICATION_CARE_PACKAGE)
            logger.info(
                "Applied Small Care Package: +%ds, +%d coins, +%d life.",
                CARE_PACKAGE_SECONDS,
                CARE_PACKAGE_COINS,
                CARE_PACKAGE_LIVES,
            )

    async def _read_u32(self, ctx: "BizHawkClientContext", address: int) -> int | None:
        from worlds._bizhawk import guarded_read

        result = await guarded_read(
            ctx.bizhawk_ctx,
            [(address, 4, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if result is None or len(result) != 1 or len(result[0]) != 4:
            return None
        return struct.unpack("<I", bytes(result[0]))[0]

    async def _write_guarded_values(
        self,
        ctx: "BizHawkClientContext",
        changes: list[tuple[int, int, int, int]],
    ) -> bool:
        """Atomically write changed integers while guarding their old values."""
        from worlds._bizhawk import guarded_write

        changed = [change for change in changes if change[1] != change[2]]
        if not changed:
            return True
        writes = []
        guards = list(self._game_data_guards())
        for address, current, target, size in changed:
            current_bytes = list(current.to_bytes(size, "little"))
            target_bytes = list(target.to_bytes(size, "little"))
            writes.append((address, target_bytes, MEMORY_DOMAIN))
            # Countdown timers are volatile between the guarded read and write.
            # Exact-value guards would reject almost every legitimate bonus.
            if address not in (ADDR_TIMER, ADDR_STARMAN_TIMER):
                guards.append((address, current_bytes, MEMORY_DOMAIN))
        return await guarded_write(ctx.bizhawk_ctx, writes, guards)
