"""Retry consumable RAM writes using the same persisted transaction."""

from __future__ import annotations

import base64
import secrets


class ItemTransactionPending(Exception):
    """An unconfirmed item write must finish before another item is attempted."""


class ItemTransactionMixin:
    @staticmethod
    def _validate_item_transaction(pending):
        if pending is None:
            return None
        from ...items import INVENTORY_RAM_VALUES, item_id_to_name
        from ...data.ram_addresses import ADDR_COINS, ADDR_INVENTORY_ITEM, ADDR_LIVES, MEMORY_DOMAIN

        if not isinstance(pending, dict) or pending.get("owner") not in {"network", "deferred"}:
            raise ValueError("Invalid pending item transaction")
        name = item_id_to_name.get(pending.get("item_id"))
        expected_address = (ADDR_INVENTORY_ITEM if name in INVENTORY_RAM_VALUES else
                            ADDR_LIVES if name in {"1-Up Mushroom", "3-Up Moon"} else
                            ADDR_COINS if name in {"Small Coin Bundle", "Coin Bundle", "Large Coin Bundle"} else None)
        request = pending.get("request", {})
        if expected_address is None or request.get("type") != "NSMBDS_ITEM_WRITE":
            raise ValueError("Invalid consumable transaction")
        token = base64.b64decode(request["token"], validate=True)
        if len(token) != 8 or not any(token) or base64.b64encode(token).decode("ascii") != request["token"]:
            raise ValueError("Invalid transaction token")
        writes = request["writes"]
        if len(writes) != 1 or writes[0]["address"] != expected_address or writes[0]["domain"] != MEMORY_DOMAIN:
            raise ValueError("Invalid transaction target")
        if len(base64.b64decode(writes[0]["value"], validate=True)) != 1:
            raise ValueError("Invalid transaction value")
        for guard in request["guards"]:
            expected = base64.b64decode(guard["expected_data"], validate=True)
            if guard["domain"] != MEMORY_DOMAIN or not isinstance(guard["address"], int) or not (
                    0 <= guard["address"] <= 0x400000 - len(expected)):
                raise ValueError("Invalid transaction guard")
        return pending

    async def _send_pending_item_transaction(self, ctx) -> bool:
        from worlds._bizhawk import send_requests

        pending = self._pending_item_transaction
        if self._persist_item_cursor() is False:
            raise ItemTransactionPending("Could not persist the pending item write")
        responses = await send_requests(ctx.bizhawk_ctx, [pending["request"]])
        if self._pending_item_transaction is not pending:
            raise ItemTransactionPending("Item session changed while the write was in flight")
        response = responses[0]
        if response.get("type") != "NSMBDS_ITEM_WRITE_RESPONSE" or type(response.get("value")) is not bool:
            raise ItemTransactionPending("Invalid consumable transaction response")
        # Keep the journal until the caller also advances its cursor/removes the
        # deferred entry and persists that state. A crash can then safely retry.
        return response["value"]

    async def _write_item_transaction(self, ctx, item_id, writes, guards) -> bool:
        pending = self._pending_item_transaction
        if pending is None:
            token = secrets.token_bytes(8)
            while not any(token):
                token = secrets.token_bytes(8)
            pending = {
                "item_id": item_id,
                "owner": getattr(self, "_item_transaction_owner", "network"),
                "request": {
                    "type": "NSMBDS_ITEM_WRITE",
                    "token": base64.b64encode(token).decode("ascii"),
                    "writes": [{"address": address, "value": base64.b64encode(bytes(value)).decode("ascii"),
                                "domain": domain} for address, value, domain in writes],
                    "guards": [{"address": address, "expected_data": base64.b64encode(bytes(value)).decode("ascii"),
                                "domain": domain} for address, value, domain in guards],
                },
            }
            self._pending_item_transaction = pending
        if pending["item_id"] != item_id:
            raise ItemTransactionPending("Another consumable transaction is still pending")
        return await self._send_pending_item_transaction(ctx)
