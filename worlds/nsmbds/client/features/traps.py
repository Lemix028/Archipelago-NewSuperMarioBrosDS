"""Live-verified trap behavior for the NSMBDS BizHawk client."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING

from ...data.ram_addresses import (
    ADDR_COINS,
    ADDR_INVENTORY_ITEM,
    ADDR_MARIO_MAX_SPEED,
    ADDR_TIMER,
    ADDR_X_SPEED,
    HYPER_SPEED_MULTIPLIER,
    MEMORY_DOMAIN,
    SLOW_SPEED_MULTIPLIER,
    SPEED_TRAP_DURATION_SECONDS,
    TIMER_UNITS_PER_SECOND,
)

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

TIMER_DRAIN_SECONDS = 50
TIMER_DRAIN_UNITS = TIMER_DRAIN_SECONDS * TIMER_UNITS_PER_SECOND
COIN_TAX_AMOUNT = 10


class TrapHandlingMixin:
    """Apply verified traps without interfering with regular item handling."""

    def _queue_timer_drain(self) -> None:
        """Queue one Timer Drain for the next active level."""
        self._pending_timer_drains += 1
        logger.info("Queued Timer Drain until the level timer is active.")

    @staticmethod
    def _drained_timer_value(current_timer: int) -> int:
        """Return the timer value after one clamped 50-second drain."""
        return max(0, current_timer - TIMER_DRAIN_UNITS)

    async def _apply_pending_timer_drains(self, ctx: "BizHawkClientContext") -> None:
        """Apply one queued Timer Drain only while the verified level timer counts down."""
        if not self._pending_timer_drains or not self._in_level_grace_polls:
            return

        from worlds._bizhawk import guarded_read, guarded_write

        current_result = await guarded_read(
            ctx.bizhawk_ctx,
            [(ADDR_TIMER, 4, MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if current_result is None or len(current_result) != 1 or len(current_result[0]) != 4:
            logger.debug("Deferred Timer Drain until the level timer can be read safely.")
            return

        current_timer = struct.unpack("<I", current_result[0])[0]
        new_timer = self._drained_timer_value(current_timer)
        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_TIMER, list(struct.pack("<I", new_timer)), MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if not applied:
            logger.debug("Deferred Timer Drain until the timer write succeeds.")
            return

        self._pending_timer_drains -= 1
        self._pending_timer_drain_notices += 1
        logger.info(
            "Applied Timer Drain: %d -> %d timer units (%d second(s)).",
            current_timer,
            new_timer,
            TIMER_DRAIN_SECONDS,
        )

    async def _apply_coin_thief(self, ctx: "BizHawkClientContext") -> bool:
        """Set the local coin counter to zero through the verified coin address."""
        from worlds._bizhawk import guarded_write

        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_COINS, [0], MEMORY_DOMAIN)],
            self._game_data_guards(),
        )
        if applied:
            self._pending_coin_thief_notices += 1
            logger.info("Applied Coin Thief by setting the local coin counter to zero.")
        return applied

    async def _apply_powerup_pickpocket(self, ctx: "BizHawkClientContext") -> bool:
        """Empty the reserve Power-Up slot without touching queued AP Power-Ups."""
        from worlds._bizhawk import guarded_read, guarded_write

        guards = self._game_data_guards()
        current_result = await guarded_read(
            ctx.bizhawk_ctx,
            [(ADDR_INVENTORY_ITEM, 1, MEMORY_DOMAIN)],
            guards,
        )
        if (
            current_result is None
            or len(current_result) != 1
            or len(current_result[0]) != 1
        ):
            return False

        current_item = current_result[0][0]
        if current_item == 0:
            self._pending_powerup_pickpocket_notices += 1
            logger.info("Power-Up Pickpocket Trap found an empty reserve slot.")
            return True

        applied = await guarded_write(
            ctx.bizhawk_ctx,
            [(ADDR_INVENTORY_ITEM, [0], MEMORY_DOMAIN)],
            [*guards, (ADDR_INVENTORY_ITEM, [current_item], MEMORY_DOMAIN)],
        )
        if applied:
            self._pending_powerup_pickpocket_notices += 1
            logger.info(
                "Power-Up Pickpocket Trap cleared reserve item value 0x%02X.",
                current_item,
            )
        return applied

    async def _apply_coin_tax(self, ctx: "BizHawkClientContext") -> bool:
        """Remove up to ten coins without underflowing the one-byte counter."""
        applied = await self._adjust_byte(ctx, ADDR_COINS, -COIN_TAX_AMOUNT, 99)
        if applied:
            self._pending_coin_tax_notices += 1
            logger.info("Applied Coin Tax by removing up to %d coins.", COIN_TAX_AMOUNT)
        return applied

    def _queue_speed_trap(self, multiplier: float) -> None:
        """Queue one speed trap (Hyper Speed or Slow Speed)."""
        if multiplier > 1.0:
            self._pending_hyper_speed_traps += 1
            logger.debug("Queued Hyper Speed Trap until active in a level.")
        else:
            self._pending_slow_speed_traps += 1
            logger.debug("Queued Slow Speed Trap until active in a level.")

    def _queue_walljump_lock_trap(self) -> None:
        """Queue one Walljump Lock Trap."""
        self._pending_walljump_lock_traps += 1
        logger.debug("Queued Walljump Lock Trap until active in a level.")

    def _queue_no_jump_trap(self) -> None:
        """Queue one No-Jump Trap."""
        self._pending_no_jump_traps += 1
        logger.debug("Queued No-Jump Trap until active in a level.")

    def _queue_reverse_controls_trap(self) -> None:
        """Queue one Reverse Controls Trap."""
        self._pending_reverse_controls_traps += 1
        logger.debug("Queued Reverse Controls Trap until active in a level.")

    def _queue_no_sprint_trap(self) -> None:
        """Queue one No Sprint Trap."""
        self._pending_no_sprint_traps += 1
        logger.debug("Queued No Sprint Trap until active in a level.")

    def _queue_button_roulette_trap(self) -> None:
        """Queue one Button Roulette Trap."""
        self._pending_button_roulette_traps += 1
        logger.debug("Queued Button Roulette Trap until active in a level.")

    def _queue_ice_shoes_trap(self) -> None:
        """Queue one Ice Shoes Trap."""
        self._pending_ice_shoes_traps += 1
        logger.debug("Queued Ice Shoes Trap until active in a level.")

    def _queue_heavy_mario_trap(self) -> None:
        """Queue one Heavy Mario Trap."""
        self._pending_heavy_mario_traps += 1
        logger.debug("Queued Heavy Mario Trap until active in a level.")

    def _queue_auto_run_trap(self) -> None:
        """Queue one Auto Run Trap."""
        self._pending_auto_run_traps += 1
        logger.debug("Queued Auto Run Trap until active in a level.")

    def _queue_sticky_buttons_trap(self) -> None:
        """Queue one Sticky Buttons Trap."""
        self._pending_sticky_buttons_traps += 1
        logger.debug("Queued Sticky Buttons Trap until active in a level.")

    def _queue_camera_drift_trap(self) -> None:
        """Queue one Camera Drift Trap."""
        self._pending_camera_drift_traps += 1
        logger.debug("Queued Camera Drift Trap until active in a level.")

    def _queue_screen_flip_trap(self) -> None:
        """Queue one Screen Flip Trap."""
        self._pending_screen_flip_traps += 1
        logger.debug("Queued Screen Flip Trap until active in a level.")

    def _queue_camera_sway_trap(self) -> None:
        """Queue one Camera Sway Trap."""
        self._pending_camera_sway_traps += 1
        logger.debug("Queued Camera Sway Trap until active in a level.")

    def _queue_boo_curse_trap(self) -> None:
        """Queue one Boo Curse Trap."""
        self._pending_boo_curse_traps += 1
        logger.debug("Queued Boo Curse Trap until active in a level.")

    def _queue_im_stuck_trap(self) -> None:
        """Queue one short I'm Stuck Trap."""
        self._pending_im_stuck_traps += 1
        logger.debug("Queued I'm Stuck Trap until active in a level.")

    def _queue_screen_tint_trap(self) -> None:
        """Queue one Screen Tint Trap."""
        self._pending_screen_tint_traps += 1
        logger.debug("Queued Screen Tint Trap until active in a level.")

    def _queue_retro_filter_trap(self) -> None:
        """Queue one Retro Filter Trap."""
        self._pending_retro_filter_traps += 1
        logger.debug("Queued Retro Filter Trap until active in a level.")

    def _queue_spotlight_trap(self) -> None:
        """Queue one Spotlight Trap."""
        self._pending_spotlight_traps += 1
        logger.debug("Queued Spotlight Trap until active in a level.")

    def _queue_ground_clap_trap(self) -> None:
        """Queue one Ground Clap Trap."""
        self._pending_ground_clap_traps += 1
        logger.debug("Queued Ground Clap Trap until active in a level.")

    def _queue_head_bonk_trap(self) -> None:
        """Queue one Head Bonk Trap."""
        self._pending_head_bonk_traps += 1
        logger.debug("Queued Head Bonk Trap until active in a level.")

    def _queue_crazy_pixels_trap(self) -> None:
        """Queue one Crazy Pixels Trap."""
        self._pending_crazy_pixels_traps += 1
        logger.debug("Queued Crazy Pixels Trap until active in a level.")

    def _queue_no_turnaround_trap(self) -> None:
        """Queue one No Turnaround Trap."""
        self._pending_no_turnaround_traps += 1
        logger.debug("Queued No Turnaround Trap until active in a level.")

    def _queue_bonk_trap(self) -> None:
        """Queue one Bonk / Damage Trap."""
        self._pending_bonk_traps += 1
        logger.debug("Queued Bonk Trap until active in a level.")

    async def _apply_pending_speed_traps(self, ctx: "BizHawkClientContext") -> None:
        """Send one trap only while the Lua trigger mailbox is idle."""
        from ...data.ram_addresses import ADDR_AP_TRAP_TRIGGER
        from worlds._bizhawk import guarded_write

        guards = [
            *self._game_data_guards(),
            (ADDR_AP_TRAP_TRIGGER, [0], MEMORY_DOMAIN),
        ]

        for counter_name, trigger_code, label in (
            ("_pending_coin_tax_notices", 15, "Coin Tax"),
            ("_pending_timer_drain_notices", 16, "Timer Drain"),
            ("_pending_coin_thief_notices", 17, "Coin Thief"),
            ("_pending_powerup_pickpocket_notices", 33, "Power-Up Pickpocket"),
        ):
            if getattr(self, counter_name, 0) <= 0:
                continue
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [trigger_code], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                setattr(self, counter_name, getattr(self, counter_name) - 1)
                logger.debug(
                    "Sent %s notification trigger (0x%02X) to RAM 0x%08X.",
                    label,
                    trigger_code,
                    ADDR_AP_TRAP_TRIGGER,
                )
            return

        if getattr(self, "_pending_crazy_pixels_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [31], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_crazy_pixels_traps -= 1
                logger.info("Triggered Crazy Pixels Trap!")
                logger.debug(
                    "Sent Crazy Pixels Trap trigger (0x1F) to RAM 0x%08X.",
                    ADDR_AP_TRAP_TRIGGER,
                )
            return

        if getattr(self, "_pending_hyper_speed_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [1], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_hyper_speed_traps -= 1
                logger.info("Triggered Hyper Speed Trap!")
                logger.debug("Sent Hyper Speed Trap trigger (0x01) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_slow_speed_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [2], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_slow_speed_traps -= 1
                logger.info("Triggered Slow Speed Trap!")
                logger.debug("Sent Slow Speed Trap trigger (0x02) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_walljump_lock_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [3], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_walljump_lock_traps -= 1
                logger.info("Triggered Walljump Lock Trap!")
                logger.debug("Sent Walljump Lock Trap trigger (0x03) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_no_jump_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [5], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_no_jump_traps -= 1
                logger.info("Triggered No-Jump Trap!")
                logger.debug("Sent No-Jump Trap trigger (0x05) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_reverse_controls_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [6], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_reverse_controls_traps -= 1
                logger.info("Triggered Reverse Controls Trap!")
                logger.debug("Sent Reverse Controls Trap trigger (0x06) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_no_sprint_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [9], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_no_sprint_traps -= 1
                logger.info("Triggered No Sprint Trap!")
                logger.debug("Sent No Sprint Trap trigger (0x09) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_button_roulette_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [10], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_button_roulette_traps -= 1
                logger.info("Triggered Button Roulette Trap!")
                logger.debug("Sent Button Roulette Trap trigger (0x0A) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_ice_shoes_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [11], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_ice_shoes_traps -= 1
                logger.info("Triggered Ice Shoes Trap!")
                logger.debug("Sent Ice Shoes Trap trigger (0x0B) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_heavy_mario_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [12], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_heavy_mario_traps -= 1
                logger.info("Triggered Heavy Mario Trap!")
                logger.debug("Sent Heavy Mario Trap trigger (0x0C) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_auto_run_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [13], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_auto_run_traps -= 1
                logger.info("Triggered Auto Run Trap!")
                logger.debug("Sent Auto Run Trap trigger (0x0D) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        if getattr(self, "_pending_sticky_buttons_traps", 0) > 0:
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [14], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_sticky_buttons_traps -= 1
                logger.info("Triggered Sticky Buttons Trap!")
                logger.debug("Sent Sticky Buttons Trap trigger (0x0E) to RAM 0x%08X.", ADDR_AP_TRAP_TRIGGER)
            return

        for counter_name, trigger_code, label in (
            ("_pending_camera_drift_traps", 19, "Camera Drift"),
            ("_pending_screen_flip_traps", 20, "Screen Flip"),
            ("_pending_camera_sway_traps", 21, "Camera Sway"),
            ("_pending_boo_curse_traps", 22, "Boo Curse"),
            ("_pending_im_stuck_traps", 23, "I'm Stuck"),
            ("_pending_screen_tint_traps", 24, "Screen Tint"),
            ("_pending_retro_filter_traps", 25, "Retro Filter"),
            ("_pending_spotlight_traps", 26, "Spotlight"),
            ("_pending_no_turnaround_traps", 32, "No Turnaround"),
        ):
            if getattr(self, counter_name, 0) <= 0:
                continue
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [trigger_code], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                setattr(self, counter_name, getattr(self, counter_name) - 1)
                logger.info("Triggered %s Trap!", label)
                logger.debug(
                    "Sent %s Trap trigger (0x%02X) to RAM 0x%08X.",
                    label,
                    trigger_code,
                    ADDR_AP_TRAP_TRIGGER,
                )
            return

        for counter_name, lethal_code, safe_code, label in (
            ("_pending_ground_clap_traps", 27, 28, "Ground Clap"),
            ("_pending_head_bonk_traps", 29, 30, "Head Bonk"),
        ):
            if getattr(self, counter_name, 0) <= 0:
                continue
            can_kill = getattr(self, "_bonk_trap_can_kill", True)
            trigger_code = lethal_code if can_kill else safe_code
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [trigger_code], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                setattr(self, counter_name, getattr(self, counter_name) - 1)
                logger.info("Triggered %s Trap!", label)
                logger.debug(
                    "Sent %s Trap trigger (0x%02X, can_kill=%s) to RAM 0x%08X.",
                    label,
                    trigger_code,
                    can_kill,
                    ADDR_AP_TRAP_TRIGGER,
                )
            return

        if getattr(self, "_pending_bonk_traps", 0) > 0:
            can_kill = getattr(self, "_bonk_trap_can_kill", True)
            code = 7 if can_kill else 8
            applied = await guarded_write(
                ctx.bizhawk_ctx,
                [(ADDR_AP_TRAP_TRIGGER, [code], MEMORY_DOMAIN)],
                guards,
            )
            if applied:
                self._pending_bonk_traps -= 1
                logger.info("Triggered Bonk Trap!")
                logger.debug("Sent Bonk Trap trigger (0x%02X, can_kill=%s) to RAM 0x%08X.", code, can_kill, ADDR_AP_TRAP_TRIGGER)
            return
