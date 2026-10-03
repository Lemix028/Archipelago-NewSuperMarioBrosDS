"""Seed-stable music catalog and assignment logic for NSMBDS USA A2DE."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from random import Random
from typing import Sequence

from .level_catalog import FULL_LEVEL_CATALOG


MUSIC_RANDOMIZATION_OFF = 0
MUSIC_RANDOMIZATION_LEVELS = 1
MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS = 2
MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS = 3
MUSIC_MAPPING_VERSION = 2

# These sequences contain the NSMBDS music-event command B0 02 01 00 80.
# Verified against the USA A2DE sound_data.sdat. Enemies such as the
# Blockhoppers in 2-5 use these events to jump.
BAH_SEQUENCE_IDS = frozenset({6, 9, 12, 14, 24, 26, 100, 101, 102, 103, 104, 106, 107})


class MusicCategory(str, Enum):
    LEVEL = "level"
    WORLD_MAP = "world_map"
    BOSS = "boss"
    TEMPORARY = "temporary"
    JINGLE = "jingle"
    MENU = "menu"
    MINIGAME = "minigame"
    CREDITS = "credits"
    AMBIENT = "ambient"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MusicTrack:
    key: str
    name: str
    sequence_id: int
    category: MusicCategory
    safe_for_levels: bool = False
    safe_for_world_maps: bool = False


@dataclass(frozen=True)
class LevelMusicContext:
    name: str
    course_prefix: str
    original_sequence_id: int


@dataclass(frozen=True)
class WorldMapMusicContext:
    name: str
    table_index: int
    original_sequence_id: int


def _track(
    sequence_id: int,
    key: str,
    name: str,
    category: MusicCategory,
    *,
    levels: bool = False,
    maps: bool = False,
) -> MusicTrack:
    return MusicTrack(key, name, sequence_id, category, levels, maps)


# Sequence IDs are the actual SDAT sequence indices
MUSIC_TRACKS: tuple[MusicTrack, ...] = (
    _track(0, "versus_ground", "Versus Ground", MusicCategory.MINIGAME),
    _track(1, "tower", "Tower", MusicCategory.LEVEL, levels=True, maps=True),
    _track(2, "starman", "Starman", MusicCategory.TEMPORARY),
    _track(3, "mega_mushroom", "Mega Mushroom", MusicCategory.TEMPORARY),
    _track(4, "course_clear", "Course Clear", MusicCategory.JINGLE),
    _track(5, "player_down", "Player Down", MusicCategory.JINGLE),
    _track(6, "desert", "Desert", MusicCategory.LEVEL, levels=True, maps=True),
    _track(7, "boss", "Boss", MusicCategory.BOSS),
    _track(9, "underground", "Underground", MusicCategory.LEVEL, levels=True, maps=True),
    _track(10, "bonus_room", "Bonus Room", MusicCategory.LEVEL, levels=True, maps=True),
    _track(11, "underwater", "Underwater", MusicCategory.LEVEL, levels=True, maps=True),
    _track(12, "volcano", "Volcano", MusicCategory.LEVEL, levels=True, maps=True),
    _track(14, "beach", "Beach", MusicCategory.LEVEL, levels=True, maps=True),
    _track(15, "bowser_jr", "Bowser Jr.", MusicCategory.BOSS),
    _track(16, "ghost_house", "Ghost House", MusicCategory.LEVEL, levels=True, maps=True),
    _track(17, "castle", "Castle", MusicCategory.LEVEL, levels=True, maps=True),
    _track(18, "switch", "Switch", MusicCategory.TEMPORARY),
    _track(19, "final_clear", "Final Clear", MusicCategory.JINGLE),
    _track(20, "game_over", "Game Over", MusicCategory.JINGLE),
    _track(21, "final_bowser", "Final Bowser", MusicCategory.BOSS),
    _track(22, "boss_clear", "Boss Clear", MusicCategory.JINGLE),
    _track(24, "athletic", "Athletic", MusicCategory.LEVEL, levels=True, maps=True),
    _track(25, "minigame", "Minigame", MusicCategory.MINIGAME),
    _track(26, "grassland", "Grassland", MusicCategory.LEVEL, levels=True, maps=True),
    _track(27, "course_select", "Course Select", MusicCategory.MENU),
    _track(28, "goal_fanfare", "Goal Fanfare", MusicCategory.JINGLE),
    _track(29, "toad_house", "Toad House", MusicCategory.MENU),
    _track(80, "lava_ambience", "Lava Ambience", MusicCategory.AMBIENT),
    _track(81, "desert_ambience", "Desert Ambience", MusicCategory.AMBIENT),
    _track(82, "water_ambience", "Water Ambience", MusicCategory.AMBIENT),
    _track(83, "underground_ambience", "Underground Ambience", MusicCategory.AMBIENT),
    _track(86, "sky_ambience", "Sky Ambience", MusicCategory.AMBIENT),
    *(
        _track(
            100 + index,
            f"world_{index + 1}",
            f"World {index + 1}",
            MusicCategory.WORLD_MAP,
            levels=True,
            maps=True,
        )
        for index in range(8)
    ),
)

TRACK_BY_ID = {track.sequence_id: track for track in MUSIC_TRACKS}
TRACK_BY_KEY = {track.key: track for track in MUSIC_TRACKS}
LEVEL_TRACKS = tuple(
    track for track in MUSIC_TRACKS
    if track.category is MusicCategory.LEVEL and track.safe_for_levels
)
WORLD_MAP_TRACKS = tuple(
    track for track in MUSIC_TRACKS
    if track.category is MusicCategory.WORLD_MAP and track.safe_for_world_maps
)
MIXED_LEVEL_TRACKS = tuple(
    track for track in MUSIC_TRACKS
    if track.safe_for_levels and track.safe_for_world_maps
)
SAFE_LEVEL_SEQUENCE_IDS = frozenset(track.sequence_id for track in LEVEL_TRACKS)
SAFE_MIXED_LEVEL_SEQUENCE_IDS = frozenset(
    track.sequence_id for track in MIXED_LEVEL_TRACKS
)
SAFE_WORLD_MAP_SEQUENCE_IDS = frozenset(track.sequence_id for track in WORLD_MAP_TRACKS)


_PRIMARY_LEVEL_SEQUENCE_IDS = (
    26, 9, 24, 26, 24, 26, 1, 17,
    6, 26, 6, 6, 6, 6, 14, 1, 17,
    14, 24, 14, 24, 24, 14, 16, 1, 17,
    26, 24, 26, 26, 26, 26, 26, 16, 1, 17,
    26, 26, 26, 24, 24, 26, 24, 16, 1, 17,
    24, 14, 26, 24, 26, 24, 26, 24, 1, 1, 17,
    24, 24, 26, 24, 26, 24, 24, 26, 16, 1, 17,
    16, 16, 16, 16, 12, 12, 9, 12, 1, 1, 17, 17,
)


def _build_level_contexts() -> tuple[LevelMusicContext, ...]:
    contexts: list[LevelMusicContext] = []
    primary_index = 0
    for world_index, levels in enumerate(FULL_LEVEL_CATALOG.values()):
        world_letter = chr(ord("A") + world_index)
        for course_index, name in enumerate(levels, 1):
            contexts.append(LevelMusicContext(
                name,
                f"{world_letter}{course_index:02d}",
                _PRIMARY_LEVEL_SEQUENCE_IDS[primary_index],
            ))
            primary_index += 1
    if primary_index != len(_PRIMARY_LEVEL_SEQUENCE_IDS):
        raise RuntimeError("Level music context table does not match the story level catalog.")
    return tuple(contexts)


LEVEL_MUSIC_CONTEXTS = _build_level_contexts()
LEVEL_CONTEXT_BY_NAME = {context.name: context for context in LEVEL_MUSIC_CONTEXTS}
WORLD_MAP_MUSIC_CONTEXTS = tuple(
    WorldMapMusicContext(f"World {index + 1}", index, 100 + index)
    for index in range(8)
)


def _avoid_self_matches(
    contexts: Sequence[LevelMusicContext | WorldMapMusicContext],
    assignments: list[MusicTrack],
) -> None:
    """Remove self-matches with bounded swaps when the pool makes that possible."""
    for index, context in enumerate(contexts):
        if assignments[index].sequence_id != context.original_sequence_id:
            continue
        for other in range(len(assignments)):
            if other == index:
                continue
            if (
                assignments[other].sequence_id != context.original_sequence_id
                and assignments[index].sequence_id != contexts[other].original_sequence_id
            ):
                assignments[index], assignments[other] = assignments[other], assignments[index]
                break


def balanced_music_assignment(
    contexts: Sequence[LevelMusicContext | WorldMapMusicContext],
    tracks: Sequence[MusicTrack],
    rng: Random,
) -> dict[str, int]:
    """Distribute tracks in shuffled cycles, terminating for every pool size."""
    if not contexts:
        return {}
    if not tracks:
        raise ValueError("Cannot assign music from an empty track pool.")

    assignments: list[MusicTrack] = []
    while len(assignments) < len(contexts):
        cycle = list(tracks)
        rng.shuffle(cycle)
        assignments.extend(cycle[:len(contexts) - len(assignments)])
    _avoid_self_matches(contexts, assignments)
    return {
        context.name: track.sequence_id
        for context, track in zip(contexts, assignments)
    }


def _assign_compatible_level_music(
    rng: Random, tracks: Sequence[MusicTrack],
) -> dict[str, int]:
    """Keep the presence of music events in each level's primary theme."""
    result: dict[str, int] = {}
    for has_bah in (True, False):
        contexts = tuple(
            context for context in LEVEL_MUSIC_CONTEXTS
            if (context.original_sequence_id in BAH_SEQUENCE_IDS) == has_bah
        )
        compatible = tuple(
            track for track in tracks
            if (track.sequence_id in BAH_SEQUENCE_IDS) == has_bah
        )
        result.update(balanced_music_assignment(contexts, compatible, rng))
    return result


def _assign_mixed_world_maps(
    rng: Random, levels: dict[str, int],
) -> dict[str, int]:
    """Use the least-used tracks so the mixed pool stays balanced overall."""
    level_counts = Counter(levels.values())
    counts = {track.sequence_id: level_counts[track.sequence_id]
              for track in MIXED_LEVEL_TRACKS}
    assignments: list[MusicTrack] = []
    for _context in WORLD_MAP_MUSIC_CONTEXTS:
        minimum = min(counts.values())
        candidates = [track for track in MIXED_LEVEL_TRACKS
                      if counts[track.sequence_id] == minimum]
        track = rng.choice(candidates)
        assignments.append(track)
        counts[track.sequence_id] += 1
    _avoid_self_matches(WORLD_MAP_MUSIC_CONTEXTS, assignments)
    return {
        context.name: track.sequence_id
        for context, track in zip(WORLD_MAP_MUSIC_CONTEXTS, assignments)
    }


def generate_music_mapping(rng: Random, mode: int) -> tuple[dict[str, int], dict[str, int]]:
    if mode == MUSIC_RANDOMIZATION_OFF:
        return {}, {}
    if mode not in (
        MUSIC_RANDOMIZATION_LEVELS,
        MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS,
        MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS,
    ):
        raise ValueError(f"Unsupported music randomization mode {mode}.")

    if mode == MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS:
        levels = _assign_compatible_level_music(rng, MIXED_LEVEL_TRACKS)
        maps = _assign_mixed_world_maps(rng, levels)
    else:
        levels = _assign_compatible_level_music(rng, LEVEL_TRACKS)
        maps: dict[str, int] = {}
    if mode == MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS:
        maps = balanced_music_assignment(WORLD_MAP_MUSIC_CONTEXTS, WORLD_MAP_TRACKS, rng)
    return levels, maps


def validate_music_mapping(
    mode: int,
    level_mapping: dict[str, int],
    world_map_mapping: dict[str, int],
) -> None:
    if mode not in (
        MUSIC_RANDOMIZATION_OFF,
        MUSIC_RANDOMIZATION_LEVELS,
        MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS,
        MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS,
    ):
        raise ValueError(f"Unsupported music randomization mode {mode}.")
    expected_levels = set() if mode == MUSIC_RANDOMIZATION_OFF else set(LEVEL_CONTEXT_BY_NAME)
    expected_maps = (
        {context.name for context in WORLD_MAP_MUSIC_CONTEXTS}
        if mode in (
            MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS,
            MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS,
        ) else set()
    )
    if set(level_mapping) != expected_levels:
        raise ValueError("Level music mapping does not match the selected mode and level catalog.")
    if set(world_map_mapping) != expected_maps:
        raise ValueError("World-map music mapping does not match the selected mode.")
    safe_level_ids = (
        SAFE_MIXED_LEVEL_SEQUENCE_IDS
        if mode == MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS
        else SAFE_LEVEL_SEQUENCE_IDS
    )
    if any(value not in safe_level_ids for value in level_mapping.values()):
        raise ValueError("Level music mapping contains a sequence outside the safe pool.")
    if any(
        (level_mapping[name] in BAH_SEQUENCE_IDS)
        != (context.original_sequence_id in BAH_SEQUENCE_IDS)
        for name, context in LEVEL_CONTEXT_BY_NAME.items()
        if name in level_mapping
    ):
        raise ValueError("Level music mapping changes a level's music-event availability.")
    safe_world_map_ids = (
        SAFE_MIXED_LEVEL_SEQUENCE_IDS
        if mode == MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS
        else SAFE_WORLD_MAP_SEQUENCE_IDS
    )
    if any(value not in safe_world_map_ids for value in world_map_mapping.values()):
        raise ValueError("World-map music mapping contains a sequence outside the safe pool.")
    if (
        mode == MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS
        and set(world_map_mapping.values()) != SAFE_WORLD_MAP_SEQUENCE_IDS
    ):
        raise ValueError("World-map music mapping must be a one-to-one permutation.")


__all__ = [
    "BAH_SEQUENCE_IDS", "LEVEL_CONTEXT_BY_NAME", "LEVEL_MUSIC_CONTEXTS", "LEVEL_TRACKS",
    "MIXED_LEVEL_TRACKS", "MUSIC_MAPPING_VERSION", "MUSIC_RANDOMIZATION_LEVELS",
    "MUSIC_RANDOMIZATION_MIXED_LEVELS_AND_WORLD_MAPS",
    "MUSIC_RANDOMIZATION_LEVELS_AND_WORLD_MAPS", "MUSIC_RANDOMIZATION_OFF",
    "MUSIC_TRACKS", "SAFE_LEVEL_SEQUENCE_IDS", "SAFE_MIXED_LEVEL_SEQUENCE_IDS",
    "SAFE_WORLD_MAP_SEQUENCE_IDS",
    "TRACK_BY_ID", "WORLD_MAP_MUSIC_CONTEXTS", "WORLD_MAP_TRACKS",
    "balanced_music_assignment", "generate_music_mapping", "validate_music_mapping",
]
