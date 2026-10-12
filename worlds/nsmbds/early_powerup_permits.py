"""Bound selected permits to logical multiworld check spheres."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from BaseClasses import CollectionState, Item, Location, MultiWorld

from .data.powerup_licenses import active_license_items
from .options import PowerupPermitPlacement

if TYPE_CHECKING:
    from . import NSMBDSWorld


def prepare_early_powerup_permits(world: NSMBDSWorld) -> None:
    """Request early placement and guarantee availability by check sphere two."""
    world.early_powerup_permit_deadlines = {}
    world.options.selected_powerup_permits.verify_keys()
    mode = world.options.powerup_permit_placement.value
    if mode == PowerupPermitPlacement.option_normal or world._re_gen_slot_data:
        return

    active = set(active_license_items(world.options))
    selected = world.options.selected_powerup_permits.value
    for name in sorted(selected - active):
        logging.warning(
            "NSMBDS Early Powerup Permits: ignoring %s for %s because its license is disabled.",
            name, world.player_name,
        )
    starting = {
        name for option in (world.options.start_inventory, getattr(world.options, "start_inventory_from_pool", None))
        if option is not None
        for name, count in option.value.items() if count > 0
    }
    permits = sorted((selected & active) - starting)
    for name in permits:
        world.early_powerup_permit_deadlines[name] = 2
        # Core handles the initial sphere before normal fill. Later deadlines
        # are enforced against the completed seed, after progression balancing.
        early = world.multiworld.early_items[world.player]
        early[name] = max(early.get(name, 0), 1)


def permit_check_spheres(multiworld: MultiWorld) -> dict[Location, int]:
    """Use sendable spheres: local events do not consume a network check sphere."""
    result = {}
    for number, sphere in enumerate(multiworld.get_sendable_spheres(), 1):
        # Core yields the unreachable tail after an empty sphere. Never count it.
        if not sphere or number > 2:
            break
        result.update((location, number) for location in sphere)
    return result


def _receives(multiworld: MultiWorld, player: int, item: Item, name: str) -> bool:
    return item.name == name and (
        item.player == player
        or player in multiworld.groups.get(item.player, {}).get("players", ())
    )


def _can_place(location: Location, item: Item, state: CollectionState) -> bool:
    """Honor locality even in test/custom generators that omitted Core locality rules."""
    multiworld = state.multiworld
    if item.player in multiworld.groups:
        group = multiworld.groups[item.player]
        local = item.name in group.get("local_items", ())
        non_local = item.name in group.get("non_local_items", ())
        native = location.player in group["players"]
    else:
        options = multiworld.worlds[item.player].options
        local = item.name in options.local_items.value
        non_local = item.name in options.non_local_items.value and not local
        native = location.player == item.player
    return not (local and not native or non_local and native) and location.can_fill(state, item, False)


def _error(world: NSMBDSWorld, name: str, deadline: int, reason: str) -> ValueError:
    return ValueError(
        f"NSMBDS Early Powerup Permits ({world.player_name}): {name} must be available "
        f"by check sphere {deadline}, but {reason}. Check permit selection, local/non-local "
        "items, excluded/priority locations, item links, and fixed Plando placements."
    )


def _available(
    state: CollectionState, spheres: dict[Location, int], player: int, name: str, deadline: int,
) -> bool:
    return state.has(name, player) or any(
        number <= deadline and _receives(state.multiworld, player, location.item, name)
        for location, number in spheres.items()
    )


def enforce_early_powerup_permits(multiworld: MultiWorld, worlds: list[NSMBDSWorld]) -> None:
    """Pull late permits into eligible early checks without breaking accessibility."""
    requests = sorted(
        (deadline, world.player, index, name, world)
        for world in worlds
        for index, (name, deadline) in enumerate(world.early_powerup_permit_deadlines.items())
    )
    if not requests:
        return

    # Fill itself imports worlds while loading. Defer this dependency until
    # generation so this world also loads when Fill was imported first.
    from Fill import swap_location_item

    state = CollectionState(multiworld)
    state.sweep_for_advancements(
        locations=[location for location in multiworld.get_filled_locations() if location.address is None]
    )
    spheres = permit_check_spheres(multiworld)
    locations = sorted(
        location for location in multiworld.get_filled_locations()
        if type(location.address) is int and type(location.item.code) is int
    )
    for deadline, player, _, name, world in requests:
        if state.has(name, player):
            continue
        sources = [location for location in locations if _receives(multiworld, player, location.item, name)]
        if not sources:
            raise _error(world, name, deadline, "no copy exists in the placed item pool or starting inventory")
        on_time = [location for location in sources if spheres.get(location, 3) <= deadline]
        if on_time:
            # Preserve these placements if another generation hook runs later.
            min(on_time, key=lambda location: (spheres[location], location)).locked = True
            continue
        movable = [location for location in sources if not location.locked]
        if not movable:
            raise _error(world, name, deadline, "its fixed placement is outside that deadline")

        candidates = [
            location for location in locations
            if not location.locked and spheres.get(location, 3) <= deadline
        ]
        world.random.shuffle(candidates)
        # Prefer replacing filler in the latest allowed sphere. Important items
        # are a fallback only when the whole seed remains accessible afterward.
        candidates.sort(key=lambda location: (
            bool(location.item.advancement or location.item.useful), -spheres[location],
        ))
        satisfied = [
            (limit, owner, permit) for limit, owner, _, permit, _ in requests
            if _available(state, spheres, owner, permit, limit)
        ]
        placed = False
        for source in movable:
            for target in candidates:
                if not (_can_place(target, source.item, state) and _can_place(source, target.item, state)):
                    continue
                swap_location_item(source, target)
                # Some worlds collect nominal filler for logic. Validate every
                # swap, including the already satisfied permit deadlines.
                updated_spheres = permit_check_spheres(multiworld)
                if (
                    updated_spheres.get(target, 3) <= deadline
                    and all(_available(state, updated_spheres, owner, permit, limit)
                            for limit, owner, permit in satisfied)
                    and multiworld.fulfills_accessibility()
                ):
                    target.locked = True
                    spheres = updated_spheres
                    placed = True
                    break
                swap_location_item(source, target)
            if placed:
                break
        if not placed:
            raise _error(world, name, deadline, "there is no legal early check available for a safe placement")

    # Moving one permit can affect another world's sphere traversal. Validate
    # every requested deadline against the resulting seed, including Plando.
    validate_early_powerup_permits(multiworld, worlds)


def validate_early_powerup_permits(multiworld: MultiWorld, worlds: list[NSMBDSWorld]) -> None:
    """Reject any seed that silently lost a deadline in another generation hook."""
    if not any(world.early_powerup_permit_deadlines for world in worlds):
        return
    state = CollectionState(multiworld)
    state.sweep_for_advancements(
        locations=[location for location in multiworld.get_filled_locations() if location.address is None]
    )
    spheres = permit_check_spheres(multiworld)
    for world in worlds:
        for name, deadline in world.early_powerup_permit_deadlines.items():
            if not _available(state, spheres, world.player, name, deadline):
                raise _error(world, name, deadline, "the completed seed does not satisfy the sphere deadline")
