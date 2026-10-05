"""Look up physical level entrances through the local client command log."""

from __future__ import annotations

import re
from typing import Any, Callable

from ...data.level_randomization import ALL_STORY_LEVELS
from ..ui.tracker.state import build_level_directory, filter_level_directory


def _normalize(value: str) -> str:
    return "".join(value.casefold().replace("world", "w").split())


def level_command(ctx: Any, output: Callable[[str], None], query: str = "") -> bool:
    """Show a course/check entrance, all entrances, or one physical map world."""
    query = query.strip()
    if not query:
        output("Usage: /level <level or check name|all|world 1-8>")
        output("Examples: /level W3-3 | /level World 3-3 Star Coin 3 | /level world 3")
        return True
    if not getattr(ctx, "slot_data", None):
        output("Connect to a seed before looking up its level mapping.")
        return False
    try:
        entries = build_level_directory(ctx)
    except (TypeError, ValueError) as exc:
        output(f"Could not load level mapping: {exc}")
        return False

    world_match = re.fullmatch(r"(?:world|w)\s*([1-8])", query, flags=re.IGNORECASE)
    search = _normalize(query)
    if query.casefold() == "all" or world_match:
        world_number = int(world_match[1]) if world_match else 0
        matches = filter_level_directory(entries, "", world_number)
        slot_order = {slot: index for index, slot in enumerate(ALL_STORY_LEVELS)}
        matches = tuple(sorted(matches, key=lambda entry: slot_order[entry.map_slot]))
    else:
        matches = filter_level_directory(entries, query)
        # A named original course must yield its entrance, even if another
        # course occupies the map node with that same name.
        exact_courses = tuple(entry for entry in matches if _normalize(entry.content_name) == search)
        if exact_courses:
            matches = exact_courses

    if not matches:
        output(f"No matching level or active check: {query}. Use /level all to list entrances.")
        return False

    for entry in matches:
        exact_check = next((name for name in entry.check_names if _normalize(name) == search), None)
        if exact_check:
            output(f"{exact_check} -> Enter {entry.map_slot} (loaded course: {entry.content_name})")
        else:
            output(f"{entry.content_name} -> Enter {entry.map_slot} "
                   f"({entry.progress.checked}/{entry.progress.total} checks)")
    return True
