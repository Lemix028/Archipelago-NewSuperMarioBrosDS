"""NSMBDS-specific extensions for the standard Archipelago client UI."""

from __future__ import annotations

import math
from typing import Any


def install_kivy_hover_density_guard(provider_type: type[Any] | None = None) -> None:
    """Prevent Kivy hover events from dividing by a transient zero DPI scale.

    On Windows, Kivy can temporarily receive a DPI value of zero while a window
    is being created or moved between display states. Kivy 2.3.1 stores that as
    ``Window._density == 0`` and then divides the hover coordinates by it.
    """
    if provider_type is None:
        from kivy.input.providers.mouse import MouseMotionEventProvider

        provider_type = MouseMotionEventProvider

    original_create_hover = provider_type.create_hover
    if getattr(original_create_hover, "_nsmbds_density_guard", False):
        return

    def create_hover_with_valid_density(self: Any, win: Any, etype: str) -> Any:
        try:
            density = float(win._density)
        except (AttributeError, TypeError, ValueError):
            density = 0.0

        if not math.isfinite(density) or density <= 0.0:
            try:
                dpi = float(win.dpi)
            except (AttributeError, TypeError, ValueError):
                dpi = 0.0
            win._density = dpi / 96.0 if math.isfinite(dpi) and dpi > 0.0 else 1.0

        return original_create_hover(self, win, etype)

    create_hover_with_valid_density._nsmbds_density_guard = True  # type: ignore[attr-defined]
    provider_type.create_hover = create_hover_with_valid_density
