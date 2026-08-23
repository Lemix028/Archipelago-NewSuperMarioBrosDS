"""Access rules for the stage-level NSMBDS world graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from worlds.generic.Rules import add_item_rule, add_rule, set_rule

from .data.logic_data import (
    INTRA_SECRET_DEPENDENT_WORLD_ROUTE_EVENTS,
    STAGE_ENTRY_REQUIREMENTS,
    TOAD_HOUSE_ENTRY_REQUIREMENTS,
    Requirement,
)
from .data.overworld_routes import WORLD_CONNECTION_REQUIREMENTS
from .data.powerup_licenses import (
    POWERUP_ABILITY_REQUIREMENTS,
    POWERUP_ALTERNATIVE_REQUIREMENTS,
    license_is_enabled,
)
from .data.star_coin_gates import STAR_COIN_GATES
from .locations import BOSS_LOCATION_COMPLETION_SOURCES

if TYPE_CHECKING:
    from BaseClasses import CollectionState
    from . import NSMBDSWorld


WORLD_KEY_NAMES = {
    1: "Grassland", 2: "Desert", 3: "Tropical", 4: "Jungle",
    5: "Glacier", 6: "Mountain", 7: "Sky", 8: "Volcano",
}


def _option_enabled(world: "NSMBDSWorld", name: str) -> bool:
    option = getattr(world.options, name)
    return bool(getattr(option, "value", option))


def _requirement_rule(
    world: "NSMBDSWorld", requirement: Requirement
) -> Callable[["CollectionState"], bool]:
    player = world.player
    # Disabled route options affect progression placement, not what the player
    # can physically visit. This keeps optional branches usable and preserves
    # full-accessibility seeds while ensuring the fill never depends on them.
    alternatives = requirement

    return lambda state: any(
        all(
            state.can_reach(atom[7:], "Region", player)
            if atom.startswith("REGION:")
            else state.can_reach(atom, "Location", player)
            for atom in alternative
        )
        for alternative in alternatives
    )


def _register_indirect_conditions(world: "NSMBDSWorld", entrance, requirement: Requirement) -> None:
    """Tell Core which cached regions can make this entrance newly reachable."""
    for alternative in requirement:
        for atom in alternative:
            if atom.startswith("REGION:"):
                dependency_region = world.multiworld.get_region(atom[7:], world.player)
            else:
                dependency_region = world.multiworld.get_location(atom, world.player).parent_region
            world.multiworld.register_indirect_condition(dependency_region, entrance)


def _gate_authorized(world: "NSMBDSWorld", gate, state: "CollectionState") -> bool:
    player = world.player
    if not state.has("Star Coin", player, gate.star_coin_cost):
        return False
    mode = world.options.star_coin_gate_mode.value
    if mode == 1:
        return state.has("Progressive Gate Pass", player, gate.progressive_index)
    if mode == 2:
        return state.has(gate.permit_item_name, player)
    return True


def _stage_key_name(region_name: str) -> str | None:
    world_number = int(region_name.split(" ", 2)[1].split("-", 1)[0])
    world_name = WORLD_KEY_NAMES[world_number]
    suffix = region_name.split("-", 1)[1]
    if suffix.startswith("Tower"):
        return f"{world_name} Tower Key"
    if suffix == "Castle" or suffix == "Bowser's Castle":
        return f"{world_name} Castle Key"
    return None


def set_rules(world: "NSMBDSWorld") -> None:
    multiworld = world.multiworld
    player = world.player

    # World access: Passes are always valid; optional vanilla route classes
    # are only included when their generator setting is enabled.
    for entrance_name, requirement in WORLD_CONNECTION_REQUIREMENTS.items():
        routes = requirement.normal_routes
        if _option_enabled(world, "secret_exit_world_unlock_logic"):
            routes += requirement.alternate_castle_routes
        if _option_enabled(world, "cannon_route_logic"):
            routes += requirement.cannon_routes
        if not _option_enabled(world, "secret_exit_shortcut_logic"):
            routes = tuple(
                alternative for alternative in routes
                if not any(
                    event in INTRA_SECRET_DEPENDENT_WORLD_ROUTE_EVENTS
                    for event in alternative
                )
            )
        set_rule(
            multiworld.get_entrance(entrance_name, player),
            lambda state, pass_item=requirement.pass_item, alternatives=routes: (
                state.has(pass_item, player)
                or any(
                    all(state.can_reach(name, "Location", player) for name in alternative)
                    for alternative in alternatives
                )
            ),
        )
        entrance = multiworld.get_entrance(entrance_name, player)
        for alternative in routes:
            for location_name in alternative:
                dependency = multiworld.get_location(location_name, player).parent_region
                multiworld.register_indirect_condition(dependency, entrance)

    gate_by_target = {gate.target_stage_name: gate for gate in STAR_COIN_GATES}

    # Every stage and Toad House has its own entrance and therefore its own route rule.
    for region_name, requirement in {
        **STAGE_ENTRY_REQUIREMENTS,
        **TOAD_HOUSE_ENTRY_REQUIREMENTS,
    }.items():
        gate = gate_by_target.get(region_name)
        source_name = gate.region_name if gate else f"World {region_name.split(' ', 2)[1].split('-', 1)[0]}"
        entrance = multiworld.get_entrance(f"{source_name} -> {region_name}", player)
        set_rule(entrance, _requirement_rule(world, requirement))
        _register_indirect_conditions(world, entrance, requirement)

        if world.options.tower_castle_keys and region_name in STAGE_ENTRY_REQUIREMENTS:
            key_name = _stage_key_name(region_name)
            if key_name:
                add_rule(entrance, lambda state, item=key_name: state.has(item, player))

    # A gates front-side route is on the gate->target entrance above. The
    # world->gate entrance solely models the vanilla five-coin authorization.
    star_coin_item_id = world.item_name_to_id["Star Coin"]
    for gate in STAR_COIN_GATES:
        gate_entrance = multiworld.get_entrance(
            f"{gate.source_region} -> {gate.region_name}", player
        )
        set_rule(
            gate_entrance,
            lambda state, current_gate=gate: _gate_authorized(world, current_gate, state),
        )
        for location in multiworld.get_region(gate.target_stage_name, player).locations:
            add_item_rule(
                location,
                lambda item, item_id=star_coin_item_id: not (
                    item.code == item_id and item.advancement
                ),
            )

    # Apply all power-up requirements. Optional location categories
    # may remove a named check, hence the guarded lookup.
    for requirement in POWERUP_ABILITY_REQUIREMENTS:
        if not license_is_enabled(world.options, requirement.license_item):
            continue
        for location_name in requirement.locations:
            try:
                add_rule(
                    multiworld.get_location(location_name, player),
                    lambda state, item=requirement.license_item: state.has(item, player),
                )
            except KeyError:
                pass

    for requirement in POWERUP_ALTERNATIVE_REQUIREMENTS:
        for location_name in requirement.locations:
            try:
                add_rule(
                    multiworld.get_location(location_name, player),
                    lambda state, items=requirement.license_items: any(
                        not license_is_enabled(world.options, item)
                        or state.has(item, player)
                        for item in items
                    ),
                )
            except KeyError:
                pass

    # Boss checks inherit the real completion route of their matching Goal.
    # The Mini-Mario castle exits in Worlds 2 and 5 are valid alternatives.
    for boss_name, source_names in BOSS_LOCATION_COMPLETION_SOURCES.items():
        boss_location = multiworld.get_location(boss_name, player)
        set_rule(
            boss_location,
            lambda state, names=source_names: any(
                multiworld.get_location(name, player).can_reach(state)
                for name in names
            ),
        )
