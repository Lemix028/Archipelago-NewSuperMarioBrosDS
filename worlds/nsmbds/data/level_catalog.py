"""Canonical New Super Mario Bros. DS story-mode level catalog for A2DE."""

FULL_LEVEL_CATALOG: dict[str, tuple[str, ...]] = {
    "World 1": (
        "World 1-1", "World 1-2", "World 1-3", "World 1-4",
        "World 1-5", "World 1-A", "World 1-Tower", "World 1-Castle",
    ),
    "World 2": (
        "World 2-1", "World 2-2", "World 2-3", "World 2-4",
        "World 2-5", "World 2-6", "World 2-A", "World 2-Tower",
        "World 2-Castle",
    ),
    "World 3": (
        "World 3-1", "World 3-2", "World 3-3", "World 3-A",
        "World 3-B", "World 3-C", "World 3-Ghost House",
        "World 3-Tower", "World 3-Castle",
    ),
    "World 4": (
        "World 4-1", "World 4-2", "World 4-3", "World 4-4",
        "World 4-5", "World 4-6", "World 4-A", "World 4-Ghost House",
        "World 4-Tower", "World 4-Castle",
    ),
    "World 5": (
        "World 5-1", "World 5-2", "World 5-3", "World 5-4",
        "World 5-A", "World 5-B", "World 5-C", "World 5-Ghost House",
        "World 5-Tower", "World 5-Castle",
    ),
    "World 6": (
        "World 6-1", "World 6-2", "World 6-3", "World 6-4",
        "World 6-5", "World 6-6", "World 6-A", "World 6-B",
        "World 6-Tower 1", "World 6-Tower 2", "World 6-Castle",
    ),
    "World 7": (
        "World 7-1", "World 7-2", "World 7-3", "World 7-4",
        "World 7-5", "World 7-6", "World 7-7", "World 7-A",
        "World 7-Ghost House", "World 7-Tower", "World 7-Castle",
    ),
    "World 8": (
        "World 8-1", "World 8-2", "World 8-3", "World 8-4",
        "World 8-5", "World 8-6", "World 8-7", "World 8-8",
        "World 8-Tower 1", "World 8-Tower 2", "World 8-Castle",
        "World 8-Bowser's Castle",
    ),
}

FULL_LEVEL_COUNT = sum(len(levels) for levels in FULL_LEVEL_CATALOG.values())
FULL_STAR_COIN_COUNT = FULL_LEVEL_COUNT * 3
