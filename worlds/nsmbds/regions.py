"""Stage-level region graph derived from the typed location catalog."""

from __future__ import annotations

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
from .data.star_coin_gates import STAR_COIN_GATES


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
