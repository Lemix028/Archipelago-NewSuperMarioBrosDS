"""Death Link behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_AP_INSURED_DEATH_SEQUENCE,
    ADDR_AP_LIFE_INSURANCE_COUNT,
    ADDR_AP_TRAP_SHIELD_COUNT,
    ADDR_LIVES,
    ADDR_STAGE_EXIT_FLAGS,
    ADDR_TIMER,
    MEMORY_DOMAIN,
    STAGE_EXIT_RETURN_TO_MAP_MASK,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")


class DeathLinkMixin:
    """Synchronize Death Link and use the native timer-expiry death effect."""

    async def _sync_death_link(self, ctx: "BizHawkClientContext") -> None:
        """Register the Death Link tag only when the current slot enables it."""
        enabled = bool(ctx.slot_data and ctx.slot_data.get("death_link", False))
        if enabled == self._death_link_enabled:
            return
        await ctx.update_death_link(enabled)
        self._death_link_enabled = enabled
        if not enabled:
            self._pending_death_link = False
            self._return_to_map_pending = False
            self._suppress_local_death_polls = 0
        logger.info("NSMBDS Death Link %s.", "enabled" if enabled else "disabled")

    @staticmethod
    def _timer_is_counting(previous_timer: int | None, timer: int) -> bool:
        """Return whether the verified level timer decreased since the last poll."""
        return previous_timer is not None and 0 < timer < previous_timer

    async def _read_lives_and_timer(
        self,
        ctx: "BizHawkClientContext",
    ) -> tuple[int, int, int, int, int, int] | None:
        """Read death state plus Lua-visible protection charges."""
        from worlds._bizhawk import read

        try:
            result = await read(
                ctx.bizhawk_ctx,
                [
                    (ADDR_LIVES, 1, MEMORY_DOMAIN),
                    (ADDR_TIMER, 4, MEMORY_DOMAIN),
                    (ADDR_AP_TRAP_SHIELD_COUNT, 1, MEMORY_DOMAIN),
                    (ADDR_AP_LIFE_INSURANCE_COUNT, 1, MEMORY_DOMAIN),
                    (ADDR_AP_INSURED_DEATH_SEQUENCE, 1, MEMORY_DOMAIN),
                    (ADDR_STAGE_EXIT_FLAGS, 4, MEMORY_DOMAIN),
                ],
            )
        except Exception:
            logger.exception("Failed to read NSMBDS Death Link state.")
            return None
        if len(result) != 6 or [len(value) for value in result] != [1, 4, 1, 1, 1, 4]:
            logger.warning("Received invalid NSMBDS Death Link state data.")
            return None
        return (
            result[0][0],
            struct.unpack("<I", bytes(result[1]))[0],
            result[2][0],
            result[3][0],
            result[4][0],
            struct.unpack("<I", bytes(result[5]))[0],
        )

    async def _handle_death_link(self, ctx: "BizHawkClientContext") -> None:
        """Apply queued incoming Death Links and send eligible local deaths."""
        state = await self._read_lives_and_timer(ctx)
        if state is None:
            return
        lives, timer, shield_count, insurance_count, insured_death_sequence, exit_flags = state
        self._pending_trap_shields = shield_count
        self._pending_life_insurance = insurance_count
        insured_death = (
            self._last_insured_death_sequence is not None
            and insured_death_sequence != self._last_insured_death_sequence
        )
        self._last_insured_death_sequence = insured_death_sequence
        timer_is_counting = self._timer_is_counting(self._last_timer, timer)
        self._last_timer = timer

        return_to_map_active = bool(exit_flags & STAGE_EXIT_RETURN_TO_MAP_MASK)
        if return_to_map_active:
            self._return_to_map_pending = True
        elif timer_is_counting:
            # A newly active level clears a stale marker left by an earlier
            # Return-to-Map transition.
            self._return_to_map_pending = False

        if timer_is_counting:
            self._in_level_grace_polls = 16
        elif self._in_level_grace_polls:
            self._in_level_grace_polls -= 1

        enabled = bool(ctx.slot_data and ctx.slot_data.get("death_link", False))
        if enabled and self._pending_death_link and timer_is_counting and not self._return_to_map_pending:
            from worlds._bizhawk import guarded_write

            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_TIMER, [0, 0, 0, 0], MEMORY_DOMAIN)],
                self._game_data_guards(),
            )
            if applied:
                self._pending_death_link = False
                self._suppress_local_death_polls = 1  # Mark that 1 incoming death needs suppression
                logger.info("Applied queued Death Link by expiring the level timer.")
            else:
                logger.info("Deferred queued Death Link until the timer write succeeds.")

        if self._last_lives is None:
            self._last_lives = lives
            return

        life_lost = lives < self._last_lives
        self._last_lives = lives

        trigger_on_insured = bool(ctx.slot_data and ctx.slot_data.get("death_link_triggers_on_insured_death", True))
        should_trigger = life_lost or (insured_death and trigger_on_insured)

        if not enabled or not should_trigger:
            return
        if self._return_to_map_pending:
            self._return_to_map_pending = False
            logger.info("Ignored life loss caused by Return to Map.")
            return
        if self._suppress_local_death_polls > 0:
            self._suppress_local_death_polls -= 1
            logger.info("Suppressed outgoing Death Link caused by an incoming Death Link.")
            return
        if not self._in_level_grace_polls:
            logger.info("Ignored life loss outside a recently active level timer.")
            return
        await ctx.send_death("Mario died.")
        logger.info("Sent Death Link for a local Mario death.")
