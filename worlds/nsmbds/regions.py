"""Stage-level region graph derived from the typed location catalog."""

from __future__ import annotations

from .data.level_randomization import MINI_CASTLE_SECRET_EXIT_SLOTS
from .data.star_coin_gates import STAR_COIN_GATES
from .locations import (
    ALL_ACTIVE_DEFINITIONS,
    BLOCKSANITY_DEFINITIONS,
    BOSS_LOCATION_BY_STAGE,
    ONE_UP_BLOCK_DEFINITIONS,
    RED_COIN_CHALLENGE_NAMES_BY_STAGE,
    RED_COIN_COURSE_LEVELS,
    LocationKind,
    StageDefinition,
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES,
)


WORLD_REGION_NAMES = tuple(f"World {world}" for world in range(1, 9))
ENTITY_REGION_NAMES = tuple(definition.name for definition in ALL_ACTIVE_DEFINITIONS)

REGION_LIST: list[str] = [
    "Menu",
    *WORLD_REGION_NAMES,
    *ENTITY_REGION_NAMES,
    "World 6-2 Bonus Area",
    *(gate.region_name for gate in STAR_COIN_GATES),
]


def _definition_location_names(definition: StageDefinition) -> list[str]:
    names = [f"{definition.name} Goal"]
    boss_definition = BOSS_LOCATION_BY_STAGE.get(definition.name)
    if boss_definition is not None:
        names.append(boss_definition.name)
    if definition.has_star_coins:
        names.extend(f"{definition.name} Star Coin {coin}" for coin in range(1, 4))
    if definition.name in RED_COIN_COURSE_LEVELS:
        names.extend(RED_COIN_CHALLENGE_NAMES_BY_STAGE[definition.name])
    if definition.has_secret_exit:
        names.append(f"{definition.name} Secret Exit")
    return names


REGION_LOCATIONS: dict[str, list[str]] = {name: [] for name in REGION_LIST}
for definition in ALL_ACTIVE_DEFINITIONS:
    REGION_LOCATIONS[definition.name].extend(_definition_location_names(definition))

for definition in ONE_UP_BLOCK_DEFINITIONS:
    target = (
        "World 6-2 Bonus Area"
        if definition.name in WORLD_6_2_BONUS_AREA_LOCATION_NAMES
        else definition.stage_name
    )
    REGION_LOCATIONS[target].append(definition.name)

for definition in BLOCKSANITY_DEFINITIONS:
    target = (
        "World 6-2 Bonus Area"
        if definition.name in WORLD_6_2_BONUS_AREA_LOCATION_NAMES
        else definition.stage_name
    )
    REGION_LOCATIONS[target].append(definition.name)


_gate_by_target = {gate.target_stage_name: gate for gate in STAR_COIN_GATES}
REGION_CONNECTIONS: dict[str, list[str]] = {name: [] for name in REGION_LIST}
REGION_CONNECTIONS["Menu"] = list(WORLD_REGION_NAMES)

for definition in ALL_ACTIVE_DEFINITIONS:
    world_region = f"World {definition.world_index + 1}"
    gate = _gate_by_target.get(definition.name)
    if gate:
        REGION_CONNECTIONS[world_region].append(gate.region_name)
        REGION_CONNECTIONS[gate.region_name].append(definition.name)
    else:
        REGION_CONNECTIONS[world_region].append(definition.name)

REGION_CONNECTIONS["World 6-2"].append("World 6-2 Bonus Area")


def build_region_locations(level_mapping: dict[str, str]) -> dict[str, list[str]]:
    """Move slot-owned castle branches while keeping course checks with content."""
    locations = {name: list(names) for name, names in REGION_LOCATIONS.items()}
    for slot_name in MINI_CASTLE_SECRET_EXIT_SLOTS:
        location_name = f"{slot_name} Secret Exit"
        for names in locations.values():
            if location_name in names:
                names.remove(location_name)
        locations[level_mapping[slot_name]].append(location_name)
    return locations


def build_region_connections(
    level_mapping: dict[str, str],
) -> tuple[tuple[str, str, str], ...]:
    """Build named entrances whose map topology is slot-owned and content target is shuffled."""
    connections: list[tuple[str, str, str]] = []
    connections.extend(
        ("Menu", world_name, f"Menu -> {world_name}")
        for world_name in WORLD_REGION_NAMES
    )

    for definition in ALL_ACTIVE_DEFINITIONS:
        target_name = (
            level_mapping[definition.name]
            if definition.kind is LocationKind.STAGE
            else definition.name
        )
        gate = _gate_by_target.get(definition.name)
        source_name = gate.region_name if gate else f"World {definition.world_index + 1}"
        if gate:
            connections.append((
                gate.source_region,
                gate.region_name,
                f"{gate.source_region} -> {gate.region_name}",
            ))
        connections.append((source_name, target_name, f"{source_name} -> {definition.name}"))

    # This room is part of the World 6-2 course and therefore follows that content.
    content_region = "World 6-2"
    connections.append((
        content_region,
        "World 6-2 Bonus Area",
        f"{content_region} -> World 6-2 Bonus Area",
    ))
    return tuple(connections)


STAGE_REGION_NAMES = frozenset(
    definition.name
    for definition in ALL_ACTIVE_DEFINITIONS
    if definition.kind is LocationKind.STAGE
)
TOAD_HOUSE_REGION_NAMES = frozenset(
    definition.name
    for definition in ALL_ACTIVE_DEFINITIONS
    if definition.kind is LocationKind.STATIC_TOAD_HOUSE
)
