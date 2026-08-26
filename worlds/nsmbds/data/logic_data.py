"""Access data for the NSMBDS world
"""

from __future__ import annotations

from typing import TypeAlias


# An expression is OR-of-AND: one inner tuple must be fully satisfied.
Requirement: TypeAlias = tuple[tuple[str, ...], ...]


def one(*atoms: str) -> Requirement:
    return (atoms,)


def any_of(*atoms: str) -> Requirement:
    return tuple((atom,) for atom in atoms)


STAGE_ENTRY_REQUIREMENTS: dict[str, Requirement] = {
    "World 1-1": one(),
    "World 1-2": one("World 1-1 Goal"),
    "World 1-3": one("World 1-2 Goal"),
    "World 1-Tower": any_of("World 1-3 Goal", "World 1-2 Secret Exit"),
    "World 1-4": one("World 1-Tower Goal"),
    "World 1-5": one("World 1-4 Goal"),
    "World 1-A": one("World 1-4 Goal"),
    "World 1-Castle": any_of("World 1-5 Goal", "World 1-A Goal"),

    "World 2-1": one(),
    "World 2-2": one("World 2-1 Goal"),
    "World 2-3": one("World 2-2 Goal"),
    "World 2-4": one("World 2-3 Goal"),
    "World 2-Tower": one("World 2-4 Goal"),
    "World 2-5": one("World 2-Tower Goal"),
    "World 2-6": any_of("World 2-5 Goal", "World 2-4 Secret Exit"),
    "World 2-A": one("World 2-3 Secret Exit"),
    "World 2-Castle": any_of("World 2-6 Goal", "World 2-A Goal"),

    "World 3-1": one(),
    "World 3-A": one(),
    "World 3-2": any_of("World 3-1 Goal", "World 3-A Goal"),
    "World 3-Tower": one("World 3-2 Goal"),
    "World 3-3": one("World 3-Tower Goal"),
    "World 3-Ghost House": one("World 3-3 Goal"),
    "World 3-B": one("World 3-2 Secret Exit"),
    "World 3-C": one("World 3-B Goal"),
    "World 3-Castle": any_of("World 3-Ghost House Goal", "World 3-C Goal"),

    "World 4-1": one(),
    "World 4-2": one("World 4-1 Goal"),
    "World 4-3": one("World 4-2 Goal"),
    "World 4-Tower": any_of("World 4-3 Goal", "World 4-1 Secret Exit"),
    "World 4-A": one("World 4-Tower Goal"),
    "World 4-4": one("World 4-Tower Goal"),
    "World 4-Ghost House": any_of("World 4-4 Goal", "World 4-A Goal"),
    "World 4-5": one("World 4-Ghost House Goal"),
    "World 4-6": one("World 4-5 Goal"),
    "World 4-Castle": one("World 4-6 Goal"),

    "World 5-1": one(),
    "World 5-A": one("World 5-1 Goal"),
    "World 5-2": one("World 5-1 Goal"),
    "World 5-Tower": any_of("World 5-2 Goal", "World 5-A Goal"),
    "World 5-3": any_of("World 5-Tower Goal", "World 5-2 Secret Exit"),
    "World 5-B": one("World 5-Tower Goal"),
    "World 5-C": one("World 5-B Goal"),
    "World 5-Ghost House": one("World 5-3 Goal"),
    "World 5-4": any_of("World 5-Ghost House Goal", "World 5-C Goal"),
    "World 5-Castle": any_of("World 5-4 Goal", "World 5-B Secret Exit"),

    "World 6-1": one(),
    "World 6-A": one(),
    "World 6-2": any_of("World 6-1 Goal", "World 6-A Goal"),
    "World 6-Tower 1": one("World 6-2 Goal"),
    "World 6-3": one("World 6-Tower 1 Goal"),
    "World 6-4": one("World 6-3 Goal"),
    "World 6-Tower 2": one("World 6-4 Goal"),
    "World 6-5": one("World 6-Tower 2 Goal"),
    "World 6-B": one("World 6-Tower 2 Goal"),
    "World 6-6": any_of("World 6-5 Goal", "World 6-B Goal"),
    "World 6-Castle": one("World 6-6 Goal"),

    "World 7-1": one(),
    "World 7-Ghost House": one("World 7-1 Goal"),
    "World 7-2": one("World 7-Ghost House Goal"),
    "World 7-3": one("World 7-2 Goal"),
    "World 7-Tower": any_of("World 7-3 Goal", "World 7-Ghost House Secret Exit"),
    "World 7-4": one("World 7-Tower Goal"),
    "World 7-5": one("World 7-4 Goal"),
    "World 7-6": one("World 7-5 Goal"),
    "World 7-A": one("World 7-5 Secret Exit"),
    "World 7-7": one("World 7-6 Secret Exit"),
    "World 7-Castle": any_of(
        "World 7-4 Secret Exit", "World 7-A Goal", "World 7-7 Goal"
    ),

    "World 8-1": one(),
    "World 8-2": one("World 8-1 Goal"),
    "World 8-Tower 1": one("World 8-2 Goal"),
    "World 8-3": one("World 8-Tower 1 Goal"),
    "World 8-4": one("World 8-3 Goal"),
    "World 8-Castle": one("World 8-4 Goal"),
    "World 8-5": one("World 8-Castle Goal"),
    "World 8-6": one("World 8-5 Goal"),
    "World 8-7": one("World 8-6 Goal"),
    "World 8-8": one("World 8-7 Goal"),
    "World 8-Tower 2": one("World 8-8 Goal"),
    "World 8-Bowser's Castle": one("World 8-Tower 2 Goal"),
}


# Gate authorization is handled separately.  These requirements describe the
# route to the front side of the sign or to an ungated Toad House.
TOAD_HOUSE_ENTRY_REQUIREMENTS: dict[str, Requirement] = {
    "World 1 Green Toad House 1": one("World 1-2 Goal"),
    "World 1 Green Toad House 2": one("World 1-4 Goal"),
    "World 1 Orange Toad House": one("World 1-Tower Goal"),
    "World 1 Red Toad House 1": one("World 1-2 Secret Exit"),
    "World 1 Red Toad House 2": one("World 1-A Goal"),
    "World 2 Red Toad House 1": one("World 2-1 Goal"),
    "World 2 Red Toad House 2": one("World 2-4 Secret Exit"),
    "World 2 Red Toad House 3": one("World 2-5 Goal"),
    "World 2 Orange Toad House": one("World 2-3 Goal"),
    "World 2 Green Toad House": one("World 2-Tower Goal"),
    "World 3 Red Toad House": one("World 3-A Goal"),
    "World 3 Orange Toad House": one("World 3-Tower Goal"),
    "World 3 Green Toad House": one("World 3-B Goal"),
    "World 4 Red Toad House 1": one("World 4-1 Goal"),
    "World 4 Green Toad House 1": one("World 4-1 Secret Exit"),
    "World 4 Orange Toad House": any_of("World 4-A Goal", "World 4-4 Goal"),
    "World 4 Green Toad House 2": one("World 4-Ghost House Goal"),
    "World 4 Red Toad House 2": one("World 4-5 Goal"),
    "World 5 Red Toad House": one("World 5-Castle Secret Exit"),
    "World 5 Orange Toad House": one("World 5-B Goal"),
    "World 5 Green Toad House": one("World 5-Ghost House Goal"),
    "World 6 Red Toad House 1": one("REGION:World 6 Gate: World 6-A"),
    "World 6 Green Toad House 1": one("World 6-1 Goal"),
    "World 6 Orange Toad House": one("World 6-Tower 1 Goal"),
    "World 6 Red Toad House 2": one("World 6-3 Goal"),
    "World 6 Green Toad House 2": one(
        "World 6-Tower 2 Goal",
        "REGION:World 6 Gate: World 6 Red Toad House 2",
    ),
    "World 7 Orange Toad House": one(),
    "World 7 Red Toad House": one("World 7-Ghost House Goal"),
    "World 7 Green Toad House 1": one("World 7-2 Goal"),
    "World 7 Green Toad House 2": one("World 7-Ghost House Secret Exit"),
    "World 7 Green Toad House 3": one("World 7-4 Secret Exit"),
    "World 8 Green Toad House": one("World 8-1 Goal"),
    "World 8 Orange Toad House": one("World 8-Tower 1 Goal"),
    "World 8 Red Toad House": one("World 8-3 Goal"),
}


CANNON_ROUTE_EXITS = frozenset({
    "World 1-Tower Secret Exit",
    "World 2-A Secret Exit",
    "World 3-Ghost House Secret Exit",
    "World 4-Ghost House Secret Exit",
    "World 5-Ghost House Secret Exit",
})

INTER_WORLD_SECRET_EXITS = frozenset({
    "World 2-Castle Secret Exit",
    "World 5-Castle Secret Exit",
})

INTER_SECRET_DEPENDENT_REGIONS = frozenset({
    "World 5 Red Toad House",
})

ALL_SECRET_EXITS = frozenset(
    atom
    for requirement in (*STAGE_ENTRY_REQUIREMENTS.values(), *TOAD_HOUSE_ENTRY_REQUIREMENTS.values())
    for alternative in requirement
    for atom in alternative
    if atom.endswith(" Secret Exit")
) | CANNON_ROUTE_EXITS | INTER_WORLD_SECRET_EXITS

INTRA_WORLD_SECRET_EXITS = ALL_SECRET_EXITS - CANNON_ROUTE_EXITS - INTER_WORLD_SECRET_EXITS


# Locations which cease to be logically reachable when internal secret paths
# are ignored. They remain usable checks, but may not hold progression.
INTRA_SECRET_DEPENDENT_REGIONS = frozenset({
    "World 2-A",
    "World 3-B",
    "World 3-C",
    "World 3 Green Toad House",
    "World 7-A",
    "World 7-Castle",
    "World 1 Red Toad House 1",
    "World 2 Red Toad House 2",
    "World 4 Green Toad House 1",
    "World 7 Green Toad House 2",
    "World 7 Green Toad House 3",
})

# These inter-world route events are physically usable, but reaching the event
# already requires an internal secret path. Omit them as generator alternatives
# when intra-world secret-exit logic is disabled.
INTRA_SECRET_DEPENDENT_WORLD_ROUTE_EVENTS = frozenset({
    "World 2-A Secret Exit",
})


_ADVANCED_CORE = {
    "World 1-2 1-Up Block", "World 1-4 1-Up Block", "World 1-Tower 1-Up Block",
    "World 2-2 Star Coin 1", "World 2-A Star Coin 3", "World 2-A Secret Exit",
    "World 2-A 1-Up Block", "World 2-Castle Secret Exit", "World 3-3 1-Up Block",
    "World 3-A 1-Up Block", "World 4-1 1-Up Block", "World 4-3 1-Up Block 2",
    "World 4-6 1-Up Block 1", "World 4 Green Toad House 1 Goal",
    "World 5-C 1-Up Block", "World 5-Castle Star Coin 2",
    "World 5-Castle Star Coin 3", "World 5-Castle Secret Exit",
    "World 6-2 1-Up Block", "World 6-3 Star Coin 3", "World 6-5 1-Up Block",
    "World 6-6 1-Up Block", "World 6-A 1-Up Block",
    "World 6-Tower 1 1-Up Block 1", "World 6-Tower 1 1-Up Block 2",
    "World 6-Castle Star Coin 3", "World 7-7 1-Up Block",
    "World 7-A 1-Up Block 1", "World 7-Ghost House Secret Exit",
    "World 7 Green Toad House 2 Goal", "World 8-1 Star Coin 1",
    "World 8-Castle Star Coin 3",
}

_ADVANCED_BLOCKS = {
    "World 2-3 Blocksanity Block 1", "World 2-3 Blocksanity Block 2",
    "World 2-A Blocksanity Block 5", "World 2-A Blocksanity Block 16",
    "World 2-A Blocksanity Block 17", "World 2-A Blocksanity Block 18",
    "World 2-A Blocksanity Block 19", "World 2-A Blocksanity Block 20",
    "World 2-A Blocksanity Block 21", "World 2-A Blocksanity Block 22",
    "World 3-B Blocksanity Block 13", "World 3-C Blocksanity Block 6",
    "World 4-4 Blocksanity Block 7", "World 4-5 Blocksanity Block 7",
    "World 4-5 Blocksanity Block 8", "World 4-5 Blocksanity Block 9",
    "World 4-5 Blocksanity Block 13", "World 4-5 Blocksanity Block 14",
    "World 4-5 Blocksanity Block 36", "World 4-5 Blocksanity Block 37",
    "World 4-5 Blocksanity Block 57", "World 4-6 Blocksanity Block 8",
    "World 4-6 Blocksanity Block 9", "World 4-Ghost House Blocksanity Block 16",
    "World 4-Ghost House Blocksanity Block 17", "World 4-Ghost House Blocksanity Block 18",
    "World 4-Castle Blocksanity Block 5", "World 5-2 Blocksanity Block 1",
    "World 5-3 Blocksanity Block 3", "World 5-C Blocksanity Block 20",
    "World 5-C Blocksanity Block 25", "World 5-C Blocksanity Block 26",
    "World 5-C Blocksanity Block 31", "World 5-C Blocksanity Block 32",
    "World 5-Ghost House Blocksanity Block 24", "World 5-Castle Blocksanity Block 10",
    "World 6-1 Blocksanity Block 1", "World 6-2 Blocksanity Block 2",
    "World 6-2 Blocksanity Block 3", "World 6-2 Blocksanity Block 4",
    "World 6-4 Blocksanity Block 4", "World 6-6 Blocksanity Block 2",
    "World 6-6 Blocksanity Block 3", "World 6-A Blocksanity Block 5",
    "World 6-A Blocksanity Block 6", "World 6-B Blocksanity Block 4",
    "World 6-Tower 1 Blocksanity Block 1", "World 6-Tower 1 Blocksanity Block 2",
    "World 6-Tower 1 Blocksanity Block 3", "World 6-Tower 2 Blocksanity Block 3",
    "World 7-3 Blocksanity Block 2", "World 7-4 Blocksanity Block 1",
    "World 7-4 Blocksanity Block 6", "World 7-4 Blocksanity Block 7",
    "World 7-4 Blocksanity Block 9", "World 7-4 Blocksanity Flying Block 1",
    "World 7-A Blocksanity Block 3", "World 7-Castle Blocksanity Block 5",
    "World 8-5 Blocksanity Block 10",
}
_ADVANCED_BLOCKS.update(f"World 5-C Blocksanity Block {index}" for index in range(1, 17))
_ADVANCED_CORE.update(
    f"World 6-2 Bonus Area Flying 1-Up Block {index}" for index in range(1, 9)
)

ADVANCED_LOCATION_NAMES = frozenset(_ADVANCED_CORE | _ADVANCED_BLOCKS)
