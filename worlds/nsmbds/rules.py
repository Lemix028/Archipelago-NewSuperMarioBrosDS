"""Access rules for the stage-level NSMBDS world graph."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rule_builder.rules import (
    And,
    CanReachLocation,
    CanReachRegion,
    Has,
    HasAny,
    Or,
    Rule,
    True_,
)
from worlds.generic.Rules import add_item_rule

from .data.logic_data import (
    INTRA_SECRET_DEPENDENT_WORLD_ROUTE_EVENTS,
    INTRA_WORLD_SECRET_EXITS,
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
from .data.star_coin_gates import (
    STAR_COIN_GATES,
    StarCoinGateDefinition,
    gate_required_lifetime_coins,
)
from .items import KEY_ITEM_NAMES
from .locations import BOSS_LOCATION_COMPLETION_SOURCES

if TYPE_CHECKING:
    from . import NSMBDSWorld


WORLD_KEY_NAMES = {
    1: "Grassland", 2: "Desert", 3: "Tropical", 4: "Jungle",
    5: "Glacier", 6: "Mountain", 7: "Sky", 8: "Volcano",
}


def _option_enabled(world: NSMBDSWorld, name: str) -> bool:
    option = getattr(world.options, name)
    return bool(getattr(option, "value", option))


def _atom_rule(atom: str) -> Rule:
    """Translate one logic-data atom into a structured Rule Builder rule."""
    if atom.startswith("REGION:"):
        return CanReachRegion(atom[7:])
    return CanReachLocation(atom)


def _alternative_rule(alternative: tuple[str, ...]) -> Rule:
    """Translate one AND branch of an OR-of-AND requirement."""
    if not alternative:
        # Archipelago 0.6.7 does not consistently simplify an empty And to
        # True. Keep free starting routes explicit for installed generators.
        return True_()
    return And(*(_atom_rule(atom) for atom in alternative))


def _requirement_rule(requirement: Requirement) -> Rule:
    """Translate an OR-of-AND requirement without changing its semantics."""
    return Or(*(_alternative_rule(alternative) for alternative in requirement))


def _active_stage_requirement(
    world: NSMBDSWorld, requirement: Requirement
) -> Requirement:
    """Prefer a stage's normal route when optional Secret Exit logic is disabled."""
    if _option_enabled(world, "secret_exit_shortcut_logic"):
        return requirement

    normal_routes = tuple(
        alternative
        for alternative in requirement
        if not any(atom in INTRA_WORLD_SECRET_EXITS for atom in alternative)
    )
    # Secret-only branches remain physically reachable with all-state, but are
    # marked non-progression during location creation. Only discard a Secret
    # Exit route when a normal alternative to the same destination exists.
    return normal_routes or requirement


def _stage_key_name(region_name: str) -> str | None:
    world_number = int(region_name.split(" ", 2)[1].split("-", 1)[0])
    world_name = WORLD_KEY_NAMES[world_number]
    suffix = region_name.split("-", 1)[1]
    if suffix in ("Tower 1", "Tower 2"):
        return f"{world_name} {suffix} Key"
    if suffix.startswith("Tower"):
        return f"{world_name} Tower Key"
    if suffix == "Bowser's Castle":
        return f"{world_name} Bowser's Castle Key"
    if suffix == "Castle":
        return f"{world_name} Castle Key"
    return None


def _star_coin_gate_rule(
    world: NSMBDSWorld, gate: StarCoinGateDefinition
) -> Rule:
    """Build the configured authorization rule for one Star-Coin gate."""
    mode = world.options.star_coin_gate_mode.value
    if mode == 0:
        tier = world.vanilla_gate_tiers[gate.name]
        return Has("Star Coin", gate_required_lifetime_coins(gate, tier))
    if mode == 1:
        return And(
            Has("Progressive Gate Pass", gate.progressive_index),
            Has(
                "Star Coin",
                gate_required_lifetime_coins(gate, gate.progressive_index),
            ),
        )
    if mode == 2:
        tier = world.individual_gate_tiers[gate.permit_item_name]
        return And(
            Has(gate.permit_item_name),
            Has("Star Coin", gate_required_lifetime_coins(gate, tier)),
        )
    raise ValueError(f"Unsupported Star Coin Gate mode: {mode}")


def _append_location_rule(
    location_rules: dict[str, Rule], location_name: str, rule: Rule
) -> None:
    """Accumulate a location's requirements before resolving it exactly once."""
    existing = location_rules.get(location_name)
    location_rules[location_name] = rule if existing is None else existing & rule


def set_rules(world: NSMBDSWorld) -> None:
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

        world.set_rule(
            multiworld.get_entrance(entrance_name, player),
            Or(
                Has(requirement.pass_item),
                *(_alternative_rule(alternative) for alternative in routes),
            ),
        )

    gate_by_target = {gate.target_stage_name: gate for gate in STAR_COIN_GATES}

    # Every stage and Toad House has its own entrance and therefore its own route rule.
    for region_name, requirement in {
        **STAGE_ENTRY_REQUIREMENTS,
        **TOAD_HOUSE_ENTRY_REQUIREMENTS,
    }.items():
        gate = gate_by_target.get(region_name)
        source_name = gate.region_name if gate else f"World {region_name.split(' ', 2)[1].split('-', 1)[0]}"
        entrance = multiworld.get_entrance(f"{source_name} -> {region_name}", player)
        active_requirement = _active_stage_requirement(world, requirement)
        rule = _requirement_rule(active_requirement)

        if world.options.tower_castle_keys and region_name in STAGE_ENTRY_REQUIREMENTS:
            key_name = _stage_key_name(region_name)
            if key_name:
                rule &= Has(key_name)

        world.set_rule(entrance, rule)

    # A gate's front-side route is on the gate->target entrance above. The
    # world->gate entrance solely models the configured gate authorization.
    star_coin_item_id = world.item_name_to_id["Star Coin"]
    key_item_names = frozenset(KEY_ITEM_NAMES)
    for gate in STAR_COIN_GATES:
        gate_entrance = multiworld.get_entrance(
            f"{gate.source_region} -> {gate.region_name}", player
        )
        world.set_rule(gate_entrance, _star_coin_gate_rule(world, gate))
        for location in multiworld.get_region(gate.target_stage_name, player).locations:
            add_item_rule(
                location,
                lambda item, item_id=star_coin_item_id, keys=key_item_names: not (
                    item.advancement
                    and (item.code == item_id or item.name in keys)
                ),
            )

    # Build every location's complete access rule before assigning it. Using
    # generic add_rule here would wrap structured rules in an opaque lambda.
    location_rules: dict[str, Rule] = {}

    for requirement in POWERUP_ABILITY_REQUIREMENTS:
        if not license_is_enabled(world.options, requirement.license_item):
            continue
        for location_name in requirement.locations:
            _append_location_rule(
                location_rules,
                location_name,
                Has(requirement.license_item),
            )

    for requirement in POWERUP_ALTERNATIVE_REQUIREMENTS:
        # A disabled License restores vanilla use of that form, satisfying the
        # alternative without requiring any of the remaining AP items.
        if any(
            not license_is_enabled(world.options, item)
            for item in requirement.license_items
        ):
            continue
        for location_name in requirement.locations:
            _append_location_rule(
                location_rules,
                location_name,
                HasAny(*requirement.license_items),
            )

    # Boss checks inherit the real completion route of their matching Goal.
    # The Mini-Mario castle exits in Worlds 2 and 5 are valid alternatives.
    for boss_name, source_names in BOSS_LOCATION_COMPLETION_SOURCES.items():
        _append_location_rule(
            location_rules,
            boss_name,
            Or(*(CanReachLocation(name) for name in source_names)),
        )

    for location_name, rule in location_rules.items():
        try:
            world.set_rule(multiworld.get_location(location_name, player), rule)
        except KeyError:
            # Optional check categories may remove a named location.
            pass


def set_completion_rules(world: NSMBDSWorld) -> None:
    """Define the configured goal as a structured, explainable rule."""
    goal = world.options.goal.value
    boss_rules = tuple(
        CanReachLocation(name) for name in world._boss_location_names
    )

    if goal == 0:  # Defeat Bowser
        rule = boss_rules[-1]
    elif goal == 1:  # Star Coin Hunt
        rule = Has("Star Coin", world.options.required_star_coins.value)
    elif goal == 2:  # World Tour
        rule = And(*boss_rules)
    elif goal == 3:  # Completionist
        rule = And(
            *boss_rules,
            Has("Star Coin", world.options.required_star_coins.value),
        )
    else:
        raise Exception(f"Unsupported goal value: {goal}")

    world.set_completion_rule(rule)
