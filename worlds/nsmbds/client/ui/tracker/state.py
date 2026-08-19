"""Spoiler-free tracker state derived from the local Archipelago session."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from ....items import INVENTORY_RAM_VALUES, ITEM_TABLE, KEY_ITEM_NAMES, item_id_to_name
from ....locations import (
    BLOCKSANITY_LOCATION_IDS,
    LOCATION_TABLE,
    ONE_UP_BLOCK_LOCATION_IDS,
    RED_COIN_LOCATION_IDS,
)
from ....data.powerup_licenses import license_items_for_mode
from ....data.star_coin_gates import STAR_COIN_GATES


GOAL_NAMES = {
    0: "Defeat Bowser",
    1: "Star Coin Hunt",
    2: "World Tour",
    3: "Completionist",
}
WORLD_ACCESS_ITEMS = (
    "Desert Pass",
    "Isle Pass",
    "Jungle Pass",
    "Glacier Pass",
    "Mountain Pass",
    "Cloud Pass",
    "Volcano Pass",
)
CASTLE_GOAL_NAMES = tuple(
    [f"World {world}-Castle Goal" for world in range(1, 8)]
    + ["World 8-Bowser's Castle Goal"]
)


@dataclass(frozen=True)
class ProgressCount:
    checked: int
    total: int


@dataclass(frozen=True)
class InventoryEntry:
    name: str
    received: int
    required: int = 1


@dataclass(frozen=True)
class TrackerSnapshot:
    seed_loaded: bool
    server_status: str
    bizhawk_status: str
    rom_status: str
    total_progress: ProgressCount
    world_progress: tuple[tuple[str, ProgressCount], ...]
    category_progress: tuple[tuple[str, ProgressCount], ...]
    inventory: tuple[tuple[str, tuple[InventoryEntry, ...]], ...]
    goal_name: str
    goal_progress: str
    goal_count: ProgressCount
    death_link_enabled: bool
    trap_shields: int
    life_insurance: int
    star_coin_lifetime: int
    star_coin_spent: int
    star_coin_available: int
    pending_powerups: tuple[InventoryEntry, ...]


def _is_server_connected(ctx: Any) -> bool:
    server = getattr(ctx, "server", None)
    socket = getattr(server, "socket", None)
    return server is not None and socket is not None and not getattr(socket, "closed", True)


def _bizhawk_status(ctx: Any) -> str:
    connection = getattr(getattr(ctx, "bizhawk_ctx", None), "connection_status", None)
    name = getattr(connection, "name", None)
    if name:
        return name.replace("_", " ").title()
    return "Not Connected" if connection is None else str(connection)


def _location_category(name: str, location_id: int) -> str:
    if location_id in RED_COIN_LOCATION_IDS:
        return "Red Coin Challenges"
    if location_id in ONE_UP_BLOCK_LOCATION_IDS:
        return "1-Up Blocks"
    if location_id in BLOCKSANITY_LOCATION_IDS:
        return "Blocksanity"
    if " Star Coin " in name:
        return "Star Coins"
    if name.endswith(" Secret Exit"):
        return "Secret Exits"
    if "Toad House" in name:
        return "Toad Houses"
    if name.endswith(" Goal"):
        return "Level Goals"
    return "Map Rewards"


def _progress_for_ids(ids: set[int], checked: set[int]) -> ProgressCount:
    return ProgressCount(len(ids & checked), len(ids))


def _inventory_entries(names: tuple[str, ...], received: Counter[int]) -> tuple[InventoryEntry, ...]:
    return tuple(
        InventoryEntry(name, received[ITEM_TABLE[name][0]])
        for name in names
    )


def build_tracker_snapshot(ctx: Any) -> TrackerSnapshot:
    """Build tracker data without requesting or exposing item-placement data."""
    known_location_ids = frozenset(LOCATION_TABLE.values())
    checked = set(getattr(ctx, "checked_locations", ())) & known_location_ids
    missing = set(getattr(ctx, "missing_locations", ())) & known_location_ids
    active = checked | missing

    id_to_name = {location_id: name for name, location_id in LOCATION_TABLE.items()}
    world_ids: dict[str, set[int]] = {f"World {world}": set() for world in range(1, 9)}
    category_ids: dict[str, set[int]] = {}
    for location_id in active:
        name = id_to_name[location_id]
        world_name = name.split("-", 1)[0].split(" ", 2)[:2]
        world_label = " ".join(world_name)
        if world_label in world_ids:
            world_ids[world_label].add(location_id)
        category_ids.setdefault(_location_category(name, location_id), set()).add(location_id)

    slot_data = getattr(ctx, "slot_data", None) or {}
    received = Counter(item.item for item in getattr(ctx, "items_received", ()))
    received_star_coins = received[ITEM_TABLE["Star Coin"][0]]
    inventory: list[tuple[str, tuple[InventoryEntry, ...]]] = [
        ("World Access", _inventory_entries(WORLD_ACCESS_ITEMS, received)),
    ]

    if slot_data.get("tower_castle_keys", True):
        inventory.append(("Tower & Castle Keys", _inventory_entries(KEY_ITEM_NAMES, received)))

    license_names = license_items_for_mode(slot_data)
    if license_names:
        inventory.append(("Power-Up Licenses", _inventory_entries(license_names, received)))

    gate_mode = int(slot_data.get("star_coin_gate_mode", 0))
    if gate_mode == 1:
        permit_name = "Progressive Gate Pass"
        inventory.append((
            "Star Coin Gate Permits",
            (InventoryEntry(permit_name, received[ITEM_TABLE[permit_name][0]], len(STAR_COIN_GATES)),),
        ))
    elif gate_mode == 2:
        permit_names = tuple(gate.permit_item_name for gate in STAR_COIN_GATES)
        inventory.append(("Star Coin Gate Permits", _inventory_entries(permit_names, received)))

    goal = int(slot_data.get("goal", 0))
    checked_names = {id_to_name[location_id] for location_id in checked}
    checked_star_coins = sum(" Star Coin " in name for name in checked_names)
    checked_castles = sum(name in checked_names for name in CASTLE_GOAL_NAMES)
    bowser_defeated = "World 8-Bowser's Castle Goal" in checked_names
    required_star_coins = int(slot_data.get("required_star_coins", 80))
    if goal == 0:
        goal_progress = "Bowser defeated" if bowser_defeated else "Bowser not defeated"
        goal_count = ProgressCount(int(bowser_defeated), 1)
    elif goal == 1:
        goal_progress = f"{received_star_coins} / {required_star_coins} Star Coins received"
        goal_count = ProgressCount(min(received_star_coins, required_star_coins), required_star_coins)
    elif goal == 2:
        goal_progress = f"{checked_castles} / {len(CASTLE_GOAL_NAMES)} Castle goals"
        goal_count = ProgressCount(checked_castles, len(CASTLE_GOAL_NAMES))
    else:
        bowser_text = "done" if bowser_defeated else "open"
        goal_progress = f"Bowser: {bowser_text} | Star Coins: {received_star_coins} / {required_star_coins}"
        goal_count = ProgressCount(
            int(bowser_defeated) + min(received_star_coins, required_star_coins),
            required_star_coins + 1,
        )

    rom_handler = getattr(ctx, "client_handler", None)
    pending_powerup_counts = Counter(
        item_id_to_name[item_id]
        for item_id in getattr(rom_handler, "_deferred_item_ids", ())
        if item_id_to_name.get(item_id) in INVENTORY_RAM_VALUES
    )
    pending_powerups = tuple(
        InventoryEntry(name, pending_powerup_counts[name])
        for name in INVENTORY_RAM_VALUES
        if pending_powerup_counts[name]
    )
    rom_status = "NSMBDS Active" if getattr(rom_handler, "server_game", None) == "New Super Mario Bros. DS" else "Waiting for NSMBDS ROM"

    category_order = (
        "Level Goals",
        "Star Coins",
        "Red Coin Challenges",
        "1-Up Blocks",
        "Secret Exits",
        "Toad Houses",
        "Map Rewards",
    )
    server_connected = _is_server_connected(ctx)
    return TrackerSnapshot(
        seed_loaded=server_connected and getattr(ctx, "slot_data", None) is not None,
        server_status="Connected" if server_connected else "Not Connected",
        bizhawk_status=_bizhawk_status(ctx),
        rom_status=rom_status,
        total_progress=_progress_for_ids(active, checked),
        world_progress=tuple(
            (world, _progress_for_ids(ids, checked))
            for world, ids in world_ids.items()
            if ids
        ),
        category_progress=tuple(
            (category, _progress_for_ids(category_ids[category], checked))
            for category in category_order
            if category in category_ids
        ),
        inventory=tuple(inventory),
        goal_name=GOAL_NAMES.get(goal, f"Unknown ({goal})"),
        goal_progress=goal_progress,
        goal_count=goal_count,
        death_link_enabled=bool(slot_data.get("death_link", False)),
        trap_shields=int(getattr(rom_handler, "_pending_trap_shields", 0)),
        life_insurance=int(getattr(rom_handler, "_pending_life_insurance", 0)),
        star_coin_lifetime=received_star_coins,
        star_coin_spent=int(getattr(rom_handler, "_star_coin_spent", 0)),
        star_coin_available=int(getattr(rom_handler, "_star_coin_available", received_star_coins)),
        pending_powerups=pending_powerups,
    )


def render_tracker_markup(snapshot: TrackerSnapshot) -> str:
    """Render a compact Kivy-markup view of a spoiler-free snapshot."""
    lines = [
        "[size=24sp][b]NSMBDS Overview[/b][/size]",
        "[color=9E9E9E]No item placements are shown. Use the Hints tab for hinted information.[/color]",
        "",
        "[size=19sp][b]Connections[/b][/size]",
        f"Server: {snapshot.server_status}   |   BizHawk: {snapshot.bizhawk_status}   |   ROM: {snapshot.rom_status}",
        "",
        "[size=19sp][b]Goal[/b][/size]",
        f"{snapshot.goal_name}: {snapshot.goal_progress}",
        (
            f"Star Coins: {snapshot.star_coin_available} available | "
            f"{snapshot.star_coin_lifetime} received total | {snapshot.star_coin_spent} spent"
        ),
        "",
        "[size=19sp][b]Check Progress[/b][/size]",
        f"Total: {snapshot.total_progress.checked} / {snapshot.total_progress.total}",
    ]
    lines.extend(
        f"{world}: {progress.checked} / {progress.total}"
        for world, progress in snapshot.world_progress
    )
    lines.extend(("", "[size=19sp][b]Categories[/b][/size]"))
    lines.extend(
        f"{category}: {progress.checked} / {progress.total}"
        for category, progress in snapshot.category_progress
    )
    lines.extend(("", "[size=19sp][b]Received Progression[/b][/size]"))
    for group, entries in snapshot.inventory:
        lines.append(f"[b]{group}[/b]")
        for entry in entries:
            if entry.required > 1:
                state = f"{min(entry.received, entry.required)} / {entry.required}"
            else:
                state = "Received" if entry.received else "Missing"
            color = "72D572" if entry.received else "9E9E9E"
            lines.append(f"  [color={color}]{entry.name}: {state}[/color]")
    lines.extend((
        "",
        "[size=19sp][b]Waiting Power-Ups[/b][/size]",
        f"Queued: {sum(entry.received for entry in snapshot.pending_powerups)}",
    ))
    if snapshot.pending_powerups:
        lines.extend(
            f"  {entry.name}: {entry.received}"
            for entry in snapshot.pending_powerups
        )
    else:
        lines.append("  None")
    lines.extend((
        "",
        "[size=19sp][b]Session Info[/b][/size]",
        f"Death Link: {'On' if snapshot.death_link_enabled else 'Off'}",
        f"Trap Shields: {snapshot.trap_shields}",
        f"Life Insurance: {snapshot.life_insurance}",
    ))
    return "\n".join(lines)
