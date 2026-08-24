"""Typed location metadata and RAM mappings for New Super Mario Bros. DS."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import Enum
from collections import defaultdict

from BaseClasses import Location

from .items import BASE_ID
from .data.level_catalog import FULL_LEVEL_CATALOG
from .data.blocksanity_data import (
    BLOCKSANITY_SPECS,
    BLOCKSANITY_STATIC_COUNT,
    BLOCKSANITY_STATIC_ID_SPAN,
    RUNTIME_AREA_OFFSET_BY_SOURCE_COURSE,
)
from .data.moving_blocksanity_data import (
    SPRITE_290_BLOCKSANITY_COUNT,
    SPRITE_290_ID,
    SPRITE_290_ONE_UP_COUNT,
    SPRITE_290_ONE_UP_ITEM,
    SPRITE_290_PLACEMENTS,
)


class NSMBDSLocation(Location):
    game = "New Super Mario Bros. DS"


class SecretExitStatus(str, Enum):
    """Indicates whether a stage has a separate Secret Exit condition."""

    NONE = "none"
    EXISTS = "exists"


class LocationKind(str, Enum):
    """Map entity type represented by a stable Archipelago location."""

    STAGE = "stage"
    STATIC_TOAD_HOUSE = "static_toad_house"
    STATIC_MAP_REWARD = "static_map_reward"
    ONE_UP_BLOCK = "one_up_block"
    BLOCKSANITY = "blocksanity"


@dataclass(frozen=True)
class StageDefinition:

    name: str
    world_index: int
    location_index: int
    ram_offset: int
    has_star_coins: bool = True
    secret_exit_status: SecretExitStatus = SecretExitStatus.NONE
    kind: LocationKind = LocationKind.STAGE
    goal_ram_offset: int | None = None

    @property
    def has_secret_exit(self) -> bool:
        """Return whether this entity has a Secret Exit route."""
        return self.secret_exit_status is SecretExitStatus.EXISTS


@dataclass(frozen=True)
class BossLocationDefinition:
    """A real AP check awarded for defeating one castle boss."""

    stage_name: str
    boss_name: str
    completion_sources: tuple[str, ...]

    @property
    def name(self) -> str:
        return f"{self.stage_name} {self.boss_name} Defeated"


@dataclass(frozen=True)
class OneUpBlockDefinition:

    name: str
    world_index: int
    stage_name: str
    source_course: str
    area_number: int
    object_id: int
    editor_x: int
    editor_y: int
    runtime_x: int
    runtime_y: int


@dataclass(frozen=True)
class BlocksanityDefinition:

    stable_uid: str
    stable_key: str
    name: str
    stage_name: str
    location_id_offset: int
    world_index: int
    runtime_level: int
    runtime_area: int
    runtime_x: int
    runtime_y: int
    object_id: int


@dataclass(frozen=True)
class MovingBlockDefinition:

    stable_uid: str
    stable_key: str
    name: str
    stage_name: str
    location_id_offset: int | None
    world_index: int
    source_course: str
    area_number: int
    runtime_level: int
    runtime_area: int
    editor_x: int
    editor_y: int
    runtime_x: int
    runtime_y: int
    sprite_id: int
    sprite_settings: int


def _loc_id(world_index: int, location_index: int, slot: int) -> int:
    """Return a Archipelago location ID inside a reserved world block."""
    return BASE_ID + 0x1000 + (world_index * 0x100) + (location_index * 0x10) + slot


def _runtime_level_for_stage_name(stage_name: str) -> int:
    """Map a canonical story-stage name to the in-level RAM selector."""
    suffix = stage_name.split("World ", 1)[1].split("-", 1)[1]
    if suffix.isdigit():
        return int(suffix)
    return {
        "A": 0x09,
        "B": 0x0A,
        "C": 0x0B,
        "Ghost House": 0x0C,
        "Tower": 0x0D,
        "Tower 1": 0x0D,
        "Castle": 0x0E,
        "Tower 2": 0x15,
        "Bowser's Castle": 0x16,
    }[suffix]


SLOT_GOAL = 0
SLOT_COIN_1 = 1
SLOT_COIN_2 = 2
SLOT_COIN_3 = 3
SLOT_RED_COIN = 4
SLOT_RED_COIN_2 = 5
SLOT_BOSS = 6
SLOT_SECRET = 8


LOCATION_ID_INDICES_PER_WORLD = tuple(range(16))
RESERVED_LOCATION_ID_INDICES_BY_WORLD = {
    f"World {world}": LOCATION_ID_INDICES_PER_WORLD for world in range(1, 9)
}


# Static houses are intentionally separate from normal stages.
STATIC_TOAD_HOUSES: tuple[StageDefinition, ...] = (
    StageDefinition("World 1 Green Toad House 1", 0, 7, 8, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 1 Green Toad House 2", 0, 11, 13, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 1 Orange Toad House", 0, 8, 10, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 1 Red Toad House 1", 0, 12, 18, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 1 Red Toad House 2", 0, 9, 11, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 2 Red Toad House 1", 1, 8, 36, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 2 Red Toad House 2", 1, 12, 41, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 2 Red Toad House 3", 1, 13, 43, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 2 Orange Toad House", 1, 9, 40, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 2 Green Toad House", 1, 11, 42, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 3 Red Toad House", 2, 8, 62, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 3 Orange Toad House", 2, 9, 64, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 3 Green Toad House", 2, 11, 66, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 4 Red Toad House 1", 3, 9, 87, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 4 Green Toad House 1", 3, 11, 88, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 4 Orange Toad House", 3, 12, 90, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 4 Green Toad House 2", 3, 13, 92, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 4 Red Toad House 2", 3, 14, 93, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 5 Red Toad House", 4, 9, 114, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 5 Orange Toad House", 4, 11, 121, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 5 Green Toad House", 4, 12, 122, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 6 Red Toad House 1", 5, 3, 139, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 6 Green Toad House 1", 5, 11, 140, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 6 Orange Toad House", 5, 12, 142, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 6 Red Toad House 2", 5, 13, 143, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 6 Green Toad House 2", 5, 14, 145, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 7 Orange Toad House", 6, 9, 161, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 7 Red Toad House", 6, 11, 162, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 7 Green Toad House 1", 6, 12, 163, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 7 Green Toad House 2", 6, 13, 164, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 7 Green Toad House 3", 6, 14, 165, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 8 Green Toad House", 7, 12, 188, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 8 Orange Toad House", 7, 13, 191, False, kind=LocationKind.STATIC_TOAD_HOUSE),
    StageDefinition("World 8 Red Toad House", 7, 14, 192, False, kind=LocationKind.STATIC_TOAD_HOUSE),
)

STATIC_MAP_REWARDS: tuple[StageDefinition, ...] = (
    # StageDefinition("World 1 Toad's Forest Shop", 0, 13, 17, False, kind=LocationKind.STATIC_MAP_REWARD),
)



# name, type, x, y
_ONE_UP_BLOCK_SPECS: tuple[tuple[str, int, int, int], ...] = (
    ("A01_1", 47, 105, 13),
    ("A02_1", 47, 85, 19),
    ("A04_1", 47, 136, 27),
    ("A06_2", 72, 102, 22),
    ("A06_2", 72, 115, 27),
    ("A07_1", 72, 49, 121),
    ("B03_2", 72, 114, 24),
    ("B06_2", 33, 171, 21),
    ("B07_1", 72, 139, 7),
    ("B09_1", 33, 83, 15),
    ("C02_1", 47, 30, 29),
    ("C03_2", 72, 55, 3),
    ("C04_1", 72, 221, 53),
    ("D01_1", 72, 103, 38),
    ("D02_1", 47, 101, 39),
    ("D03_2", 72, 253, 23),
    ("D03_2", 33, 121, 26),
    ("D05_2", 47, 75, 19),
    ("D06_1", 72, 122, 36),
    ("D06_2", 33, 44, 5),
    ("D10_1", 33, 217, 20),
    ("E02_2", 47, 74, 27),
    ("E04_1", 33, 176, 25),
    ("E05_1", 47, 169, 24),
    ("E06_1", 33, 107, 25),
    ("E07_2", 47, 141, 19),
    ("E09_1", 33, 41, 82),
    ("F02_1", 72, 58, 50),
    ("F05_2", 72, 306, 22),
    ("F06_1", 47, 19, 25),
    ("F07_2", 72, 70, 16),
    ("F09_1", 72, 56, 51),
    ("F09_1", 72, 54, 55),
    ("G01_1", 47, 217, 26),
    ("G02_2", 33, 1, 76),
    ("G05_1", 33, 172, 27),
    ("G06_1", 47, 64, 62),
    ("G07_1", 47, 53, 58),
    ("G08_2", 72, 10, 54),
    ("G08_2", 47, 12, 77),
    ("H03_2", 33, 72, 18),
    ("H05_1", 33, 96, 26),
)
_COURSE_PREFIX_TO_WORLD_INDEX = {letter: index for index, letter in enumerate("ABCDEFGH")}
_ONE_UP_BLOCK_NAMES_BY_STAGE: dict[str, int] = defaultdict(int)
_one_up_block_definitions: list[OneUpBlockDefinition] = []

for source_course, object_id, editor_x, editor_y in _ONE_UP_BLOCK_SPECS:
    prefix = source_course[0]
    course_number = int(source_course[1:3])
    area_number = int(source_course[4:])
    world_index = _COURSE_PREFIX_TO_WORLD_INDEX[prefix]
    stage_name = FULL_LEVEL_CATALOG[f"World {world_index + 1}"][course_number - 1]
    _ONE_UP_BLOCK_NAMES_BY_STAGE[stage_name] += 1
    block_number = _ONE_UP_BLOCK_NAMES_BY_STAGE[stage_name]
    _one_up_block_definitions.append(
        OneUpBlockDefinition(
            name=f"{stage_name} 1-Up Block {block_number}",
            world_index=world_index,
            stage_name=stage_name,
            source_course=source_course,
            area_number=area_number,
            object_id=object_id,
            editor_x=editor_x,
            editor_y=editor_y,
            runtime_x=editor_x,
            runtime_y=-editor_y - 1,
        )
    )

_static_one_up_totals = {
    stage_name: sum(
        definition.stage_name == stage_name
        for definition in _one_up_block_definitions
    )
    for stage_name in _ONE_UP_BLOCK_NAMES_BY_STAGE
}
STATIC_ONE_UP_BLOCK_DEFINITIONS = tuple(
    replace(definition, name=f"{definition.stage_name} 1-Up Block")
    if _static_one_up_totals[definition.stage_name] == 1
    else definition
    for definition in _one_up_block_definitions
)
if len(STATIC_ONE_UP_BLOCK_DEFINITIONS) != 42:
    raise ValueError("The A2DE 1-Up block catalog must contain exactly 42 placements.")
if len({definition.name for definition in STATIC_ONE_UP_BLOCK_DEFINITIONS}) != len(STATIC_ONE_UP_BLOCK_DEFINITIONS):
    raise ValueError("The A2DE 1-Up block catalog contains duplicate location names.")

def _static_blocksanity_definition(spec: tuple) -> BlocksanityDefinition:
    """Apply live course identities to the generated physical block record."""
    (
        stable_uid,
        stable_key,
        old_name,
        _old_stage_name,
        location_id_offset,
        _old_world_index,
        _old_runtime_level,
        _old_runtime_area,
        runtime_x,
        runtime_y,
        object_id,
    ) = spec
    source_course = stable_key.split("course/", 1)[1].split("_bgdat.bin", 1)[0]
    world_index = _COURSE_PREFIX_TO_WORLD_INDEX[source_course[0]]
    course_number = int(source_course[1:3])
    stage_name = FULL_LEVEL_CATALOG[f"World {world_index + 1}"][course_number - 1]
    block_suffix = old_name.split(" Blocksanity Block ", 1)[1]
    return BlocksanityDefinition(
        stable_uid=stable_uid,
        stable_key=stable_key,
        name=f"{stage_name} Blocksanity Block {block_suffix}",
        stage_name=stage_name,
        location_id_offset=location_id_offset,
        world_index=world_index,
        runtime_level=_runtime_level_for_stage_name(stage_name),
        runtime_area=RUNTIME_AREA_OFFSET_BY_SOURCE_COURSE[source_course],
        runtime_x=runtime_x,
        runtime_y=runtime_y,
        object_id=object_id,
    )


STATIC_BLOCKSANITY_DEFINITIONS = tuple(
    _static_blocksanity_definition(spec) for spec in BLOCKSANITY_SPECS
)
if len(STATIC_BLOCKSANITY_DEFINITIONS) != BLOCKSANITY_STATIC_COUNT:
    raise ValueError("The generated A2DE Blocksanity count does not match its catalog.")
if len({definition.name for definition in STATIC_BLOCKSANITY_DEFINITIONS}) != len(STATIC_BLOCKSANITY_DEFINITIONS):
    raise ValueError("The A2DE Blocksanity catalog contains duplicate location names.")
if len({definition.stable_uid for definition in STATIC_BLOCKSANITY_DEFINITIONS}) != len(STATIC_BLOCKSANITY_DEFINITIONS):
    raise ValueError("The A2DE Blocksanity catalog contains duplicate stable UIDs.")

_moving_blocksanity_counts: dict[str, int] = defaultdict(int)
_moving_one_up_counts: dict[str, int] = defaultdict(int)
_moving_bonus_blocksanity_counts: dict[str, int] = defaultdict(int)
_moving_bonus_one_up_counts: dict[str, int] = defaultdict(int)
_moving_blocksanity_definitions: list[MovingBlockDefinition] = []
_moving_one_up_definitions: list[MovingBlockDefinition] = []
for source_course, record_offset, editor_x, editor_y, sprite_settings in SPRITE_290_PLACEMENTS:
    world_index = _COURSE_PREFIX_TO_WORLD_INDEX[source_course[0]]
    course_number = int(source_course[1:3])
    area_number = int(source_course[4:])
    stage_name = FULL_LEVEL_CATALOG[f"World {world_index + 1}"][course_number - 1]
    stable_key = f"course/{source_course}.bin@block7+0x{record_offset:04X}"
    stable_uid = hashlib.sha256(stable_key.encode("ascii")).hexdigest()[:16]
    is_one_up = sprite_settings & 0x0F == SPRITE_290_ONE_UP_ITEM
    is_bonus_area = source_course == "F02_2"

    if is_one_up:
        if is_bonus_area:
            _moving_bonus_one_up_counts[stage_name] += 1
            name = (
                f"{stage_name} Bonus Area Flying 1-Up Block "
                f"{_moving_bonus_one_up_counts[stage_name]}"
            )
        else:
            _moving_one_up_counts[stage_name] += 1
            name = f"{stage_name} Flying 1-Up Block {_moving_one_up_counts[stage_name]}"
        location_id_offset = None
    else:
        if is_bonus_area:
            _moving_bonus_blocksanity_counts[stage_name] += 1
            name = (
                f"{stage_name} Bonus Area Blocksanity Flying Block "
                f"{_moving_bonus_blocksanity_counts[stage_name]}"
            )
        else:
            _moving_blocksanity_counts[stage_name] += 1
            name = f"{stage_name} Blocksanity Flying Block {_moving_blocksanity_counts[stage_name]}"
        location_id_offset = (
            0x4000 + BLOCKSANITY_STATIC_ID_SPAN + len(_moving_blocksanity_definitions)
        )

    definition = MovingBlockDefinition(
        stable_uid=stable_uid,
        stable_key=stable_key,
        name=name,
        stage_name=stage_name,
        location_id_offset=location_id_offset,
        world_index=world_index,
        source_course=source_course,
        area_number=area_number,
        runtime_level=_runtime_level_for_stage_name(stage_name),
        runtime_area=RUNTIME_AREA_OFFSET_BY_SOURCE_COURSE[source_course],
        editor_x=editor_x,
        editor_y=editor_y,
        runtime_x=editor_x,
        runtime_y=-editor_y - 1,
        sprite_id=SPRITE_290_ID,
        sprite_settings=sprite_settings,
    )
    if is_one_up:
        _moving_one_up_definitions.append(definition)
    else:
        _moving_blocksanity_definitions.append(definition)

MOVING_BLOCKSANITY_DEFINITIONS = tuple(_moving_blocksanity_definitions)
_moving_one_up_group_totals = {
    (definition.stage_name, definition.source_course == "F02_2"): sum(
        other.stage_name == definition.stage_name
        and (other.source_course == "F02_2") == (definition.source_course == "F02_2")
        for other in _moving_one_up_definitions
    )
    for definition in _moving_one_up_definitions
}
MOVING_ONE_UP_BLOCK_DEFINITIONS = tuple(
    replace(
        definition,
        name=(
            f"{definition.stage_name} Bonus Area Flying 1-Up Block"
            if definition.source_course == "F02_2"
            else f"{definition.stage_name} Flying 1-Up Block"
        ),
    )
    if _moving_one_up_group_totals[
        (definition.stage_name, definition.source_course == "F02_2")
    ] == 1
    else definition
    for definition in _moving_one_up_definitions
)
WORLD_6_2_BONUS_AREA_LOCATION_NAMES = frozenset(
    definition.name
    for definition in (*MOVING_BLOCKSANITY_DEFINITIONS, *MOVING_ONE_UP_BLOCK_DEFINITIONS)
    if definition.source_course == "F02_2"
)
if len(WORLD_6_2_BONUS_AREA_LOCATION_NAMES) != 128:
    raise ValueError("World 6-2 Bonus Area must contain exactly 128 flying blocks.")
if len(MOVING_BLOCKSANITY_DEFINITIONS) != SPRITE_290_BLOCKSANITY_COUNT:
    raise ValueError("The Sprite-290 Blocksanity catalog count is invalid.")
if len(MOVING_ONE_UP_BLOCK_DEFINITIONS) != SPRITE_290_ONE_UP_COUNT:
    raise ValueError("The Sprite-290 1-Up catalog count is invalid.")

ONE_UP_BLOCK_DEFINITIONS = (
    *STATIC_ONE_UP_BLOCK_DEFINITIONS,
    *MOVING_ONE_UP_BLOCK_DEFINITIONS,
)
BLOCKSANITY_DEFINITIONS = (
    *STATIC_BLOCKSANITY_DEFINITIONS,
    *MOVING_BLOCKSANITY_DEFINITIONS,
)
if len({definition.name for definition in ONE_UP_BLOCK_DEFINITIONS}) != len(ONE_UP_BLOCK_DEFINITIONS):
    raise ValueError("The combined 1-Up block catalog contains duplicate location names.")
if len({definition.name for definition in BLOCKSANITY_DEFINITIONS}) != len(BLOCKSANITY_DEFINITIONS):
    raise ValueError("The combined Blocksanity catalog contains duplicate location names.")


W1_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 1-1", 0, 0, 1),
    StageDefinition("World 1-2", 0, 1, 2, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 1-3", 0, 2, 3),
    StageDefinition("World 1-Tower", 0, 10, 4, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 1-4", 0, 4, 5),
    StageDefinition("World 1-5", 0, 5, 6),
    StageDefinition("World 1-Castle", 0, 15, 7),
    StageDefinition("World 1-A", 0, 6, 12),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 0),
    *(stage for stage in STATIC_MAP_REWARDS if stage.world_index == 0),
)

W2_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 2-1", 1, 0, 26),
    StageDefinition("World 2-2", 1, 1, 27),
    StageDefinition("World 2-3", 1, 2, 28, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 2-Tower", 1, 10, 30),
    StageDefinition("World 2-4", 1, 4, 29, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 2-5", 1, 5, 32),
    StageDefinition("World 2-6", 1, 7, 34),
    StageDefinition("World 2-Castle", 1, 15, 35, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 2-A", 1, 6, 37, secret_exit_status=SecretExitStatus.EXISTS),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 1),
)

W3_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 3-1", 2, 0, 52),
    StageDefinition("World 3-A", 2, 6, 61),
    StageDefinition("World 3-2", 2, 1, 54, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 3-Tower", 2, 10, 55),
    StageDefinition("World 3-3", 2, 2, 57),
    StageDefinition("World 3-Ghost House", 2, 4, 58, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 3-B", 2, 5, 63),
    StageDefinition("World 3-C", 2, 7, 65),
    StageDefinition("World 3-Castle", 2, 15, 60),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 2),
)

W4_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 4-1", 3, 0, 76, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 4-2", 3, 1, 77),
    StageDefinition("World 4-3", 3, 2, 78),
    StageDefinition("World 4-Tower", 3, 10, 79),
    StageDefinition("World 4-A", 3, 6, 89),
    StageDefinition("World 4-4", 3, 4, 81),
    StageDefinition("World 4-Ghost House", 3, 5, 83, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 4-5", 3, 7, 84),
    StageDefinition("World 4-6", 3, 8, 85),
    StageDefinition("World 4-Castle", 3, 15, 86),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 3),
)

W5_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 5-1", 4, 0, 101),
    StageDefinition("World 5-2", 4, 1, 103, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 5-A", 4, 6, 113),
    StageDefinition("World 5-Tower", 4, 10, 105),
    StageDefinition("World 5-3", 4, 2, 107),
    StageDefinition("World 5-Ghost House", 4, 4, 108, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 5-B", 4, 5, 116, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 5-C", 4, 7, 118),
    StageDefinition("World 5-4", 4, 8, 110),
    StageDefinition("World 5-Castle", 4, 15, 111, secret_exit_status=SecretExitStatus.EXISTS),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 4),
)

W6_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 6-1", 5, 0, 127),
    StageDefinition("World 6-2", 5, 1, 129),
    StageDefinition("World 6-Tower 1", 5, 10, 130),
    StageDefinition("World 6-3", 5, 2, 131),
    StageDefinition("World 6-4", 5, 4, 132),
    StageDefinition("World 6-Tower 2", 5, 5, 133),
    StageDefinition("World 6-5", 5, 6, 135),
    StageDefinition("World 6-6", 5, 7, 136),
    StageDefinition("World 6-Castle", 5, 15, 137),
    StageDefinition("World 6-A", 5, 8, 138),
    StageDefinition("World 6-B", 5, 9, 144),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 5),
)

W7_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 7-1", 6, 0, 151),
    StageDefinition("World 7-Ghost House", 6, 1, 152, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 7-2", 6, 2, 153),
    StageDefinition("World 7-3", 6, 3, 154),
    StageDefinition("World 7-Tower", 6, 10, 155),
    StageDefinition("World 7-4", 6, 4, 156, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 7-5", 6, 5, 157, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 7-A", 6, 6, 158),
    StageDefinition("World 7-6", 6, 7, 160, secret_exit_status=SecretExitStatus.EXISTS),
    StageDefinition("World 7-7", 6, 8, 167),
    StageDefinition("World 7-Castle", 6, 15, 166),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 6),
)

W8_LEVELS: tuple[StageDefinition, ...] = (
    StageDefinition("World 8-1", 7, 0, 176),
    StageDefinition("World 8-2", 7, 1, 177),
    StageDefinition("World 8-Tower 1", 7, 10, 178),
    StageDefinition("World 8-3", 7, 2, 179),
    StageDefinition("World 8-4", 7, 4, 180),
    StageDefinition("World 8-Castle", 7, 15, 181),
    StageDefinition("World 8-5", 7, 5, 182),
    StageDefinition("World 8-6", 7, 6, 183),
    StageDefinition("World 8-7", 7, 7, 184),
    StageDefinition("World 8-Tower 2", 7, 8, 185),
    StageDefinition("World 8-8", 7, 9, 186),
    StageDefinition("World 8-Bowser's Castle", 7, 11, 187),
    *(stage for stage in STATIC_TOAD_HOUSES if stage.world_index == 7),
)

ALL_WORLDS: tuple[tuple[StageDefinition, ...], ...] = (
    W1_LEVELS, W2_LEVELS, W3_LEVELS, W4_LEVELS,
    W5_LEVELS, W6_LEVELS, W7_LEVELS, W8_LEVELS,
)
ALL_ACTIVE_DEFINITIONS = tuple(stage for world in ALL_WORLDS for stage in world)
ACTIVE_STAGE_DEFINITIONS = tuple(
    stage for stage in ALL_ACTIVE_DEFINITIONS if stage.kind is LocationKind.STAGE
)
RUNTIME_COURSE_TO_STAGE_NAME = {
    (stage.world_index, _runtime_level_for_stage_name(stage.name)): stage.name
    for stage in ACTIVE_STAGE_DEFINITIONS
}
if len(RUNTIME_COURSE_TO_STAGE_NAME) != len(ACTIVE_STAGE_DEFINITIONS):
    raise ValueError("Active NSMBDS stages contain duplicate runtime course identities.")

BOSS_LOCATION_DEFINITIONS: tuple[BossLocationDefinition, ...] = (
    BossLocationDefinition("World 1-Castle", "Bowser", ("World 1-Castle Goal",)),
    BossLocationDefinition(
        "World 2-Castle",
        "Mummipokey",
        ("World 2-Castle Goal", "World 2-Castle Secret Exit"),
    ),
    BossLocationDefinition("World 3-Castle", "Cheepskipper", ("World 3-Castle Goal",)),
    BossLocationDefinition("World 4-Castle", "Mega Goomba", ("World 4-Castle Goal",)),
    BossLocationDefinition(
        "World 5-Castle",
        "Petey Piranha",
        ("World 5-Castle Goal", "World 5-Castle Secret Exit"),
    ),
    BossLocationDefinition("World 6-Castle", "Monty Tank", ("World 6-Castle Goal",)),
    BossLocationDefinition("World 7-Castle", "Lakithunder", ("World 7-Castle Goal",)),
    BossLocationDefinition("World 8-Castle", "Dry Bowser", ("World 8-Castle Goal",)),
    BossLocationDefinition(
        "World 8-Bowser's Castle",
        "Bowser & Bowser Jr.",
        ("World 8-Bowser's Castle Goal",),
    ),
)
BOSS_LOCATION_BY_STAGE = {
    definition.stage_name: definition for definition in BOSS_LOCATION_DEFINITIONS
}
BOSS_LOCATION_NAMES = tuple(definition.name for definition in BOSS_LOCATION_DEFINITIONS)
BOSS_LOCATION_COMPLETION_SOURCES = {
    definition.name: definition.completion_sources
    for definition in BOSS_LOCATION_DEFINITIONS
}

_unknown_boss_stages = set(BOSS_LOCATION_BY_STAGE) - {
    stage.name for stage in ACTIVE_STAGE_DEFINITIONS
}
if _unknown_boss_stages:
    raise ValueError(f"Boss catalog references unknown stages: {_unknown_boss_stages}")

# Runtime course level (world, level) RAM pair.
RED_COIN_COURSE_LEVELS: dict[str, int] = {
    "World 1-1": 0x01,
    "World 1-3": 0x03,
    "World 1-5": 0x05,
    "World 1-A": 0x09,
    "World 2-Tower": 0x0D,
    "World 3-1": 0x01,
    "World 3-2": 0x02,
    "World 3-3": 0x03,
    "World 3-A": 0x09,
    "World 4-2": 0x02,
    "World 4-3": 0x03,
    "World 4-Tower": 0x0D,
    "World 4-4": 0x04,
    "World 4-6": 0x06,
    "World 5-4": 0x04,
    "World 5-A": 0x09,
    "World 6-2": 0x02,
    "World 6-3": 0x03,
    "World 6-5": 0x05,
    "World 6-6": 0x06,
    "World 7-1": 0x01,
    "World 7-2": 0x02,
    "World 7-3": 0x03,
    "World 7-4": 0x04,
    "World 7-7": 0x07,
    "World 8-3": 0x03,
    "World 8-7": 0x07,
    "World 8-Tower 2": 0x15,
}

RED_COIN_CHALLENGE_NAMES_BY_STAGE: dict[str, tuple[str, ...]] = {
    stage_name: (
        (f"{stage_name} Red Coin Challenge 1", f"{stage_name} Red Coin Challenge 2")
        if stage_name == "World 3-1"
        else (f"{stage_name} Red Coin Challenge",)
    )
    for stage_name in RED_COIN_COURSE_LEVELS
}

_active_stage_names = {stage.name for stage in ACTIVE_STAGE_DEFINITIONS}
_unknown_red_coin_stages = set(RED_COIN_COURSE_LEVELS) - _active_stage_names
if _unknown_red_coin_stages:
    raise ValueError(f"Red Coin catalog references unknown stages: {_unknown_red_coin_stages}")

# These assignments preserve every currently shipped stage ID. Future stages
# must receive an unused index from their world's reserved sixteen-index block.
ACTIVE_LOCATION_ID_INDICES = {
    stage.name: (stage.world_index, stage.location_index)
    for stage in ALL_ACTIVE_DEFINITIONS
}

LOCATION_TABLE: dict[str, int] = {}
LOCATION_RAM_MAP: dict[str, tuple[int, int]] = {}
ONE_UP_BLOCK_LOCATION_ID_START = BASE_ID + 0x3000

for stage in ALL_ACTIVE_DEFINITIONS:
    LOCATION_TABLE[f"{stage.name} Goal"] = _loc_id(stage.world_index, stage.location_index, SLOT_GOAL)
    goal_ram_offset = stage.goal_ram_offset if stage.goal_ram_offset is not None else stage.ram_offset
    LOCATION_RAM_MAP[f"{stage.name} Goal"] = (goal_ram_offset, 0x10)
    boss_definition = BOSS_LOCATION_BY_STAGE.get(stage.name)
    if boss_definition is not None:
        LOCATION_TABLE[boss_definition.name] = _loc_id(
            stage.world_index, stage.location_index, SLOT_BOSS
        )
    if stage.has_star_coins:
        for coin_number, coin_slot, coin_bit in (
            (1, SLOT_COIN_1, 0x01),
            (2, SLOT_COIN_2, 0x02),
            (3, SLOT_COIN_3, 0x04),
        ):
            location_name = f"{stage.name} Star Coin {coin_number}"
            LOCATION_TABLE[location_name] = _loc_id(stage.world_index, stage.location_index, coin_slot)
            LOCATION_RAM_MAP[location_name] = (stage.ram_offset, coin_bit)
    if stage.name in RED_COIN_COURSE_LEVELS:
        for challenge_slot, location_name in zip(
            (SLOT_RED_COIN, SLOT_RED_COIN_2),
            RED_COIN_CHALLENGE_NAMES_BY_STAGE[stage.name],
        ):
            LOCATION_TABLE[location_name] = _loc_id(
                stage.world_index, stage.location_index, challenge_slot
            )
    if stage.secret_exit_status is SecretExitStatus.EXISTS:
        LOCATION_TABLE[f"{stage.name} Secret Exit"] = _loc_id(
            stage.world_index, stage.location_index, SLOT_SECRET
        )

for block_index, definition in enumerate(ONE_UP_BLOCK_DEFINITIONS):
    LOCATION_TABLE[definition.name] = ONE_UP_BLOCK_LOCATION_ID_START + block_index

for definition in BLOCKSANITY_DEFINITIONS:
    LOCATION_TABLE[definition.name] = BASE_ID + definition.location_id_offset

# Secret exits use persistent world-map flags outside the normal level block.
LOCATION_RAM_MAP["World 1-2 Secret Exit"] = (0xD2, 0xC0)
LOCATION_RAM_MAP["World 1-Tower Secret Exit"] = (0xD4, 0xC0)
LOCATION_RAM_MAP["World 2-3 Secret Exit"] = (0x0F1, 0xC0)
LOCATION_RAM_MAP["World 2-A Secret Exit"] = (0xF2, 0xC0)
LOCATION_RAM_MAP["World 2-4 Secret Exit"] = (0xF5, 0xC0)
LOCATION_RAM_MAP["World 2-Castle Secret Exit"] = (0x2F4, 0x01)
LOCATION_RAM_MAP["World 3-2 Secret Exit"] = (0x111, 0xC0)
LOCATION_RAM_MAP["World 3-Ghost House Secret Exit"] = (0x117, 0xC0)
LOCATION_RAM_MAP["World 4-1 Secret Exit"] = (0x12E, 0xC0)
LOCATION_RAM_MAP["World 4-Ghost House Secret Exit"] = (0x133, 0xC0)
LOCATION_RAM_MAP["World 5-2 Secret Exit"] = (0x14B, 0xC0)
LOCATION_RAM_MAP["World 5-Ghost House Secret Exit"] = (0x155, 0xC0)
LOCATION_RAM_MAP["World 5-B Secret Exit"] = (0x154, 0xC0)
LOCATION_RAM_MAP["World 5-Castle Secret Exit"] = (0x2F4, 0x02)
LOCATION_RAM_MAP["World 7-Ghost House Secret Exit"] = (0x189, 0xC0)
LOCATION_RAM_MAP["World 7-4 Secret Exit"] = (0x18B, 0xC0)
LOCATION_RAM_MAP["World 7-5 Secret Exit"] = (0x183, 0xC0)
LOCATION_RAM_MAP["World 7-6 Secret Exit"] = (0x18F, 0xC0)

SECRET_EXIT_RAM_REQUIREMENTS: dict[str, tuple[tuple[int, int], ...]] = {
    "World 1-2 Secret Exit": ((0xD2, 0xC0), (0xDE, 0xC0)),
    "World 1-Tower Secret Exit": ((0xD4, 0xC0),),
    "World 2-3 Secret Exit": ((0x0F1, 0xC0),),
    "World 2-A Secret Exit": ((0xF2, 0xC0),),
    "World 2-4 Secret Exit": ((0xF5, 0xC0), (0xF6, 0xC0)),
    "World 2-Castle Secret Exit": ((35, 0x10), (0x2F4, 0x01)),
    "World 3-2 Secret Exit": ((0x111, 0xC0),),
    "World 3-Ghost House Secret Exit": ((0x117, 0xC0),),
    "World 4-1 Secret Exit": ((0x12E, 0xC0), (0x12F, 0xC0)),
    "World 4-Ghost House Secret Exit": ((0x133, 0xC0),),
    "World 5-2 Secret Exit": ((0x14B, 0xC0),),
    "World 5-Ghost House Secret Exit": ((0x155, 0xC0),),
    "World 5-B Secret Exit": ((0x154, 0xC0),),
    "World 5-Castle Secret Exit": ((111, 0x10), (0x2F4, 0x02)),
    "World 7-Ghost House Secret Exit": ((0x189, 0xC0),),
    "World 7-4 Secret Exit": ((0x18B, 0xC0), (0x18C, 0xC0)),
    "World 7-5 Secret Exit": ((0x183, 0xC0), (0x184, 0xC0)),
    "World 7-6 Secret Exit": ((0x18F, 0xC0), (0x190, 0xC0)),
}

UNVERIFIED_SECRET_EXIT_CANDIDATES: tuple[str, ...] = ()

ACTIVE_STAR_COIN_COUNT = sum(" Star Coin " in name for name in LOCATION_TABLE)
RED_COIN_LOCATION_NAMES = frozenset(
    location_name
    for location_names in RED_COIN_CHALLENGE_NAMES_BY_STAGE.values()
    for location_name in location_names
)
RED_COIN_LOCATION_IDS = frozenset(LOCATION_TABLE[name] for name in RED_COIN_LOCATION_NAMES)
ONE_UP_BLOCK_LOCATION_NAMES = frozenset(definition.name for definition in ONE_UP_BLOCK_DEFINITIONS)
ONE_UP_BLOCK_LOCATION_IDS = frozenset(
    LOCATION_TABLE[name] for name in ONE_UP_BLOCK_LOCATION_NAMES
)
ONE_UP_BLOCK_LOCATION_NAMES_BY_WORLD = {
    world_index: tuple(
        definition.name for definition in ONE_UP_BLOCK_DEFINITIONS
        if definition.world_index == world_index
    )
    for world_index in range(8)
}
BLOCKSANITY_LOCATION_NAMES = frozenset(
    definition.name for definition in BLOCKSANITY_DEFINITIONS
)
BLOCKSANITY_LOCATION_IDS = frozenset(
    LOCATION_TABLE[name] for name in BLOCKSANITY_LOCATION_NAMES
)
BOSS_LOCATION_IDS = frozenset(LOCATION_TABLE[name] for name in BOSS_LOCATION_NAMES)
BLOCKSANITY_LOCATION_NAMES_BY_WORLD = {
    world_index: tuple(
        definition.name for definition in BLOCKSANITY_DEFINITIONS
        if definition.world_index == world_index
    )
    for world_index in range(8)
}
RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME = {
    (
        definition.world_index,
        definition.runtime_level,
        definition.runtime_area,
        definition.runtime_x,
        definition.runtime_y,
    ): definition.name
    for definition in STATIC_BLOCKSANITY_DEFINITIONS
}
if len(RUNTIME_BLOCK_TO_BLOCKSANITY_LOCATION_NAME) != len(STATIC_BLOCKSANITY_DEFINITIONS):
    raise ValueError("The A2DE Blocksanity catalog has duplicate runtime block keys.")
WORLD_TILE_TO_ONE_UP_LOCATION_NAME = {
    (definition.world_index, definition.runtime_x, definition.runtime_y): definition.name
    for definition in STATIC_ONE_UP_BLOCK_DEFINITIONS
}
if len(WORLD_TILE_TO_ONE_UP_LOCATION_NAME) != len(STATIC_ONE_UP_BLOCK_DEFINITIONS):
    raise ValueError("The A2DE 1-Up block catalog has duplicate runtime world/tile keys.")
RUNTIME_BLOCK_TO_ONE_UP_LOCATION_NAME = {
    (
        definition.world_index,
        _runtime_level_for_stage_name(definition.stage_name),
        RUNTIME_AREA_OFFSET_BY_SOURCE_COURSE[definition.source_course],
        definition.runtime_x,
        definition.runtime_y,
    ): definition.name
    for definition in STATIC_ONE_UP_BLOCK_DEFINITIONS
}
if len(RUNTIME_BLOCK_TO_ONE_UP_LOCATION_NAME) != len(STATIC_ONE_UP_BLOCK_DEFINITIONS):
    raise ValueError("The A2DE 1-Up block catalog has duplicate full runtime block keys.")
RUNTIME_MOVING_BLOCK_TO_BLOCKSANITY_LOCATION_NAME = {
    (
        definition.world_index,
        definition.runtime_level,
        definition.runtime_area,
        definition.runtime_x,
        definition.runtime_y,
    ): definition.name
    for definition in MOVING_BLOCKSANITY_DEFINITIONS
}
if len(RUNTIME_MOVING_BLOCK_TO_BLOCKSANITY_LOCATION_NAME) != len(MOVING_BLOCKSANITY_DEFINITIONS):
    raise ValueError("The Sprite-290 Blocksanity catalog has duplicate runtime source keys.")
RUNTIME_MOVING_BLOCK_TO_ONE_UP_LOCATION_NAME = {
    (
        definition.world_index,
        definition.runtime_level,
        definition.runtime_area,
        definition.runtime_x,
        definition.runtime_y,
    ): definition.name
    for definition in MOVING_ONE_UP_BLOCK_DEFINITIONS
}
if len(RUNTIME_MOVING_BLOCK_TO_ONE_UP_LOCATION_NAME) != len(MOVING_ONE_UP_BLOCK_DEFINITIONS):
    raise ValueError("The Sprite-290 1-Up catalog has duplicate runtime source keys.")
COURSE_KEY_TO_RED_COIN_LOCATION_NAME = {
    (stage.world_index, RED_COIN_COURSE_LEVELS[stage.name]):
        RED_COIN_CHALLENGE_NAMES_BY_STAGE[stage.name][0]
    for stage in ACTIVE_STAGE_DEFINITIONS
    if stage.name in RED_COIN_COURSE_LEVELS
}
if len(COURSE_KEY_TO_RED_COIN_LOCATION_NAME) != len(RED_COIN_COURSE_LEVELS):
    raise ValueError("Red Coin catalog contains duplicate runtime course keys.")


def resolve_red_coin_location_name(
    world: int,
    level: int,
    area: int,
    player_x: int,
    counter_index: int,
) -> str | None:
    """Resolve a transient completion, including both rings in World 3-1."""
    if (world, level, area) == (2, 0x01, 45):
        # The vanilla USA course contains rings at editor X 41 and 219 in the
        # same area. Their eight-coin routes are separated by the midpoint.
        if player_x >= 130 or (player_x < 0 and counter_index == 2):
            return "World 3-1 Red Coin Challenge 2"
        return "World 3-1 Red Coin Challenge 1"
    return COURSE_KEY_TO_RED_COIN_LOCATION_NAME.get((world, level))


location_name_to_id: dict[str, int] = LOCATION_TABLE
