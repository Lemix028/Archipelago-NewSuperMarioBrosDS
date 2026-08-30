"""Verified Star-Coin gate metadata shared by AP logic and the BizHawk client."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StarCoinGateMapping:
    """One live-captured vanilla Star-Coin sign and its persistent path byte."""

    world_number: int
    target_stage_name: str
    path_address: int
    selector: int
    star_coin_cost: int = 5
    closed_value: int = 0x00
    opened_value: int = 0xC0
    label_verified: bool = True

    @property
    def name(self) -> str:
        return f"{self.target_stage_name} Gate"


@dataclass(frozen=True)
class StarCoinGateDefinition:
    """One overwrite-safe overworld path controlled by a Star-Coin sign."""

    name: str
    source_region: str
    target_stage_name: str
    path_address: int
    selector: int
    progressive_index: int
    permit_item_name: str
    world_number: int
    world_gate_index: int
    star_coin_cost: int

    @property
    def region_name(self) -> str:
        return f"{self.source_region} Gate: {self.target_stage_name}"

    @property
    def permit_bit(self) -> int:
        return self.world_gate_index

    @property
    def permit_byte_index(self) -> int:
        return self.world_number - 1


def gate_required_lifetime_coins(
    gate: StarCoinGateDefinition,
    tier: int,
) -> int:
    """Return the cumulative lifetime Star-Coin budget for a logical gate tier."""
    return tier * gate.star_coin_cost


def _mapping(
    world_number: int,
    target_stage_name: str,
    path_address: int,
    selector: int,
    *,
    label_verified: bool = True,
) -> StarCoinGateMapping:
    return StarCoinGateMapping(
        world_number,
        target_stage_name,
        path_address,
        selector,
        label_verified=label_verified,
    )



STAR_COIN_GATE_CATALOG: tuple[StarCoinGateMapping, ...] = (
    _mapping(1, "World 1 Green Toad House 1",  0x00088D1F, 0x08),
    _mapping(1, "World 1 Orange Toad House",   0x00088D21, 0x0A),
    _mapping(1, "World 1-A",                    0x00088D23, 0x0C),
    _mapping(1, "World 1 Green Toad House 2",  0x00088D25, 0x0D),

    _mapping(2, "World 2 Red Toad House 1",     0x00088D3C, 0x0B),
    _mapping(2, "World 2 Orange Toad House",    0x00088D40, 0x0F),
    _mapping(2, "World 2 Green Toad House",     0x00088D43, 0x11),
    _mapping(2, "World 2 Red Toad House 3",     0x00088D44, 0x12),

    _mapping(3, "World 3-A",                    0x00088D5A, 0x0B),
    _mapping(3, "World 3 Orange Toad House",    0x00088D5F, 0x0E),
    _mapping(3, "World 3 Green Toad House",     0x00088D61, 0x10),

    _mapping(4, "World 4 Red Toad House 1",     0x00088D79, 0x0C),
    _mapping(4, "World 4-A",                    0x00088D7C, 0x0E),
    _mapping(4, "World 4 Orange Toad House",    0x00088D7D, 0x0F),
    _mapping(4, "World 4 Green Toad House 2",   0x00088D80, 0x11),
    _mapping(4, "World 4 Red Toad House 2",     0x00088D81, 0x12),

    _mapping(5, "World 5-A",                    0x00088D98, 0x0D),
    _mapping(5, "World 5 Red Toad House",       0x00088D9A, 0x0E),
    _mapping(5, "World 5-B",                    0x00088D9C, 0x06),
    _mapping(5, "World 5 Orange Toad House",    0x00088DA2, 0x15),
    _mapping(5, "World 5 Green Toad House",     0x00088DA3, 0x16),

    _mapping(6, "World 6-A",                    0x00088DB6, 0x0D),
    _mapping(6, "World 6 Green Toad House 1",   0x00088DB9, 0x0F),
    _mapping(6, "World 6 Orange Toad House",    0x00088DBB, 0x11),
    _mapping(6, "World 6 Red Toad House 2",     0x00088DBC, 0x12),
    _mapping(6, "World 6-B",                    0x00088DBD, 0x13),

    _mapping(7, "World 7 Orange Toad House",    0x00088DD2, 0x0B),
    _mapping(7, "World 7 Red Toad House",       0x00088DD3, 0x0C),
    _mapping(7, "World 7 Green Toad House 1",   0x00088DD4, 0x0D),

    _mapping(8, "World 8 Orange Toad House",    0x00088DF5, 0x10),
    _mapping(8, "World 8 Red Toad House",       0x00088DF6, 0x11),
    _mapping(8, "World 8 Green Toad House",     0x00088DF2, 0x0D),
)


def _permit_item_name(target_stage_name: str) -> str:
    return f"{target_stage_name} Gate Pass"


_world_gate_counts: dict[int, int] = {}
_active_gates: list[StarCoinGateDefinition] = []
for progressive_index, mapping in enumerate(STAR_COIN_GATE_CATALOG, start=1):
    world_gate_index = _world_gate_counts.get(mapping.world_number, 0)
    _world_gate_counts[mapping.world_number] = world_gate_index + 1
    _active_gates.append(
        StarCoinGateDefinition(
            mapping.name,
            f"World {mapping.world_number}",
            mapping.target_stage_name,
            mapping.path_address,
            mapping.selector,
            progressive_index,
            _permit_item_name(mapping.target_stage_name),
            mapping.world_number,
            world_gate_index,
            mapping.star_coin_cost,
        )
    )

STAR_COIN_GATES: tuple[StarCoinGateDefinition, ...] = tuple(_active_gates)
TOTAL_STAR_COIN_GATE_COST = sum(gate.star_coin_cost for gate in STAR_COIN_GATES)
