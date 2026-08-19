"""Central reconciliation of Archipelago-controlled overworld RAM state."""

from __future__ import annotations

import logging
import struct
from typing import TYPE_CHECKING, Sequence

from ...items import ITEM_TABLE, KEY_ITEM_NAMES
from ...data.ram_addresses import (
    ADDR_AP_STAR_COIN_GATE_HOOK_MARKER,
    ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
    ADDR_AP_STAR_COIN_CURRENCY_MAILBOX,
    ADDR_LEVEL_DATA_BASE,
    ADDR_W8_CASTLE_APPROACH_PATH,
    ADDR_WORLD_FLAGS_BASE,
    AP_STAR_COIN_GATE_HOOK_MARKER,
    AP_STAR_COIN_GATE_PERMIT_MASK_SIZE,
    AP_STAR_COIN_CURRENCY_MAGIC,
    KEY_PATH_GATE_ADDRESSES,
    MEMORY_DOMAIN,
    W8_CASTLE_APPROACH_PATH_MASK,
    WORLD_ENABLED_VALUE,
)
from ...data.star_coin_gates import STAR_COIN_GATES

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext


logger = logging.getLogger("NSMBDS")

WORLD_ACCESS_ITEMS = (
    "Desert Pass",
    "Isle Pass",
    "Jungle Pass",
    "Glacier Pass",
    "Mountain Pass",
    "Cloud Pass",
    "Volcano Pass",
)
WORLD_FLAG_BYTES = 16


class OverworldStateReconcilerMixin:
    """Derive and atomically restore every AP-owned overworld byte."""

    @staticmethod
    def _star_coin_permit_masks(ctx: "BizHawkClientContext") -> bytes:
        masks = bytearray(AP_STAR_COIN_GATE_PERMIT_MASK_SIZE)
        gate_mode = int(ctx.slot_data.get("star_coin_gate_mode", 0))
        if gate_mode not in (1, 2):
            for gate in STAR_COIN_GATES:
                masks[gate.permit_byte_index] |= 1 << gate.permit_bit
        elif gate_mode == 1:
            permit_id = ITEM_TABLE["Progressive Gate Pass"][0]
            permit_count = min(
                sum(item.item == permit_id for item in ctx.items_received),
                len(STAR_COIN_GATES),
            )
            for gate in STAR_COIN_GATES[:permit_count]:
                masks[gate.permit_byte_index] |= 1 << gate.permit_bit
        else:
            received_ids = {item.item for item in ctx.items_received}
            for gate in STAR_COIN_GATES:
                if ITEM_TABLE[gate.permit_item_name][0] in received_ids:
                    masks[gate.permit_byte_index] |= 1 << gate.permit_bit
        return bytes(masks)

    @staticmethod
    def _level_byte(level_data: bytes, address: int) -> int | None:
        offset = address - ADDR_LEVEL_DATA_BASE
        if 0 <= offset < len(level_data):
            return level_data[offset]
        return None

    def _star_coin_balances(
        self,
        ctx: "BizHawkClientContext",
    ) -> tuple[int, int, int]:
        """Return lifetime, spent, and available AP Star Coins."""
        star_coin_id = ITEM_TABLE["Star Coin"][0]
        lifetime = sum(item.item == star_coin_id for item in ctx.items_received)
        spent = 0
        for gate_index, gate in enumerate(STAR_COIN_GATES):
            if self._gate_purchase_mask & (1 << gate_index):
                spent += gate.star_coin_cost
        spent = max(spent, self._gate_purchase_spent_floor)
        return lifetime, spent, max(0, lifetime - spent)

    async def _reconcile_overworld_state(
        self,
        ctx: "BizHawkClientContext",
        level_data: bytes,
    ) -> None:
        """Restore AP-owned world flags, paths, and native Permit masks."""
        from worlds._bizhawk import guarded_read, guarded_write

        # The permit mailbox lives inside Overlay 8. Guard with the hook cave
        # marker bytes so we never read/write it during the loading screen.
        overlay8_guard = [
            (ADDR_AP_STAR_COIN_GATE_HOOK_MARKER, list(AP_STAR_COIN_GATE_HOOK_MARKER), MEMORY_DOMAIN),
        ]
        star_coin_items_enabled = bool(ctx.slot_data.get("star_coin_items", False))
        external_reads = [
            (ADDR_WORLD_FLAGS_BASE, WORLD_FLAG_BYTES, MEMORY_DOMAIN),
            (
                ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
                AP_STAR_COIN_GATE_PERMIT_MASK_SIZE,
                MEMORY_DOMAIN,
            ),
            (ADDR_AP_STAR_COIN_CURRENCY_MAILBOX, 8, MEMORY_DOMAIN),
        ]
        current_external = await guarded_read(
            ctx.bizhawk_ctx,
            external_reads,
            [*self._game_data_guards(), *overlay8_guard],
        )
        if (
            current_external is None
            or len(current_external) != len(external_reads)
            or len(current_external[0]) != WORLD_FLAG_BYTES
            or len(current_external[1]) != AP_STAR_COIN_GATE_PERMIT_MASK_SIZE
            or len(current_external[2]) != 8
        ):
            logger.debug("Deferred overworld reconciliation: Overlay 8 not yet loaded.")
            return

        world_flags = current_external[0]
        current_permit_masks = current_external[1]
        current_currency_mailbox = current_external[2]
        received_ids = {item.item for item in ctx.items_received}
        writes: list[tuple[int, list[int], str]] = []
        target_guards: list[tuple[int, Sequence[int], str]] = []
        desired_by_address: dict[int, bytes] = {}
        current_by_address: dict[int, bytes] = {}

        def request_write(address: int, current: bytes, target: bytes) -> None:
            if current == target:
                return
            previous = desired_by_address.get(address)
            if previous is not None and previous != target:
                raise ValueError(
                    f"Conflicting overworld targets for 0x{address:06X}: "
                    f"{previous.hex()} and {target.hex()}"
                )
            desired_by_address[address] = target
            current_by_address[address] = current

        # World Access items only enable worlds; vanilla/save progress may also
        # legitimately enable them, so missing items never force a relock.
        for world_number, item_name in enumerate(WORLD_ACCESS_ITEMS, start=2):
            if ITEM_TABLE[item_name][0] not in received_ids:
                continue
            offset = (world_number - 1) * 2
            current = bytes(world_flags[offset:offset + 2])
            request_write(
                ADDR_WORLD_FLAGS_BASE + offset,
                current,
                struct.pack("<H", WORLD_ENABLED_VALUE),
            )

        # Physical Tower/Castle keys fully own their verified path bytes.
        if bool(ctx.slot_data.get("tower_castle_keys", True)):
            for key_name in KEY_ITEM_NAMES:
                target = 0xC0 if ITEM_TABLE[key_name][0] in received_ids else 0x00
                for address in KEY_PATH_GATE_ADDRESSES.get(key_name, ()):
                    current = self._level_byte(level_data, address)
                    if current is not None:
                        request_write(address, bytes([current]), bytes([target]))

        permit_masks = self._star_coin_permit_masks(ctx)
        request_write(
            ADDR_AP_STAR_COIN_GATE_PERMIT_MASK,
            bytes(current_permit_masks),
            permit_masks,
        )

        if star_coin_items_enabled:
            # Reopen every DataStorage-confirmed purchase after loading an
            # older savestate. Missing bits never close paths.
            for gate_index, gate in enumerate(STAR_COIN_GATES):
                if not self._gate_purchase_mask & (1 << gate_index):
                    continue
                current_path = self._level_byte(level_data, gate.path_address)
                if current_path is not None:
                    request_write(
                        gate.path_address,
                        bytes([current_path]),
                        bytes([current_path | 0xC0]),
                    )
            lifetime, spent, available = self._star_coin_balances(ctx)
            self._star_coin_lifetime = lifetime
            self._star_coin_spent = spent
            self._star_coin_available = available
            currency_mailbox = AP_STAR_COIN_CURRENCY_MAGIC + struct.pack("<I", available)
        else:
            # A zero mode byte makes the native getter run its original code.
            currency_mailbox = bytes(8)
        request_write(
            ADDR_AP_STAR_COIN_CURRENCY_MAILBOX,
            bytes(current_currency_mailbox),
            currency_mailbox,
        )

        # Permits authorize the native purchase interaction via ARM ROM hooks.
        # The native ROM hook checks ADDR_AP_STAR_COIN_GATE_PERMIT_MASK and displays
        # BMG message 15 ("A Star Coin Gate Pass is required...") when missing.

        # The selected goal owns only the two approach-path bits.
        final_gate_open = self._final_castle_gate_should_open(ctx)
        current_final_gate = self._level_byte(level_data, ADDR_W8_CASTLE_APPROACH_PATH)
        if final_gate_open is not None and current_final_gate is not None:
            if final_gate_open:
                target = current_final_gate | W8_CASTLE_APPROACH_PATH_MASK
            else:
                target = current_final_gate & ~W8_CASTLE_APPROACH_PATH_MASK
            request_write(
                ADDR_W8_CASTLE_APPROACH_PATH,
                bytes([current_final_gate]),
                bytes([target]),
            )

        for address, target in desired_by_address.items():
            current = current_by_address[address]
            writes.append((address, list(target), MEMORY_DOMAIN))
            target_guards.append((address, list(current), MEMORY_DOMAIN))
        if not writes:
            return

        applied = await guarded_write(
            ctx.bizhawk_ctx,
            writes,
            [*self._game_data_guards(), *overlay8_guard, *target_guards],
        )
        if applied:
            logger.info("Reconciled %d overworld RAM value(s).", len(writes))
        else:
            logger.debug("Deferred overworld reconciliation because target RAM changed.")
