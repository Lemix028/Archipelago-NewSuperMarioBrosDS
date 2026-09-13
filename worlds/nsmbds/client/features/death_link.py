"""Death Link behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
import struct
import time
from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_AP_INSURED_DEATH_SEQUENCE,
    ADDR_AP_LIFE_INSURANCE_COUNT,
    ADDR_AP_RETURN_TO_MAP_DEATH_SEQUENCE,
    ADDR_AP_TRAP_SHIELD_COUNT,
    ADDR_AP_TRAP_TRIGGER,
    ADDR_COINS,
    ADDR_LIVES,
    ADDR_POWERUP_LEVEL,
    ADDR_STAGE_EXIT_FLAGS,
    ADDR_TIMER,
    AP_NOTIFICATION_DEATH_LINK,
    MEMORY_DOMAIN,
    STAGE_EXIT_RETURN_TO_MAP_MASK,
    TIMER_UNITS_PER_SECOND,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

DEATH_LINK_EFFECT_DEATH = 0
DEATH_LINK_EFFECT_DAMAGE = 1
DEATH_LINK_EFFECT_TIMER_DRAIN = 2
DEATH_LINK_EFFECT_LOSE_ALL_COINS = 3
DEATH_LINK_EFFECT_RANDOM = 4
DEATH_LINK_CONCRETE_EFFECTS = (
    DEATH_LINK_EFFECT_DEATH,
    DEATH_LINK_EFFECT_DAMAGE,
    DEATH_LINK_EFFECT_TIMER_DRAIN,
    DEATH_LINK_EFFECT_LOSE_ALL_COINS,
)
DEATH_LINK_EFFECT_KEYS = {
    "death": DEATH_LINK_EFFECT_DEATH,
    "damage": DEATH_LINK_EFFECT_DAMAGE,
    "timer_drain": DEATH_LINK_EFFECT_TIMER_DRAIN,
    "lose_all_coins": DEATH_LINK_EFFECT_LOSE_ALL_COINS,
}
DEATH_LINK_EFFECT_NAMES = {
    DEATH_LINK_EFFECT_DEATH: "Death",
    DEATH_LINK_EFFECT_DAMAGE: "Damage",
    DEATH_LINK_EFFECT_TIMER_DRAIN: "100-Second Timer Drain",
    DEATH_LINK_EFFECT_LOSE_ALL_COINS: "Lose All Coins",
}
DEATH_LINK_TIMER_DRAIN_SECONDS = 100
DEATH_LINK_DAMAGE_TRIGGER = 34
DEATH_LINK_NOTIFICATION_GRACE = 4


class DeathLinkMixin:
    """Synchronize Death Link and use the native timer-expiry death effect."""

    def _install_death_link_log_filter(self, ctx: BizHawkClientContext) -> None:
        """Let NSMBDS report only its final DL outcome instead of Core's raw receipt."""
        if getattr(ctx, "_nsmbds_death_link_log_filter_installed", False):
            return
        original_on_deathlink = getattr(ctx, "on_deathlink", None)
        if original_on_deathlink is None:
            return

        def filtered_on_deathlink(data: dict) -> None:
            if getattr(ctx, "client_handler", None) is self:
                timestamp = data.get("time")
                if timestamp is not None:
                    ctx.last_death_link = max(timestamp, ctx.last_death_link)
                return
            original_on_deathlink(data)

        ctx.on_deathlink = filtered_on_deathlink
        ctx._nsmbds_death_link_log_filter_installed = True

    async def _sync_death_link(self, ctx: BizHawkClientContext) -> None:
        """Register the Death Link tag only when the current slot enables it."""
        enabled = bool(ctx.slot_data and ctx.slot_data.get("death_link", False))
        if enabled == self._death_link_enabled:
            return
        await ctx.update_death_link(enabled)
        self._death_link_enabled = enabled
        if not enabled:
            self._pending_death_link = False
            self._pending_death_link_effect = None
            self._return_to_map_pending = False
            self._death_link_cooldown_until = 0.0
            self._suppress_next_local_death = False
        logger.info("NSMBDS Death Link %s.", "enabled" if enabled else "disabled")

    def _queue_incoming_death_link(self, ctx: BizHawkClientContext, source: str | None) -> None:
        """Apply receive-time cooldown/grace rules and retain one accepted effect."""
        slot_data = ctx.slot_data or {}
        if not slot_data.get("death_link", False):
            return

        now = time.monotonic()
        if now < self._death_link_cooldown_until:
            return
        if self._pending_death_link:
            return

        grace_percentage = max(0, min(75, int(slot_data.get("death_link_grace_percentage", 0))))
        if grace_percentage and self._death_link_rng.randrange(100) < grace_percentage:
            self._queue_ap_notification(AP_NOTIFICATION_DEATH_LINK, DEATH_LINK_NOTIFICATION_GRACE)
            logger.info("DL: GRACE.")
            return

        configured_effect = int(slot_data.get("death_link_effect", DEATH_LINK_EFFECT_DEATH))
        if configured_effect == DEATH_LINK_EFFECT_RANDOM:
            configured_random_effects = slot_data.get("death_link_random_effects", DEATH_LINK_EFFECT_KEYS)
            random_effects = tuple(
                effect
                for key, effect in DEATH_LINK_EFFECT_KEYS.items()
                if key in configured_random_effects
            )
            if not random_effects:
                logger.warning("Death Link random effect pool is empty; using all effects.")
                random_effects = DEATH_LINK_CONCRETE_EFFECTS
            effect = self._death_link_rng.choice(random_effects)
        elif configured_effect in DEATH_LINK_CONCRETE_EFFECTS:
            effect = configured_effect
        else:
            effect = DEATH_LINK_EFFECT_DEATH
            logger.warning("Unknown Death Link effect %r; using Death.", configured_effect)

        self._pending_death_link = True
        self._pending_death_link_effect = effect

    async def _apply_pending_death_link(
        self,
        ctx: BizHawkClientContext,
        timer: int,
        powerup: int = 0,
    ) -> bool:
        """Apply the accepted concrete Death Link effect through verified RAM writes."""
        from worlds._bizhawk import guarded_write

        effect = self._pending_death_link_effect
        if effect not in DEATH_LINK_CONCRETE_EFFECTS:
            effect = DEATH_LINK_EFFECT_DEATH
        guards = self._game_data_guards()
        writes: list[tuple[int, list[int], str]]
        may_kill = False

        if effect == DEATH_LINK_EFFECT_DEATH:
            writes = [(ADDR_TIMER, [0, 0, 0, 0], MEMORY_DOMAIN)]
            may_kill = True
        elif effect == DEATH_LINK_EFFECT_DAMAGE:
            guards = [*guards, (ADDR_AP_TRAP_TRIGGER, [0], MEMORY_DOMAIN)]
            writes = [(ADDR_AP_TRAP_TRIGGER, [DEATH_LINK_DAMAGE_TRIGGER], MEMORY_DOMAIN)]
            may_kill = powerup == 0
        elif effect == DEATH_LINK_EFFECT_TIMER_DRAIN:
            drained_timer = max(0, timer - DEATH_LINK_TIMER_DRAIN_SECONDS * TIMER_UNITS_PER_SECOND)
            writes = [(ADDR_TIMER, list(struct.pack("<I", drained_timer)), MEMORY_DOMAIN)]
            may_kill = drained_timer == 0
        else:
            writes = [(ADDR_COINS, [0], MEMORY_DOMAIN)]

        applied = await guarded_write(ctx.bizhawk_ctx, writes, guards)
        if not applied:
            logger.info(
                "Deferred queued Death Link effect %s until its guarded write succeeds.",
                DEATH_LINK_EFFECT_NAMES[effect],
            )
            return False

        self._pending_death_link = False
        self._pending_death_link_effect = None
        if may_kill:
            self._suppress_next_local_death = True
        cooldown_seconds = max(0, min(300, int((ctx.slot_data or {}).get("death_link_cooldown_seconds", 0))))
        if cooldown_seconds:
            self._death_link_cooldown_until = time.monotonic() + cooldown_seconds
        self._queue_ap_notification(AP_NOTIFICATION_DEATH_LINK, effect)
        notification_name = {
            DEATH_LINK_EFFECT_DEATH: "DEATH",
            DEATH_LINK_EFFECT_DAMAGE: "DAMAGE",
            DEATH_LINK_EFFECT_TIMER_DRAIN: "TIMER",
            DEATH_LINK_EFFECT_LOSE_ALL_COINS: "COINS",
        }[effect]
        logger.info("DL: %s.", notification_name)
        return True

    @staticmethod
    def _timer_is_counting(previous_timer: int | None, timer: int) -> bool:
        """Return whether the verified level timer decreased since the last poll."""
        return previous_timer is not None and 0 < timer < previous_timer

    async def _read_lives_and_timer(
        self,
        ctx: BizHawkClientContext,
    ) -> tuple[int, int, int, int, int, int, int, int] | None:
        """Read death state plus Lua-visible protection charges."""
        from worlds._bizhawk import read

        try:
            result = await read(
                ctx.bizhawk_ctx,
                [
                    (ADDR_LIVES, 1, MEMORY_DOMAIN),
                    (ADDR_TIMER, 4, MEMORY_DOMAIN),
                    (ADDR_POWERUP_LEVEL, 1, MEMORY_DOMAIN),
                    (ADDR_AP_TRAP_SHIELD_COUNT, 1, MEMORY_DOMAIN),
                    (ADDR_AP_LIFE_INSURANCE_COUNT, 1, MEMORY_DOMAIN),
                    (ADDR_AP_INSURED_DEATH_SEQUENCE, 1, MEMORY_DOMAIN),
                    (ADDR_AP_RETURN_TO_MAP_DEATH_SEQUENCE, 1, MEMORY_DOMAIN),
                    (ADDR_STAGE_EXIT_FLAGS, 4, MEMORY_DOMAIN),
                ],
            )
        except Exception:
            logger.exception("Failed to read NSMBDS Death Link state.")
            return None
        if len(result) != 8 or [len(value) for value in result] != [1, 4, 1, 1, 1, 1, 1, 4]:
            logger.warning("Received invalid NSMBDS Death Link state data.")
            return None
        return (
            result[0][0],
            struct.unpack("<I", bytes(result[1]))[0],
            result[2][0],
            result[3][0],
            result[4][0],
            result[5][0],
            result[6][0],
            struct.unpack("<I", bytes(result[7]))[0],
        )

    async def _handle_death_link(self, ctx: BizHawkClientContext) -> None:
        """Apply queued incoming Death Links and send eligible local deaths."""
        state = await self._read_lives_and_timer(ctx)
        if state is None:
            return
        (
            lives,
            timer,
            powerup,
            shield_count,
            insurance_count,
            insured_death_sequence,
            return_to_map_death_sequence,
            exit_flags,
        ) = state
        self._pending_trap_shields = shield_count
        self._pending_life_insurance = insurance_count
        insured_death = (
            self._last_insured_death_sequence is not None
            and insured_death_sequence != self._last_insured_death_sequence
        )
        self._last_insured_death_sequence = insured_death_sequence
        return_to_map_death = (
            self._last_return_to_map_death_sequence is not None
            and return_to_map_death_sequence != self._last_return_to_map_death_sequence
        )
        self._last_return_to_map_death_sequence = return_to_map_death_sequence
        timer_is_counting = self._timer_is_counting(self._last_timer, timer)
        self._last_timer = timer

        return_to_map_active = bool(exit_flags & STAGE_EXIT_RETURN_TO_MAP_MASK)
        # The direct bit covers a same-poll life loss. The sticky Lua sequence
        # covers the common case where the 500 ms client poll misses that bit.
        # This is deliberately a snapshot, not a latch: the sequence is emitted
        # only for an actual Return-to-Map life loss, so stale exits cannot hide
        # a later real death.
        self._return_to_map_pending = return_to_map_active or return_to_map_death

        if timer_is_counting:
            self._in_level_grace_polls = 16
        elif self._in_level_grace_polls:
            self._in_level_grace_polls -= 1

        enabled = bool(ctx.slot_data and ctx.slot_data.get("death_link", False))
        if enabled and self._pending_death_link and timer_is_counting and not self._return_to_map_pending:
            await self._apply_pending_death_link(ctx, timer, powerup)

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
        if self._suppress_next_local_death:
            self._suppress_next_local_death = False
            logger.info("Suppressed outgoing Death Link caused by an incoming Death Link.")
            return
        if not self._in_level_grace_polls:
            logger.info("Ignored life loss outside a recently active level timer.")
            return
        await ctx.send_death("Mario died.")
        logger.info("Sent Death Link for a local Mario death.")
