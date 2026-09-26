"""Run the real Red Coin resolver without importing the full AP test harness."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


WORLD = Path(__file__).resolve().parents[1]
REPO = WORLD.parents[1]


def package(name: str, path: Path) -> None:
    module = ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module


def verify() -> None:
    # Import the real mapping, catalog and client resolver. Stub only the AP
    # base class and item ID, which are irrelevant to location identity.
    package("worlds", REPO / "worlds")
    package("worlds.nsmbds", WORLD)
    package("worlds.nsmbds.data", WORLD / "data")
    package("worlds.nsmbds.client", WORLD / "client")
    package("worlds.nsmbds.client.features", WORLD / "client" / "features")
    base = ModuleType("BaseClasses")
    base.Location = type("Location", (), {})
    sys.modules["BaseClasses"] = base
    items = ModuleType("worlds.nsmbds.items")
    items.BASE_ID = 0x120000
    sys.modules["worlds.nsmbds.items"] = items

    randomization = importlib.import_module("worlds.nsmbds.data.level_randomization")
    locations = importlib.import_module("worlds.nsmbds.locations")
    resolver = importlib.import_module("worlds.nsmbds.client.features.red_coins")
    resolve = resolver.RedCoinTrackingMixin._resolve_seed_red_coin_location

    catalog_names = {
        name for name in locations.LOCATION_TABLE if "Red Coin Challenge" in name
    }
    resolved_names = set()
    for (world, level), expected in locations.COURSE_KEY_TO_RED_COIN_LOCATION_NAME.items():
        actual = resolve(None, world, level, 0, 0, 1)
        assert actual == expected, (world, level, expected, actual)
        resolved_names.add(actual)
    resolved_names.add(resolve(None, 2, 1, 45, 219, 2))
    assert resolved_names == catalog_names
    assert len(catalog_names) == 29

    assert resolve(None, 2, 1, 45, 41, 1) == "World 3-1 Red Coin Challenge 1"
    assert resolve(None, 2, 1, 45, 219, 2) == "World 3-1 Red Coin Challenge 2"

    mapping = dict(randomization.IDENTITY_LEVEL_MAPPING)
    mapping["World 1-1"], mapping["World 3-1"] = "World 3-1", "World 1-1"
    slot_data = {
        "level_randomization": randomization.LEVEL_RANDOMIZATION_GLOBAL,
        "level_randomization_version": randomization.LEVEL_RANDOMIZATION_VERSION,
        "level_mapping": mapping,
        "level_mapping_digest": randomization.level_mapping_digest(mapping),
    }
    assert resolve(slot_data, 2, 1, 0, 0, 1) == "World 1-1 Red Coin Challenge"
    assert resolve(slot_data, 0, 1, 45, 41, 1) == "World 3-1 Red Coin Challenge 1"
    assert resolve(slot_data, 0, 1, 45, 219, 2) == "World 3-1 Red Coin Challenge 2"
    print("Red Coin identity: all 29 catalog locations and shuffled slot/content courses OK")


if __name__ == "__main__":
    verify()
