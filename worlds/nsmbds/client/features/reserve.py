"""One-copy reserve selections shared by Overview, Settings and commands."""

from __future__ import annotations

import logging

from ...items import INVENTORY_RAM_VALUES, ITEM_TABLE, item_id_to_name
from .. import launcher

logger = logging.getLogger("NSMBDS.Sync")


class ReserveHandlingMixin:
    @property
    def reserve_mode(self) -> str:
        if self._reserve_mode is None:
            self._reserve_mode = launcher.reserve_mode()
        return self._reserve_mode

    def reserve_delivery_pending(self) -> bool:
        pending = self._pending_item_transaction
        return bool(pending and item_id_to_name.get(pending["item_id"]) in INVENTORY_RAM_VALUES)

    def _persist_reserve_selection(self) -> bool:
        # Utils updates its cache before writing. A failed save must not make
        # an identical retry skip the actual file write.
        self._force_item_cursor_store = True
        try:
            return self._persist_item_cursor() is not False
        finally:
            self._force_item_cursor_store = False

    def set_reserve_mode(self, mode: str) -> bool:
        self.reserve_action_error = ""
        if mode not in launcher.RESERVE_MODES:
            self.reserve_action_error = "Choose Automatic or Manual."
            return False
        if mode == self.reserve_mode:
            return True
        if self.reserve_delivery_pending():
            self.reserve_action_error = "Finishing a pocket delivery; try again once it is confirmed."
            return False
        previous = (self._next_powerup_id, self._next_powerup_mode)
        self._next_powerup_id = self._next_powerup_mode = None
        if not self._persist_reserve_selection():
            self._next_powerup_id, self._next_powerup_mode = previous
            self._persist_reserve_selection()
            self.reserve_action_error = "Could not save the reserve selection; mode was not changed."
            return False
        try:
            launcher.set_reserve_mode(mode)
        except (OSError, TypeError, ValueError) as exc:
            self._next_powerup_id, self._next_powerup_mode = previous
            self._persist_reserve_selection()
            self.reserve_action_error = "Could not save the reserve mode."
            logger.warning("Could not save reserve mode: %s", exc)
            return False
        self._reserve_mode = mode
        self._reserve_selection_revision += 1
        logger.info("Item Reserve: %s.", mode.title())
        return True

    def select_next_powerup(self, ctx, item_id: int | None) -> bool:
        """Select one queued copy; None cancels an unstarted delivery."""
        self.reserve_action_error = ""
        if self.reserve_delivery_pending():
            self.reserve_action_error = "Finishing a pocket delivery; try again once it is confirmed."
            return False
        if self._awaiting_item_history or self._item_cursor_needs_initial_sync:
            self.reserve_action_error = "Waiting for the server item history."
            return False
        if item_id is not None:
            if item_id not in self._deferred_item_ids or item_id_to_name.get(item_id) not in INVENTORY_RAM_VALUES:
                self.reserve_action_error = "No queued copy of that power-up is available."
                return False
            missing = self._missing_powerup_license(ctx, item_id)
            if missing is not None:
                self.reserve_action_error = f"Requires {missing}."
                return False
        previous = (self._next_powerup_id, self._next_powerup_mode)
        self._next_powerup_id = item_id
        self._next_powerup_mode = self.reserve_mode if item_id is not None else None
        if not self._persist_reserve_selection():
            self._next_powerup_id, self._next_powerup_mode = previous
            self._persist_reserve_selection()
            self.reserve_action_error = "Could not save the reserve selection."
            return False
        self._reserve_selection_revision += 1
        return True

    def _reserve_item_allowed(self, item_id: int) -> bool:
        return self.reserve_mode == "automatic" or (
            item_id == self._next_powerup_id
            and self._next_powerup_mode == "manual"
            and item_id in self._deferred_item_ids
        )


def reserve_command(ctx, output, argument: str = "") -> bool:
    """Handle /nsmbds_reserve without requiring the dedicated GUI."""
    mode = argument.strip().lower()
    handler = getattr(ctx, "client_handler", None)
    if handler is None or not callable(getattr(handler, "set_reserve_mode", None)):
        output("Connect an NSMBDS ROM first.")
        return False
    if mode and not handler.set_reserve_mode(mode):
        output(handler.reserve_action_error)
        return False
    output(f"Item Reserve: {handler.reserve_mode.title()}.")
    return True


def powerup_command(ctx, output, argument: str = "") -> bool:
    """Handle a full power-up name or cancel using the shared selection API."""
    handler = getattr(ctx, "client_handler", None)
    if handler is None or not callable(getattr(handler, "select_next_powerup", None)):
        output("Connect an NSMBDS ROM first.")
        return False
    name = argument.strip().casefold()
    names = {powerup.casefold(): powerup for powerup in INVENTORY_RAM_VALUES}
    if name == "cancel":
        item_id = None
    elif name in names:
        item_id = ITEM_TABLE[names[name]][0]
    else:
        output("Usage: /nsmbds_powerup <Mushroom|Fire Flower|Blue Shell|Mini Mushroom|Mega Mushroom|cancel>")
        return False
    if not handler.select_next_powerup(ctx, item_id):
        output(handler.reserve_action_error)
        return False
    output("Reserve selection cancelled." if item_id is None else
           f"Selected {item_id_to_name[item_id]} ×1; delivered when the pocket is empty.")
    return True
