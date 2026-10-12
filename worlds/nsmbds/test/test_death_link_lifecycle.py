"""DeathLink lifecycle regressions independent of death statistics."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from worlds.nsmbds.client import NSMBDSClient
from worlds.nsmbds.client.features.death_link import (
    DEATH_LINK_EFFECT_DAMAGE, DEATH_LINK_EFFECT_DEATH, DEATH_LINK_EFFECT_TIMER_DRAIN,
)
from worlds.nsmbds.data import ram_addresses as ram


class TestDeathLinkLifecycle(IsolatedAsyncioTestCase):
    def setUp(self):
        self.ctx = SimpleNamespace(
            slot_data={"death_link": True}, bizhawk_ctx=object(), send_death=AsyncMock(),
        )
        self.client = NSMBDSClient()
        self.client._last_lives = 5
        self.client._last_timer = 101 * ram.TIMER_UNITS_PER_SECOND
        self.client._last_insured_death_sequence = 0
        self.client._last_return_to_map_death_sequence = 0

    def incoming(self, *, timestamp=1.0):
        self.client._queue_incoming_death_link(self.ctx, "Luigi")

    async def poll(self, *, lives=5, timer=100, insured=0, returned=0, flags=0, powerup=0, freeze=0, menu=0):
        self.client._read_lives_and_timer = AsyncMock(return_value=(
            lives, timer * ram.TIMER_UNITS_PER_SECOND, powerup, 0, 0, insured, returned, flags, freeze, menu,
        ))
        await self.client._handle_death_link(self.ctx)

    async def test_pending_deathlink_never_claims_an_already_observed_death(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)) as write:
            await self.poll(lives=4)
            write.assert_not_awaited()
            self.assertTrue(self.client._pending_death_link)
            self.ctx.send_death.assert_awaited_once()
            await self.poll(lives=4, timer=300)
            await self.poll(lives=4, timer=299)
            write.assert_awaited_once()
            self.assertFalse(self.client._pending_death_link)


    async def test_single_pending_effect_waits_through_menu_and_failed_guard(self):
        self.incoming()
        self.ctx.slot_data["death_link_effect"] = DEATH_LINK_EFFECT_DAMAGE
        self.incoming(timestamp=2.0)
        self.assertEqual(self.client._pending_death_link_effect, DEATH_LINK_EFFECT_DEATH)
        with patch("worlds._bizhawk.guarded_write", AsyncMock(side_effect=[False, True])) as write:
            await self.poll(timer=101)
            await self.poll(timer=101)
            write.assert_not_awaited()
            await self.poll(timer=100)
            self.assertTrue(self.client._pending_death_link)
            self.assertFalse(self.client._suppress_next_local_death)
            await self.poll(timer=99)
            self.assertFalse(self.client._pending_death_link)
            guards = write.await_args.args[2]
            for address, value in ((ram.ADDR_STAGE_MENU_OPEN, [0]), (ram.ADDR_STAGE_FREEZE_FLAG, [0]),
                                   (ram.ADDR_STAGE_EXIT_FLAGS, [0, 0, 0, 0])):
                self.assertIn((address, value, ram.MEMORY_DOMAIN), guards)


    async def test_incoming_lethal_effect_does_not_echo(self):
        for effect in (DEATH_LINK_EFFECT_DEATH, DEATH_LINK_EFFECT_DAMAGE, DEATH_LINK_EFFECT_TIMER_DRAIN):
            with self.subTest(effect=effect):
                self.client._last_lives = 5
                self.client._last_timer = 76 * ram.TIMER_UNITS_PER_SECOND
                self.client._pending_death_link = True
                self.client._pending_death_link_effect = effect
                with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
                    await self.poll(timer=75)
                await self.poll(lives=4, timer=0)
                await self.poll(lives=4, timer=0)
        self.ctx.send_death.assert_not_awaited()


    async def test_long_paused_incoming_death_is_still_suppressed(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
            await self.poll()
        for _ in range(40):
            await self.poll(timer=0)
        self.assertTrue(self.client._suppress_next_local_death)
        await self.poll(lives=4, timer=0)
        self.ctx.send_death.assert_not_awaited()


    async def test_long_pause_preserves_normal_death_context(self):
        await self.poll()
        for _ in range(40):
            await self.poll(menu=1, freeze=1)
        await self.poll(lives=4, timer=0)
        self.ctx.send_death.assert_awaited_once()


    async def test_pause_and_stage_exit_defer_pending_effect(self):
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)) as write:
            await self.poll(timer=100, menu=1)
            await self.poll(timer=99, freeze=1)
            await self.poll(timer=98, flags=1)
            write.assert_not_awaited()
            self.assertTrue(self.client._pending_death_link)
            await self.poll(timer=97)
            write.assert_awaited_once()


    async def test_life_delivery_refresh_keeps_next_death_visible(self):
        await self.poll(lives=4)
        with patch("worlds._bizhawk.guarded_read", AsyncMock(return_value=[bytes([4])])), \
                patch.object(self.client, "_write_item_transaction", AsyncMock(return_value=True)):
            await self.client._adjust_byte(self.ctx, ram.ADDR_LIVES, 1, 99, 123)
        self.assertTrue(self.client._life_delivery_needs_observation)
        await self.poll(lives=5, timer=99)
        self.assertFalse(self.client._life_delivery_needs_observation)
        await self.poll(lives=4, timer=98)
        self.assertEqual(self.ctx.send_death.await_count, 2)


    async def test_nonlethal_damage_cannot_suppress_later_unrelated_death(self):
        self.ctx.slot_data["death_link_effect"] = DEATH_LINK_EFFECT_DAMAGE
        self.incoming()
        with patch("worlds._bizhawk.guarded_write", AsyncMock(return_value=True)):
            await self.poll()
        # Lua may find a powered-up Mario by the time it consumes this trigger.
        await self.poll(timer=100, powerup=2)
        self.assertTrue(self.client._suppress_next_local_death)
        await self.poll(timer=98, powerup=2)
        self.assertFalse(self.client._suppress_next_local_death)
        await self.poll(lives=4, timer=97)
        self.ctx.send_death.assert_awaited_once()


    async def test_return_to_map_clears_echo_expectation(self):
        self.client._suppress_next_local_death = True
        await self.poll(lives=4, returned=1)
        self.assertFalse(self.client._suppress_next_local_death)
        await self.poll(lives=3, timer=99, returned=1)
        self.ctx.send_death.assert_awaited_once()
