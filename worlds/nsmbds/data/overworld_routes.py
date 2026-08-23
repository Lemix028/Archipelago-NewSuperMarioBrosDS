"""Verified inter-world routes, grouped by generator option."""

from __future__ import annotations

from dataclasses import dataclass


RouteAlternatives = tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class WorldConnectionRequirement:
    pass_item: str
    normal_routes: RouteAlternatives = ()
    alternate_castle_routes: RouteAlternatives = ()
    cannon_routes: RouteAlternatives = ()

    @property
    def vanilla_routes(self) -> RouteAlternatives:
        """All physical routes, retained for client/event compatibility."""
        return self.normal_routes + self.alternate_castle_routes + self.cannon_routes


WORLD_CONNECTION_REQUIREMENTS: dict[str, WorldConnectionRequirement] = {
    "Menu -> World 2": WorldConnectionRequirement(
        "Desert Pass", normal_routes=(("World 1-Castle Goal",),),
    ),
    "Menu -> World 3": WorldConnectionRequirement(
        "Isle Pass", normal_routes=(("World 2-Castle Goal",),),
    ),
    "Menu -> World 4": WorldConnectionRequirement(
        "Jungle Pass", alternate_castle_routes=(("World 2-Castle Secret Exit",),),
    ),
    "Menu -> World 5": WorldConnectionRequirement(
        "Glacier Pass",
        normal_routes=(("World 3-Castle Goal",), ("World 4-Castle Goal",)),
        cannon_routes=(("World 1-Tower Secret Exit",), ("World 2-A Secret Exit",)),
    ),
    "Menu -> World 6": WorldConnectionRequirement(
        "Mountain Pass",
        normal_routes=(("World 5-Castle Goal",),),
        cannon_routes=(("World 3-Ghost House Secret Exit",),),
    ),
    "Menu -> World 7": WorldConnectionRequirement(
        "Cloud Pass",
        alternate_castle_routes=(("World 5-Castle Secret Exit",),),
        cannon_routes=(("World 4-Ghost House Secret Exit",),),
    ),
    "Menu -> World 8": WorldConnectionRequirement(
        "Volcano Pass",
        normal_routes=(("World 6-Castle Goal",), ("World 7-Castle Goal",)),
        cannon_routes=(("World 5-Ghost House Secret Exit",),),
    ),
}


VANILLA_ROUTE_EVENT_NAMES = frozenset(
    location_name
    for requirement in WORLD_CONNECTION_REQUIREMENTS.values()
    for alternative in requirement.vanilla_routes
    for location_name in alternative
)
