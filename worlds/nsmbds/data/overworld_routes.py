"""Verified overworld route requirements used by trackers and AP logic."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorldConnectionRequirement:
    """A destination Pass or one of the vanilla routes can open a world."""

    pass_item: str
    vanilla_routes: tuple[tuple[str, ...], ...]


# Location reachability is the monotonic AP equivalent of completing a route:
# if its Goal/Secret Exit can be reached, the solver may assume it can be cleared.
WORLD_CONNECTION_REQUIREMENTS: dict[str, WorldConnectionRequirement] = {
    "World 1 -> World 2": WorldConnectionRequirement(
        "Desert Pass", (("World 1-Castle Goal",),),
    ),
    "World 2 -> World 3": WorldConnectionRequirement(
        "Isle Pass", (("World 2-Castle Goal",),),
    ),
    "World 2 -> World 4": WorldConnectionRequirement(
        "Jungle Pass", (("World 2-Castle Secret Exit",),),
    ),
    "World 1 -> World 5": WorldConnectionRequirement(
        "Glacier Pass", (("World 1-Tower Secret Exit",),),
    ),
    "World 2 -> World 5": WorldConnectionRequirement(
        "Glacier Pass", (("World 2-A Secret Exit",),),
    ),
    "World 3 -> World 4": WorldConnectionRequirement(
        "Jungle Pass", (("World 3-Castle Goal",),),
    ),
    "World 3 -> World 6": WorldConnectionRequirement(
        "Mountain Pass", (("World 3-Ghost House Secret Exit",),),
    ),
    "World 4 -> World 5": WorldConnectionRequirement(
        "Glacier Pass", (("World 4-Castle Goal",),),
    ),
    "World 4 -> World 7": WorldConnectionRequirement(
        "Cloud Pass", (("World 4-Ghost House Secret Exit",),),
    ),
    "World 5 -> World 6": WorldConnectionRequirement(
        "Mountain Pass", (("World 5-Castle Goal",),),
    ),
    "World 5 -> World 7": WorldConnectionRequirement(
        "Cloud Pass", (("World 5-Castle Secret Exit",),),
    ),
    "World 5 -> World 8": WorldConnectionRequirement(
        "Volcano Pass", (("World 5-Ghost House Secret Exit",),),
    ),
    "World 6 -> World 8": WorldConnectionRequirement(
        "Volcano Pass", (("World 6-Castle Goal",),),
    ),
    "World 7 -> World 8": WorldConnectionRequirement(
        "Volcano Pass",
        (
            ("World 7-Castle Goal",),
            ("World 7-4 Secret Exit",),
        ),
    ),
}


# Each inner tuple is one possible route. Every event in that tuple is required.
# Goal events mean the normal exit; Secret Exit events mean the red-flag exit.
TRACKER_ROUTE_ALTERNATIVES: dict[str, tuple[tuple[str, ...], ...]] = {
    "World 1 Red Toad House 2": (("World 1-2 Secret Exit",),),
    "World 2 Red Toad House 2": (("World 2-4 Secret Exit",),),
    "World 3 Red Toad House": (("World 3-A Goal",),),
    "World 4 Green Toad House 1": (("World 4-1 Secret Exit",),),

    # World 7 contains loops and mandatory secret-exit routing.
    "World 7-Ghost House": (("World 7-1 Goal",),),
    "World 7-2": (("World 7-Ghost House Goal",),),
    "World 7-3": (("World 7-2 Goal",),),
    "World 7-Tower": (
        ("World 7-3 Goal",),
        ("World 7-Ghost House Secret Exit",),
    ),
    "World 7-4": (("World 7-Tower Goal",),),
    "World 7-5": (("World 7-4 Goal",),),
    "World 7-6": (("World 7-5 Goal",),),
    "World 7-A": (("World 7-5 Secret Exit",),),
    "World 7-7": (("World 7-6 Secret Exit",),),
    "World 7-Castle": (
        ("World 7-4 Secret Exit",),
        ("World 7-A Goal",),
        ("World 7-7 Goal",),
    ),
    "World 7 Red Toad House": (("World 7-Ghost House Goal",),),
    "World 7 Green Toad House 1": (
        ("World 7-3 Goal",),
        ("World 7-Ghost House Secret Exit",),
    ),
    "World 7 Green Toad House 2": (("World 7-4 Secret Exit",),),
    "World 7 Green Toad House 3": (("World 7-5 Goal",),),

    # World 8 has one linear route through both halves of the world.
    "World 8-2": (("World 8-1 Goal",),),
    "World 8-Tower 1": (("World 8-2 Goal",),),
    "World 8-3": (("World 8-Tower 1 Goal",),),
    "World 8-4": (("World 8-3 Goal",),),
    "World 8-Castle": (("World 8-4 Goal",),),
    "World 8-5": (("World 8-Castle Goal",),),
    "World 8-6": (("World 8-5 Goal",),),
    "World 8-7": (("World 8-6 Goal",),),
    "World 8-8": (("World 8-7 Goal",),),
    "World 8-Tower 2": (("World 8-8 Goal",),),
    "World 8-Bowser's Castle": (("World 8-Tower 2 Goal",),),
}


# Route needed to approach the sign from its front side. An empty tuple means
# the sign is available immediately after entering that world.
GATE_FRONT_ROUTE_EVENTS: dict[str, tuple[str, ...]] = {
    "World 1-A": ("World 1-Tower Goal",),
    "World 3-A": (),
    "World 4-A": ("World 4-Tower Goal",),
    "World 5-A": ("World 5-1 Goal",),
    "World 5-B": ("World 5-Tower Goal",),
    "World 6-A": (),
    "World 6-B": ("World 6-Tower 2 Goal",),
}

# Star-Coin gated stages have no gate-free back routes.
GATE_BACK_ROUTE_EVENTS: dict[str, tuple[tuple[str, ...], ...]] = {}
