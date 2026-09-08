"""Authoritative overworld-slot metadata for NSMBDS level randomization."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .level_catalog import FULL_LEVEL_CATALOG


LEVEL_RANDOMIZATION_OFF = 0
LEVEL_RANDOMIZATION_GLOBAL = 1
LEVEL_RANDOMIZATION_WITHIN_WORLD = 2
LEVEL_RANDOMIZATION_VERSION = 1


class LevelPool(StrEnum):
    """Mutually exclusive compatibility pool for one story level."""

    SECRET_EXIT = "secret_exit"
    TOWER = "tower"
    CASTLE = "castle"
    NORMAL = "normal"
    FINAL_CASTLE = "final_castle"


@dataclass(frozen=True)
class LevelSlotDefinition:
    """One overworld node and the vanilla story course loaded from it."""

    name: str
    world_number: int
    area_id: int
    overlay_node_offset: int
    pool: LevelPool


CLASSIC_SECRET_EXIT_STAGES = frozenset({
    "World 1-2", "World 1-Tower",
    "World 2-3", "World 2-4", "World 2-A",
    "World 3-2", "World 3-Ghost House",
    "World 4-1", "World 4-Ghost House",
    "World 5-2", "World 5-B", "World 5-Ghost House",
    "World 7-Ghost House", "World 7-4", "World 7-5", "World 7-6",
})

MINI_CASTLE_SECRET_EXIT_SLOTS = frozenset({"World 2-Castle", "World 5-Castle"})
FINAL_CASTLE_STAGE = "World 8-Bowser's Castle"


# Values are the global area identifiers stored in Overlay 8's world-map node
# table. Offsets address the decompressed USA A2DE Overlay 8 image. They were
# checked against all 80 vanilla node bytes, not inferred from file order.
_VANILLA_NODE_DATA: tuple[tuple[str, int, int], ...] = (
    ("World 1-1", 0, 111108), ("World 1-2", 3, 111120),
    ("World 1-3", 6, 111132), ("World 1-Tower", 14, 111144),
    ("World 1-4", 7, 111156), ("World 1-5", 10, 111168),
    ("World 1-Castle", 17, 111180), ("World 1-A", 12, 111240),

    ("World 2-1", 21, 111336), ("World 2-2", 24, 111348),
    ("World 2-3", 26, 111360), ("World 2-4", 28, 111372),
    ("World 2-Tower", 37, 111384), ("World 2-5", 30, 111408),
    ("World 2-6", 32, 111432), ("World 2-Castle", 40, 111444),
    ("World 2-A", 34, 111468),

    ("World 3-1", 44, 110232), ("World 3-2", 46, 110256),
    ("World 3-Tower", 61, 110268), ("World 3-3", 48, 110292),
    ("World 3-Ghost House", 58, 110304), ("World 3-Castle", 63, 110328),
    ("World 3-A", 51, 110340), ("World 3-B", 54, 110364),
    ("World 3-C", 56, 110388),

    ("World 4-1", 66, 110652), ("World 4-2", 67, 110664),
    ("World 4-3", 69, 110676), ("World 4-Tower", 83, 110688),
    ("World 4-4", 71, 110712), ("World 4-Ghost House", 80, 110736),
    ("World 4-5", 73, 110748), ("World 4-6", 76, 110760),
    ("World 4-Castle", 85, 110772), ("World 4-A", 78, 110808),

    ("World 5-1", 88, 112084), ("World 5-2", 89, 112108),
    ("World 5-Tower", 102, 112132), ("World 5-3", 91, 112156),
    ("World 5-Ghost House", 99, 112168), ("World 5-Castle", 104, 112204),
    ("World 5-A", 94, 112228), ("World 5-C", 97, 112288),
    ("World 5-B", 96, 112264), ("World 5-4", 93, 112192),

    ("World 6-1", 107, 111588), ("World 6-2", 109, 111612),
    ("World 6-Tower 1", 122, 111624), ("World 6-3", 111, 111636),
    ("World 6-4", 113, 111648), ("World 6-Tower 2", 124, 111660),
    ("World 6-5", 114, 111684), ("World 6-6", 116, 111696),
    ("World 6-Castle", 126, 111708), ("World 6-A", 119, 111720),
    ("World 6-B", 121, 111792),

    ("World 7-1", 129, 110436), ("World 7-Ghost House", 144, 110448),
    ("World 7-2", 130, 110460), ("World 7-3", 132, 110472),
    ("World 7-Tower", 147, 110484), ("World 7-4", 134, 110496),
    ("World 7-5", 135, 110508), ("World 7-A", 142, 110520),
    ("World 7-Castle", 149, 110544), ("World 7-6", 138, 110616),
    ("World 7-7", 141, 110628),

    ("World 8-1", 151, 110880), ("World 8-2", 153, 110892),
    ("World 8-Tower 1", 167, 110904), ("World 8-3", 156, 110916),
    ("World 8-4", 158, 110928), ("World 8-Castle", 171, 110940),
    ("World 8-5", 160, 110952), ("World 8-6", 162, 110964),
    ("World 8-7", 164, 110976), ("World 8-8", 165, 110988),
    ("World 8-Tower 2", 169, 111000),
    ("World 8-Bowser's Castle", 173, 111012),
)


def _pool_for_stage(stage_name: str) -> LevelPool:
    if stage_name == FINAL_CASTLE_STAGE:
        return LevelPool.FINAL_CASTLE
    if stage_name in CLASSIC_SECRET_EXIT_STAGES:
        return LevelPool.SECRET_EXIT
    suffix = stage_name.split("-", 1)[1]
    if suffix.startswith("Tower"):
        return LevelPool.TOWER
    if suffix == "Castle":
        return LevelPool.CASTLE
    return LevelPool.NORMAL


LEVEL_SLOTS: tuple[LevelSlotDefinition, ...] = tuple(
    LevelSlotDefinition(
        name,
        int(name.split(" ", 2)[1].split("-", 1)[0]),
        area_id,
        overlay_node_offset,
        _pool_for_stage(name),
    )
    for name, area_id, overlay_node_offset in _VANILLA_NODE_DATA
)
LEVEL_SLOT_BY_NAME = {slot.name: slot for slot in LEVEL_SLOTS}
LEVEL_AREA_ID_BY_NAME = {slot.name: slot.area_id for slot in LEVEL_SLOTS}
LEVEL_NODE_OFFSET_BY_NAME = {slot.name: slot.overlay_node_offset for slot in LEVEL_SLOTS}
ALL_STORY_LEVELS = tuple(slot.name for slot in LEVEL_SLOTS)
IDENTITY_LEVEL_MAPPING = {name: name for name in ALL_STORY_LEVELS}


def _stable_seed(seed_name: str, player: int, mode: int) -> int:
    material = "\0".join((
        str(seed_name), str(player), "nsmbds-level-randomization",
        str(mode), str(LEVEL_RANDOMIZATION_VERSION),
    )).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:16], "little")


def _derangement(values: tuple[str, ...], rng: random.Random) -> tuple[str, ...]:
    """Return a deterministic derangement, leaving singleton pools fixed."""
    if len(values) < 2:
        return values
    randomized = list(values)
    for _attempt in range(256):
        rng.shuffle(randomized)
        if all(source != target for source, target in zip(values, randomized)):
            return tuple(randomized)
    # Rejection has vanishing failure probability; retain a deterministic,
    # guaranteed-safe result even if a custom RNG behaves unexpectedly.
    return values[1:] + values[:1]


def generate_level_mapping(
    seed_name: str,
    player: int,
    mode: int,
) -> dict[str, str]:
    """Generate the canonical slot-to-content permutation for one player."""
    if mode == LEVEL_RANDOMIZATION_OFF:
        return dict(IDENTITY_LEVEL_MAPPING)
    if mode not in (LEVEL_RANDOMIZATION_GLOBAL, LEVEL_RANDOMIZATION_WITHIN_WORLD):
        raise ValueError(f"Unsupported level randomization mode: {mode}")

    rng = random.Random(_stable_seed(seed_name, player, mode))
    mapping = dict(IDENTITY_LEVEL_MAPPING)
    grouping_keys = sorted({
        (
            slot.pool,
            slot.world_number if mode == LEVEL_RANDOMIZATION_WITHIN_WORLD else 0,
        )
        for slot in LEVEL_SLOTS
        if slot.pool is not LevelPool.FINAL_CASTLE
    })
    for pool, world_number in grouping_keys:
        slots = tuple(
            slot.name
            for slot in LEVEL_SLOTS
            if slot.pool is pool
            and (not world_number or slot.world_number == world_number)
        )
        for destination, source in zip(slots, _derangement(slots, rng)):
            mapping[destination] = source

    validate_level_mapping(mapping, mode)
    return mapping


def validate_level_mapping(mapping: Mapping[str, str], mode: int) -> None:
    """Reject incomplete, non-bijective, or cross-pool mappings."""
    if mode not in (
        LEVEL_RANDOMIZATION_OFF,
        LEVEL_RANDOMIZATION_GLOBAL,
        LEVEL_RANDOMIZATION_WITHIN_WORLD,
    ):
        raise ValueError(f"Unsupported level randomization mode: {mode}")
    expected = set(ALL_STORY_LEVELS)
    if set(mapping) != expected or set(mapping.values()) != expected:
        raise ValueError("Level mapping must contain every story slot and level exactly once.")
    if mapping[FINAL_CASTLE_STAGE] != FINAL_CASTLE_STAGE:
        raise ValueError("World 8-Bowser's Castle must remain in its vanilla slot.")
    if mode == LEVEL_RANDOMIZATION_OFF and dict(mapping) != IDENTITY_LEVEL_MAPPING:
        raise ValueError("Disabled level randomization requires the identity mapping.")
    for slot_name, content_name in mapping.items():
        slot = LEVEL_SLOT_BY_NAME[slot_name]
        content = LEVEL_SLOT_BY_NAME[content_name]
        if slot.pool is not content.pool:
            raise ValueError(
                f"Incompatible level mapping {slot_name} -> {content_name}: "
                f"{slot.pool.value} cannot receive {content.pool.value}."
            )
        if (
            mode == LEVEL_RANDOMIZATION_WITHIN_WORLD
            and slot.world_number != content.world_number
        ):
            raise ValueError(
                f"Within-world mapping crosses worlds: {slot_name} -> {content_name}."
            )


def level_mapping_digest(mapping: Mapping[str, str]) -> str:
    """Return a stable short diagnostic digest for serialized mappings."""
    material = "\n".join(
        f"{slot}={mapping[slot]}" for slot in ALL_STORY_LEVELS
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def invert_level_mapping(mapping: Mapping[str, str]) -> dict[str, str]:
    validate_level_mapping(mapping, _infer_mapping_mode(mapping))
    return {content: slot for slot, content in mapping.items()}


def _infer_mapping_mode(mapping: Mapping[str, str]) -> int:
    """Infer the least restrictive validation mode for a received mapping."""
    if dict(mapping) == IDENTITY_LEVEL_MAPPING:
        return LEVEL_RANDOMIZATION_OFF
    if all(
        LEVEL_SLOT_BY_NAME[slot].world_number == LEVEL_SLOT_BY_NAME[content].world_number
        for slot, content in mapping.items()
    ):
        return LEVEL_RANDOMIZATION_WITHIN_WORLD
    return LEVEL_RANDOMIZATION_GLOBAL


def mapped_event_name(mapping: Mapping[str, str], vanilla_event_name: str) -> str:
    """Translate a slot-owned Goal/Secret Exit atom to its content check."""
    suffix = None
    for candidate in (" Goal", " Secret Exit"):
        if vanilla_event_name.endswith(candidate):
            suffix = candidate
            break
    if suffix is None:
        return vanilla_event_name
    slot_name = vanilla_event_name[:-len(suffix)]
    if slot_name not in mapping:
        return vanilla_event_name
    # Mini-Mario castle branches are properties of their map slots.
    if suffix == " Secret Exit" and slot_name in MINI_CASTLE_SECRET_EXIT_SLOTS:
        return vanilla_event_name
    return f"{mapping[slot_name]}{suffix}"


def mapping_from_slot_data(slot_data: Mapping[str, Any] | None) -> dict[str, str]:
    """Read and validate a mapping received by a client or tracker."""
    if not slot_data:
        return dict(IDENTITY_LEVEL_MAPPING)
    mode = int(slot_data.get("level_randomization", LEVEL_RANDOMIZATION_OFF))
    if mode == LEVEL_RANDOMIZATION_OFF:
        return dict(IDENTITY_LEVEL_MAPPING)
    if int(slot_data.get("level_randomization_version", -1)) != LEVEL_RANDOMIZATION_VERSION:
        raise ValueError("Unsupported NSMBDS level-randomization slot-data version.")
    raw_mapping = slot_data.get("level_mapping")
    if not isinstance(raw_mapping, Mapping):
        raise ValueError("Level-randomized slot data has no level_mapping.")
    mapping = {str(slot): str(content) for slot, content in raw_mapping.items()}
    validate_level_mapping(mapping, mode)
    digest = slot_data.get("level_mapping_digest")
    if digest and digest != level_mapping_digest(mapping):
        raise ValueError("NSMBDS level mapping digest does not match its contents.")
    return mapping


_catalog_names = {
    name for levels in FULL_LEVEL_CATALOG.values() for name in levels
}
if len(LEVEL_SLOTS) != 80 or len(LEVEL_SLOT_BY_NAME) != 80:
    raise ValueError("NSMBDS level randomization catalog must contain exactly 80 unique slots.")
if set(LEVEL_SLOT_BY_NAME) != _catalog_names:
    raise ValueError("NSMBDS level randomization catalog differs from the story catalog.")
if len(LEVEL_AREA_ID_BY_NAME.values()) != len(set(LEVEL_AREA_ID_BY_NAME.values())):
    raise ValueError("NSMBDS level randomization catalog contains duplicate area IDs.")
if len(LEVEL_NODE_OFFSET_BY_NAME.values()) != len(set(LEVEL_NODE_OFFSET_BY_NAME.values())):
    raise ValueError("NSMBDS level randomization catalog contains duplicate node offsets.")
_pool_counts = {
    pool: sum(slot.pool is pool for slot in LEVEL_SLOTS) for pool in LevelPool
}
if _pool_counts != {
    LevelPool.SECRET_EXIT: 16,
    LevelPool.TOWER: 9,
    LevelPool.CASTLE: 8,
    LevelPool.NORMAL: 46,
    LevelPool.FINAL_CASTLE: 1,
}:
    raise ValueError(f"Unexpected NSMBDS level pool sizes: {_pool_counts!r}")


__all__ = [
    "ALL_STORY_LEVELS",
    "CLASSIC_SECRET_EXIT_STAGES",
    "FINAL_CASTLE_STAGE",
    "IDENTITY_LEVEL_MAPPING",
    "LEVEL_AREA_ID_BY_NAME",
    "LEVEL_NODE_OFFSET_BY_NAME",
    "LEVEL_RANDOMIZATION_GLOBAL",
    "LEVEL_RANDOMIZATION_OFF",
    "LEVEL_RANDOMIZATION_VERSION",
    "LEVEL_RANDOMIZATION_WITHIN_WORLD",
    "LEVEL_SLOT_BY_NAME",
    "LEVEL_SLOTS",
    "LevelPool",
    "LevelSlotDefinition",
    "MINI_CASTLE_SECRET_EXIT_SLOTS",
    "generate_level_mapping",
    "invert_level_mapping",
    "level_mapping_digest",
    "mapped_event_name",
    "mapping_from_slot_data",
    "validate_level_mapping",
]
