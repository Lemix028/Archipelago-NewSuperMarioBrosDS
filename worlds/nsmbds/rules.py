"""
New Super Mario Bros. DS - Access Rules
Defines which items are required to access which regions and locations.
"""

from typing import TYPE_CHECKING

from worlds.generic.Rules import add_item_rule, add_rule, set_rule

from .data.powerup_licenses import (
    POWERUP_ABILITY_REQUIREMENTS,
    POWERUP_ALTERNATIVE_REQUIREMENTS,
    license_is_enabled,
)
from .data.star_coin_gates import STAR_COIN_GATES
from .data.overworld_routes import WORLD_CONNECTION_REQUIREMENTS

if TYPE_CHECKING:
    from . import NSMBDSWorld


# Mapping of world number -> stage name prefixes that are located behind the Tower path gate
TOWER_DEPENDENT_STAGES: dict[int, tuple[str, ...]] = {
    1: ("World 1-Tower", "World 1-A", "World 1-4", "World 1-5", "World 1-Castle", "World 1 Red Toad House 2", "World 1 Orange Toad House 1", "World 1 Green Toad House 2"),
    2: ("World 2-Tower", "World 2-5", "World 2-6", "World 2-Castle", "World 2 Red Toad House 2", "World 2 Red Toad House 3", "World 2 Green Toad House"),
    3: ("World 3-Tower", "World 3-3", "World 3-Ghost House", "World 3-B", "World 3-C", "World 3-Castle", "World 3 Green Toad House", "World 3 Orange Toad House"),
    4: ("World 4-Tower", "World 4-A", "World 4-4", "World 4-Ghost House", "World 4-5", "World 4-6", "World 4-Castle", "World 4 Orange Toad House", "World 4 Green Toad House 2", "World 4 Red Toad House 2"),
    5: ("World 5-Tower", "World 5-3", "World 5-Ghost House", "World 5-B", "World 5-C", "World 5-4", "World 5-Castle", "World 5 Orange Toad House", "World 5 Green Toad House", "World 5 Red Toad House"),
    6: ("World 6-Tower 1", "World 6-3", "World 6-4", "World 6-Tower 2", "World 6-5", "World 6-B", "World 6-6", "World 6-Castle", "World 6 Orange Toad House", "World 6 Red Toad House 2", "World 6 Green Toad House 2"),
    7: ("World 7-Tower", "World 7-4", "World 7-5", "World 7-A", "World 7-6", "World 7-7", "World 7-Castle", "World 7 Green Toad House 3"),
    8: ("World 8-Tower 1", "World 8-3", "World 8-4", "World 8-Castle", "World 8-5", "World 8-6", "World 8-7", "World 8-Tower 2", "World 8-8", "World 8-Bowser's Castle", "World 8 Red Toad House", "World 8 Green Toad House"),
}

# Mapping of world number -> stage name prefixes that are located behind the Castle path gate
CASTLE_DEPENDENT_STAGES: dict[int, tuple[str, ...]] = {
    1: ("World 1-Castle",),
    2: ("World 2-Castle",),
    3: ("World 3-Castle",),
    4: ("World 4-Castle",),
    5: ("World 5-Castle",),
    6: ("World 6-Castle",),
    7: ("World 7-Castle",),
    8: ("World 8-Castle", "World 8-5", "World 8-6", "World 8-7", "World 8-Tower 2", "World 8-8", "World 8-Bowser's Castle"),
}


def set_rules(world: "NSMBDSWorld") -> None:
    """
    Set all access rules for regions and locations.

    Rules follow in-game logic:
    - Each world requires the corresponding Access key item.
    - Alternate boss and cannon routes require their exact power-up ability.
    - Certain Secret Exits and Star Coins require power-up licenses.
    """
    multiworld = world.multiworld
    player = world.player

    # ------------------------------------------------------------------
    # World entrance rules — gates on the connection between regions
    # ------------------------------------------------------------------

    for entrance_name, requirement in WORLD_CONNECTION_REQUIREMENTS.items():
        set_rule(
            multiworld.get_entrance(entrance_name, player),
            lambda state, route=requirement: (
                state.has(route.pass_item, player)
                or any(
                    all(
                        state.can_reach(location_name, "Location", player)
                        for location_name in alternative
                    )
                    for alternative in route.vanilla_routes
                )
            ),
        )

    # ------------------------------------------------------------------
    # Location-specific rules (require power-up licenses)
    # ------------------------------------------------------------------


    gate_mode = world.options.star_coin_gate_mode.value
    star_coin_item_id = world.item_name_to_id["Star Coin"]
    for gate in STAR_COIN_GATES:
        entrance = multiworld.get_entrance(
            f"{gate.source_region} -> {gate.region_name}", player
        )
        for location in multiworld.get_region(gate.region_name, player).locations:
            add_item_rule(
                location,
                lambda item, item_id=star_coin_item_id: not (
                    item.code == item_id and item.advancement
                ),
            )
        if gate_mode == 1:
            set_rule(
                entrance,
                lambda state, count=gate.progressive_index,
                cost=gate.star_coin_cost: (
                    state.has("Progressive Gate Pass", player, count)
                    and state.has("Star Coin", player, cost)
                ),
            )
        elif gate_mode == 2:
            set_rule(
                entrance,
                lambda state, item_name=gate.permit_item_name,
                cost=gate.star_coin_cost: (
                    state.has(item_name, player)
                    and state.has("Star Coin", player, cost)
                ),
            )
        else:
            set_rule(
                entrance,
                lambda state, cost=gate.star_coin_cost: state.has(
                    "Star Coin", player, cost
                ),
            )

    # World 3 Red Toad House is located on the island accessed through World 3-A.
    try:
        add_rule(
            multiworld.get_location("World 3 Red Toad House Goal", player),
            lambda state: state.can_reach("World 3 Gate: World 3-A", "Region", player),
        )
    except KeyError:
        pass

    # Apply only the License requirements enabled by selected options.
    for requirement in POWERUP_ABILITY_REQUIREMENTS:
        if not license_is_enabled(world.options, requirement.license_item):
            continue
        for location_name in requirement.locations:
            try:
                add_rule(
                    multiworld.get_location(location_name, player),
                    lambda state, item_name=requirement.license_item: state.has(item_name, player),
                )
            except KeyError:
                # Optional check categories may remove these locations.
                pass

    # Some checks have multiple valid forms. A disabled License means that
    # form remains available through normal gameplay; otherwise its Permit
    # must have been received. The alternatives are combined with OR.
    for requirement in POWERUP_ALTERNATIVE_REQUIREMENTS:
        for location_name in requirement.locations:
            add_rule(
                multiworld.get_location(location_name, player),
                lambda state, item_names=requirement.license_items: any(
                    not license_is_enabled(world.options, item_name)
                    or state.has(item_name, player)
                    for item_name in item_names
                ),
            )

    # Tower & Castle Key location requirements when option is enabled
    if world.options.tower_castle_keys:
        world_names = {
            1: "Grassland",
            2: "Desert",
            3: "Tropical",
            4: "Jungle",
            5: "Glacier",
            6: "Mountain",
            7: "Sky",
            8: "Volcano",
        }
        for location in multiworld.get_locations(player):
            for w, w_name in world_names.items():
                tower_key = f"{w_name} Tower Key"
                castle_key = f"{w_name} Castle Key"

                # Check if location is in a post-Tower stage for world w
                for prefix in TOWER_DEPENDENT_STAGES[w]:
                    if location.name.startswith(prefix):
                        add_rule(location, lambda state, k=tower_key: state.has(k, player))
                        break

                # Check if location is in a post-Castle stage for world w
                for prefix in CASTLE_DEPENDENT_STAGES[w]:
                    if location.name.startswith(prefix):
                        add_rule(location, lambda state, k=castle_key: state.has(k, player))
                        break

    # World Tour deliberately keeps Bowser's Castle as its final castle. Star
    # Coin goals use the normal World 8 route so every final-castle check can
    # contribute toward the configured total in either order.
    goal = world.options.goal.value
    bowser_prefix = "World 8-Bowser's Castle"
    bowser_locations = [
        location
        for location in multiworld.get_locations(player)
        if location.name.startswith(bowser_prefix)
    ]
    if goal == 2:
        prior_castles = tuple(
            name
            for name in world._castle_goal_location_names
            if name != "World 8-Bowser's Castle Goal"
        )
        for location in bowser_locations:
            add_rule(
                location,
                lambda state, names=prior_castles: (
                    world._count_reachable_locations(state, names) == len(names)
                ),
            )
