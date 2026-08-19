"""Region definitions derived from the active typed location catalog."""

from .locations import (
    ALL_WORLDS,
    BLOCKSANITY_LOCATION_NAMES_BY_WORLD,
    ONE_UP_BLOCK_LOCATION_NAMES_BY_WORLD,
    RED_COIN_CHALLENGE_NAMES_BY_STAGE,
    RED_COIN_COURSE_LEVELS,
    StageDefinition,
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES,
)
from .data.star_coin_gates import STAR_COIN_GATES


REGION_LIST: list[str] = [
    "Menu", "World 1", "World 2", "World 3", "World 4",
    "World 5", "World 6", "World 6-2 Bonus Area", "World 7", "World 8",
] + [gate.region_name for gate in STAR_COIN_GATES]

REGION_CONNECTIONS: dict[str, list[str]] = {
    "Menu": ["World 1"],
    "World 1": ["World 2", "World 5"],
    "World 2": ["World 3", "World 4", "World 5"],
    "World 3": ["World 4", "World 6"],
    "World 4": ["World 5", "World 7"],
    "World 5": ["World 6", "World 7", "World 8"],
    "World 6": ["World 6-2 Bonus Area", "World 8"],
    "World 6-2 Bonus Area": [],
    "World 7": ["World 8"],
    "World 8": [],
}

for gate in STAR_COIN_GATES:
    REGION_CONNECTIONS[gate.source_region].append(gate.region_name)


def _stage_location_names(stage: StageDefinition) -> list[str]:
    """Return every active AP location generated for one catalog definition."""
    names = [f"{stage.name} Goal"]
    if stage.has_star_coins:
        names.extend(f"{stage.name} Star Coin {coin}" for coin in range(1, 4))
    if stage.name in RED_COIN_COURSE_LEVELS:
        names.extend(RED_COIN_CHALLENGE_NAMES_BY_STAGE[stage.name])
    if stage.has_secret_exit:
        names.append(f"{stage.name} Secret Exit")
    return names


REGION_LOCATIONS: dict[str, list[str]] = {"Menu": []}
for world_number, definitions in enumerate(ALL_WORLDS, start=1):
    REGION_LOCATIONS[f"World {world_number}"] = [
        location_name
        for definition in definitions
        for location_name in _stage_location_names(definition)
    ] + list(ONE_UP_BLOCK_LOCATION_NAMES_BY_WORLD[world_number - 1]) \
      + list(BLOCKSANITY_LOCATION_NAMES_BY_WORLD[world_number - 1])

# Keep the dense optional room visually separate from the normal World-6 pool.
REGION_LOCATIONS["World 6"] = [
    name
    for name in REGION_LOCATIONS["World 6"]
    if name not in WORLD_6_2_BONUS_AREA_LOCATION_NAMES
]
REGION_LOCATIONS["World 6-2 Bonus Area"] = sorted(
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES
)

# Move each Star-Coin-gated destination into its own region.
for gate in STAR_COIN_GATES:
    gated_location_names = [
        name for name in REGION_LOCATIONS[gate.source_region]
        if name.startswith(gate.target_stage_name)
    ]
    if not gated_location_names:
        raise ValueError(f"No locations found for verified Star-Coin gate target {gate.target_stage_name!r}.")
    REGION_LOCATIONS[gate.source_region] = [
        name for name in REGION_LOCATIONS[gate.source_region]
        if name not in gated_location_names
    ]
    REGION_LOCATIONS[gate.region_name] = gated_location_names
