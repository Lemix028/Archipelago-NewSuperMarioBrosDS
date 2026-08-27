"""Power-Up License modes and live-verified logical requirements."""

from __future__ import annotations

from dataclasses import dataclass


LICENSE_MODE_DISABLED = 0
LICENSE_MODE_SHORTCUTS_ONLY = 1
LICENSE_MODE_MAJOR_POWERUPS = 2
LICENSE_MODE_ALL_POWERUPS = 3

MINI_MUSHROOM_LICENSE = "Mini Mushroom Permit"
BLUE_SHELL_LICENSE = "Blue Shell Permit"
MEGA_MUSHROOM_LICENSE = "Mega Mushroom Permit"
TOUCHSCREEN_RESERVE_LICENSE = "Touchscreen Pocket Permit"
MUSHROOM_LICENSE = "Mushroom Permit"
FIRE_FLOWER_LICENSE = "Fire Flower Permit"


@dataclass(frozen=True)
class PowerUpAbilityRequirement:
    """One License and the individual locations whose logic requires it."""

    license_item: str
    locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class PowerUpAlternativeRequirement:
    """Alternative forms that can satisfy one location requirement."""

    license_items: tuple[str, ...]
    locations: tuple[str, ...]


LARGE_MARIO_LOCATIONS = (
    "World 1-1 Star Coin 3", "World 1-4 Star Coin 2", "World 1-4 1-Up Block",
    "World 2-2 Star Coin 2", "World 5-2 Star Coin 1",
    "World 5-3 Star Coin 2", "World 5-C Star Coin 3", "World 6-6 Star Coin 1",
    "World 6-Tower 2 Star Coin 2", "World 7-2 Star Coin 1",
    "World 7-6 Star Coin 1", "World 7-6 Secret Exit", "World 8-6 Star Coin 2",
    "World 1-2 Blocksanity Block 7", "World 1-2 Blocksanity Block 8",
    "World 2-5 Blocksanity Block 4", "World 2-5 Blocksanity Block 5",
    "World 2-5 Blocksanity Block 7", "World 2-5 Blocksanity Block 15",
    "World 2-5 Blocksanity Block 16", "World 2-5 Blocksanity Block 18",
    "World 2-5 Blocksanity Block 19", "World 4-5 Blocksanity Block 37",
    "World 5-2 Blocksanity Block 1", "World 5-4 Blocksanity Block 2",
    "World 5-A Blocksanity Block 4", "World 5-C Blocksanity Block 20",
    "World 5-C Blocksanity Block 22", "World 6-6 Blocksanity Block 5",
    "World 6-6 Blocksanity Block 6",
    *(f"World 5-C Blocksanity Block {index}" for index in range(1, 17)),
)


POWERUP_ABILITY_REQUIREMENTS: tuple[PowerUpAbilityRequirement, ...] = (
    PowerUpAbilityRequirement(
        MINI_MUSHROOM_LICENSE,
        locations=(
            "World 1-4 Star Coin 1",
            "World 2-4 Secret Exit",
            "World 2-Castle Star Coin 3",
            "World 2-Castle Secret Exit",
            "World 3-A Star Coin 3",
            "World 4-Ghost House Star Coin 3",
            "World 4-Ghost House Secret Exit",
            "World 5-Castle Secret Exit",
            "World 7-4 Secret Exit",
            "World 7-5 Star Coin 2",
            "World 7-A Star Coin 3",
            "World 8-4 Star Coin 3",
            "World 8-8 Star Coin 2",
            "World 2 Red Toad House 2 Goal",
            "World 2-Castle Blocksanity Block 13",
            "World 2-Castle Blocksanity Block 14",
            "World 3-A Blocksanity Block 12",
            "World 3-A Blocksanity Block 13",
            "World 4-4 Blocksanity Block 8",
            "World 5-3 Blocksanity Block 4",
            "World 5-3 Blocksanity Block 5",
            "World 6-1 Blocksanity Block 6",
            "World 7-4 Blocksanity Block 6",
            "World 7-4 Blocksanity Block 7",
            "World 7-4 Blocksanity Block 9",
            "World 7-4 Blocksanity Flying Block 1",
            "World 7-5 Blocksanity Block 28",
            "World 8-2 Blocksanity Block 6",
            "World 8-4 Blocksanity Block 10",
            "World 8-4 Blocksanity Block 11",
        ),
    ),
    PowerUpAbilityRequirement(
        BLUE_SHELL_LICENSE,
        locations=(
            "World 1-Tower Secret Exit",
            "World 3-Ghost House Star Coin 3",
            "World 5-B Secret Exit",
            "World 8-Bowser's Castle Star Coin 3",
            "World 1-Tower Blocksanity Block 11",
            "World 1-Tower Blocksanity Block 12",
            "World 1-Tower Blocksanity Block 13",
            "World 5-C Blocksanity Block 25",
            "World 5-C Blocksanity Block 26",
            "World 5-C Blocksanity Block 31",
            "World 5-C Blocksanity Block 32",
        ),
    ),
    PowerUpAbilityRequirement(
        MEGA_MUSHROOM_LICENSE,
        locations=(),
    ),
    PowerUpAbilityRequirement(TOUCHSCREEN_RESERVE_LICENSE),
)


POWERUP_ALTERNATIVE_REQUIREMENTS: tuple[PowerUpAlternativeRequirement, ...] = (
    PowerUpAlternativeRequirement(
        (MUSHROOM_LICENSE, FIRE_FLOWER_LICENSE, BLUE_SHELL_LICENSE, MEGA_MUSHROOM_LICENSE),
        locations=LARGE_MARIO_LOCATIONS,
    ),
)


from typing import Any


def active_license_items(options: Any) -> tuple[str, ...]:
    """Return active license items based on individual YAML options or slot_data dict."""
    def _bool(opt_name: str) -> bool:
        if isinstance(options, dict):
            val = options.get(opt_name, 1)
            return bool(val)
        opt = getattr(options, opt_name, None)
        if opt is None:
            return True
        return bool(getattr(opt, "value", opt))

    licenses = []
    if _bool("license_mini_mushroom"):
        licenses.append(MINI_MUSHROOM_LICENSE)
    if _bool("license_blue_shell"):
        licenses.append(BLUE_SHELL_LICENSE)
    if _bool("license_mega_mushroom"):
        licenses.append(MEGA_MUSHROOM_LICENSE)
    if _bool("license_mushroom"):
        licenses.append(MUSHROOM_LICENSE)
    if _bool("license_fire_flower"):
        licenses.append(FIRE_FLOWER_LICENSE)
    if _bool("license_touchscreen_pocket"):
        licenses.append(TOUCHSCREEN_RESERVE_LICENSE)

    return tuple(licenses)


def native_license_mode(options: Any) -> int:
    """Return the native ROM hook tier needed by the enabled individual Licenses."""
    active = set(active_license_items(options))
    if active & {MUSHROOM_LICENSE, FIRE_FLOWER_LICENSE, TOUCHSCREEN_RESERVE_LICENSE}:
        return LICENSE_MODE_ALL_POWERUPS
    if MEGA_MUSHROOM_LICENSE in active:
        return LICENSE_MODE_MAJOR_POWERUPS
    if active & {MINI_MUSHROOM_LICENSE, BLUE_SHELL_LICENSE}:
        return LICENSE_MODE_SHORTCUTS_ONLY
    return LICENSE_MODE_DISABLED


def license_items_for_mode(options: Any) -> tuple[str, ...]:
    """Return the exact License pool for a configured mode or options."""
    return active_license_items(options)


def license_is_enabled(options: Any, item_name: str) -> bool:
    """Return whether the selected mode or options logically enforces this License."""
    return item_name in active_license_items(options)


POWERUP_ITEM_LICENSES: dict[str, str] = {
    "Mushroom": MUSHROOM_LICENSE,
    "Fire Flower": FIRE_FLOWER_LICENSE,
    "Mini Mushroom": MINI_MUSHROOM_LICENSE,
    "Blue Shell": BLUE_SHELL_LICENSE,
    "Mega Mushroom": MEGA_MUSHROOM_LICENSE,
}


def required_license_for_powerup(options: Any, powerup_item: str) -> str | None:
    """Return the enabled type License required for a delivered Power-Up."""
    license_item = POWERUP_ITEM_LICENSES.get(powerup_item)
    if license_item and license_is_enabled(options, license_item):
        return license_item
    return None
