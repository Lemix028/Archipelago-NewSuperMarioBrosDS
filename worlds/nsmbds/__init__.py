"""
New Super Mario Bros. DS - World Class Definition
Main entry point for Archipelago multiworld generation.
"""

import os
from typing import Any, ClassVar

from BaseClasses import Item, ItemClassification, Location, LocationProgressType, Region
from settings import get_settings
from worlds.AutoWorld import World
from worlds.LauncherComponents import Component, SuffixIdentifier, Type, components, launch_subprocess

from .items import (
    calculate_nonprogression_pool_counts,
    FILLER_ITEM_WEIGHTS,
    ITEM_TABLE,
    KEY_ITEM_NAMES,
    PROGRESSION_ITEM_NAMES,
    NSMBDSItem,
)
from .locations import (
    LOCATION_TABLE,
    LOCATION_RAM_MAP,
    ACTIVE_LOCATION_ID_INDICES,
    ALL_ACTIVE_DEFINITIONS,
    BLOCKSANITY_DEFINITIONS,
    BLOCKSANITY_LOCATION_IDS,
    BLOCKSANITY_LOCATION_NAMES,
    BOSS_LOCATION_NAMES,
    ONE_UP_BLOCK_DEFINITIONS,
    ONE_UP_BLOCK_LOCATION_NAMES,
    ONE_UP_BLOCK_LOCATION_IDS,
    RED_COIN_LOCATION_NAMES,
    RED_COIN_LOCATION_IDS,
    NSMBDSLocation,
    TOAD_HOUSE_LOCATION_NAMES,
    WORLD_6_2_BONUS_AREA_LOCATION_NAMES,
)

from .options import (
    ITEM_PLACEMENT_EXCLUDED,
    ITEM_PLACEMENT_NON_PROGRESSION,
    ITEM_PLACEMENT_PROGRESSION,
    NSMBDSOptions,
)
from .regions import REGION_LIST, REGION_LOCATIONS, REGION_CONNECTIONS
from .settings import NSMBDSSettings
from .rom import NSMBDSPatchExtension, NSMBDSProcedurePatch, write_patch_payload
from .client import NSMBDSClient  # Imported to register the BizHawk handler.
from .rules import set_completion_rules, set_rules
from .data.star_coin_gates import STAR_COIN_GATES, TOTAL_STAR_COIN_GATE_COST
from .data.powerup_licenses import license_items_for_mode
from .data.logic_data import (
    ADVANCED_LOCATION_NAMES,
    ALL_SECRET_EXITS,
    CANNON_ROUTE_EXITS,
    INTER_SECRET_DEPENDENT_REGIONS,
    INTER_WORLD_SECRET_EXITS,
    INTRA_SECRET_DEPENDENT_REGIONS,
    INTRA_WORLD_SECRET_EXITS,
)


VANILLA_ROUTE_EVENT_NAMES = ALL_SECRET_EXITS


def allow_non_progression_item(item: Any) -> bool:
    """Allow useful, filler, and trap items while rejecting advancement items."""
    return not item.advancement


def launch_client(*args: str) -> None:
    """Launch the NSMBDS BizHawk client executable component."""
    from .client import main
    launch_subprocess(main, name="NSMBDS BizHawk Client", args=args)


components.insert(
    0,
    Component(
        display_name="NSMBDS Client",
        description="Archipelago client for New Super Mario Bros. DS using BizHawk.",
        func=launch_client,
        component_type=Type.CLIENT,
        file_identifier=SuffixIdentifier(".apnsmbds"),
        game_name="New Super Mario Bros. DS",
    )
)


from .web import NSMBDSWeb


class NSMBDSWorld(World):
    """Archipelago World implementation for New Super Mario Bros. DS."""

    game = "New Super Mario Bros. DS"
    topology_present = True
    web = NSMBDSWeb()
    options_dataclass = NSMBDSOptions
    options: NSMBDSOptions
    settings_key = "nsmbds_options"
    settings: ClassVar[NSMBDSSettings]
    # Universal Tracker can rebuild this world directly from Connected slot data.
    ut_can_gen_without_yaml = True

    item_name_to_id = {name: data[0] for name, data in ITEM_TABLE.items()}
    location_name_to_id = LOCATION_TABLE

    _star_coin_location_names: tuple[str, ...] = tuple(
        name for name in LOCATION_TABLE if " Star Coin " in name
    )
    location_name_groups = {
        "Star Coins": frozenset(_star_coin_location_names),
        "Secret Exits": frozenset(
            name for name in LOCATION_TABLE if name.endswith(" Secret Exit")
        ),
        "Red Coin Challenges": RED_COIN_LOCATION_NAMES,
        "1-Up Blocks": ONE_UP_BLOCK_LOCATION_NAMES,
        "Blocksanity": BLOCKSANITY_LOCATION_NAMES,
        "Toad Houses": TOAD_HOUSE_LOCATION_NAMES,
    }
    _boss_location_names: tuple[str, ...] = BOSS_LOCATION_NAMES
    individual_gate_tiers: dict[str, int]
    vanilla_gate_tiers: dict[str, int]

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        """Ask Universal Tracker to regenerate with the real seed options."""
        return slot_data

    def generate_early(self) -> None:
        """Validate option combinations and host limits before regions and items are created."""
        re_gen_passthrough = getattr(self.multiworld, "re_gen_passthrough", {})
        slot_data = re_gen_passthrough.get(self.game, {})
        if slot_data:
            # New seeds carry every option. The top-level fallback keeps older
            # 0.4.x seeds trackable with the options they already exposed.
            slot_options = slot_data.get("options") or {
                name: slot_data[name]
                for name in NSMBDSOptions.__annotations__
                if name in slot_data
            }
            for name, value in slot_options.items():
                option = getattr(self.options, name, None)
                if option is not None:
                    setattr(self.options, name, option.from_any(value))

        def gate_tiers(
            identifiers: tuple[str, ...],
            slot_data_key: str,
        ) -> dict[str, int]:
            if not slot_data:
                tiers = list(range(1, len(identifiers) + 1))
                self.random.shuffle(tiers)
                return dict(zip(identifiers, tiers))

            if slot_data_key not in slot_data:
                raise ValueError(
                    f"Incompatible NSMBDS slot data: missing required {slot_data_key}."
                )
            stored = slot_data[slot_data_key]

            # Normal generation consumed one shuffle here. Preserve the RNG
            # position during UT reconstruction while using the serialized
            # mapping as the authority.
            shuffled_tiers = list(range(1, len(identifiers) + 1))
            self.random.shuffle(shuffled_tiers)
            restored = {str(identifier): int(tier) for identifier, tier in stored.items()}
            expected_identifiers = set(identifiers)
            expected_tiers = set(range(1, len(identifiers) + 1))
            if set(restored) != expected_identifiers or set(restored.values()) != expected_tiers:
                raise ValueError(
                    f"Invalid {slot_data_key} in slot data: expected every gate and tier "
                    f"from 1 through {len(identifiers)} exactly once."
                )
            return restored

        self.individual_gate_tiers = {}
        self.vanilla_gate_tiers = {}
        gate_mode = int(self.options.star_coin_gate_mode.value)
        if gate_mode == 2:
            self.individual_gate_tiers = gate_tiers(
                tuple(gate.permit_item_name for gate in STAR_COIN_GATES),
                "individual_gate_tiers",
            )
        elif gate_mode == 0:
            self.vanilla_gate_tiers = gate_tiers(
                tuple(gate.name for gate in STAR_COIN_GATES),
                "vanilla_gate_tiers",
            )

        host_settings = get_settings().nsmbds_options
        allow_unsafe_value = host_settings.allow_unsafe_nsmbds_options
        if isinstance(allow_unsafe_value, str):
            allow_unsafe = allow_unsafe_value.strip().lower() in {"1", "true", "yes", "on"}
        else:
            allow_unsafe = bool(allow_unsafe_value)
        # The host already approved these values when the real seed was made;
        # a tracker's local host.yaml must not reject that existing seed.
        allow_unsafe = allow_unsafe or bool(slot_data)

        def _val(opt: Any) -> int:
            return int(getattr(opt, "value", opt))

        def _bool(opt: Any) -> bool:
            return bool(getattr(opt, "value", opt))

        blocksanity_pct = _val(self.options.blocksanity_global_check_percentage)
        trap_pct = _val(self.options.trap_percentage)

        if not allow_unsafe:
            if blocksanity_pct > 30:
                raise Exception(
                    f"Blocksanity Global Check Percentage ({blocksanity_pct}%) "
                    f"exceeds host maximum of 30%. Enable allow_unsafe_nsmbds_options to override."
                )
            if trap_pct > 50:
                raise Exception(
                    f"Trap Percentage ({trap_pct}%) "
                    f"exceeds host maximum of 50%. Enable allow_unsafe_nsmbds_options to override."
                )

        goal = _val(self.options.goal)
        if goal in (1, 3):
            if _val(self.options.required_star_coins) > 240:
                raise Exception(
                    "Required Star Coins cannot exceed 240."
                )

        fillers_enabled = any([
            _bool(self.options.filler_powerups),
            _bool(self.options.filler_starman),
            _bool(self.options.filler_extra_lives),
            _bool(self.options.filler_coins),
            _bool(self.options.filler_time_capsule),
            _bool(self.options.filler_starman_lite),
            _bool(self.options.filler_trap_shield),
            _bool(self.options.filler_care_package),
            _bool(self.options.filler_life_insurance),
        ])
        traps_enabled = any([
            _bool(self.options.trap_hyper_speed), _bool(self.options.trap_slow_speed), _bool(self.options.trap_walljump_lock),
            _bool(self.options.trap_no_jump), _bool(self.options.trap_reverse_controls), _bool(self.options.trap_no_sprint),
            _bool(self.options.trap_button_roulette), _bool(self.options.trap_ice_shoes), _bool(self.options.trap_heavy_mario),
            _bool(self.options.trap_auto_run), _bool(self.options.trap_sticky_buttons), _bool(self.options.trap_coin_tax),
            _bool(self.options.trap_camera_drift), _bool(self.options.trap_screen_flip), _bool(self.options.trap_camera_sway),
            _bool(self.options.trap_boo_curse), _bool(self.options.trap_im_stuck), _bool(self.options.trap_screen_tint),
            _bool(self.options.trap_retro_filter), _bool(self.options.trap_spotlight), _bool(self.options.trap_ground_clap),
            _bool(self.options.trap_head_bonk), _bool(self.options.trap_crazy_pixels), _bool(self.options.trap_bonk),
            _bool(self.options.trap_timer_drain), _bool(self.options.trap_coin_thief),
            _bool(self.options.trap_no_turnaround),
            _bool(self.options.trap_powerup_pickpocket),
        ])
        if trap_pct > 0 and not traps_enabled:
            raise Exception(
                "Trap Percentage is greater than 0%, but all individual trap types are disabled."
            )
        if not fillers_enabled and (trap_pct == 0 or not traps_enabled):
            raise Exception(
                "No filler items or traps are available to fill non-progression item pool slots. "
                "Please enable at least one filler category or trap type."
            )

    def create_regions(self) -> None:
        """Create all game regions, connect them, and populate with locations."""
        created_regions: dict[str, Region] = {}

        # Create all regions
        for region_name in REGION_LIST:
            region = Region(region_name, self.player, self.multiworld)
            created_regions[region_name] = region
            self.multiworld.regions.append(region)

        active_block_locations: list[NSMBDSLocation] = []

        # Add locations to each region
        for region_name, location_names in REGION_LOCATIONS.items():
            region = created_regions[region_name]
            for loc_name in location_names:
                # Skip optional check categories when disabled in YAML options.
                is_bonus_area = loc_name in WORLD_6_2_BONUS_AREA_LOCATION_NAMES
                if is_bonus_area and self.options.world_6_2_bonus_area.value == 0:
                    continue
                is_disabled_secret_exit = (
                    "Secret Exit" in loc_name
                    and not self.options.secret_exit_checks
                )
                if is_disabled_secret_exit and loc_name not in VANILLA_ROUTE_EVENT_NAMES:
                    continue
                loc_id = None if is_disabled_secret_exit else LOCATION_TABLE[loc_name]
                if loc_id in RED_COIN_LOCATION_IDS and not self.options.red_coin_checks:
                    continue
                if loc_id in ONE_UP_BLOCK_LOCATION_IDS and not self.options.one_up_block_checks:
                    continue
                if loc_id in BLOCKSANITY_LOCATION_IDS and not self.options.blocksanity:
                    continue
                if "Toad House" in loc_name and not self.options.toad_house_checks:
                    continue
                location = NSMBDSLocation(self.player, loc_name, loc_id, region)
                if loc_id is None:
                    location.place_locked_item(NSMBDSItem(
                        "Vanilla Route Event",
                        ItemClassification.progression,
                        None,
                        self.player,
                    ))
                    region.locations.append(location)
                    continue
                if is_bonus_area:
                    # World 6-2 Bonus Area NEVER contains progression items
                    placement_mode = ITEM_PLACEMENT_EXCLUDED
                elif loc_id in ONE_UP_BLOCK_LOCATION_IDS:
                    placement_mode = self.options.one_up_block_item_placement.value
                elif loc_id in BLOCKSANITY_LOCATION_IDS:
                    placement_mode = self.options.blocksanity_item_placement.value
                else:
                    placement_mode = ITEM_PLACEMENT_PROGRESSION
                if placement_mode == ITEM_PLACEMENT_EXCLUDED:
                    location.progress_type = LocationProgressType.EXCLUDED
                elif placement_mode == ITEM_PLACEMENT_NON_PROGRESSION:
                    location.item_rule = allow_non_progression_item
                    setattr(location, "is_non_progression_only", True)

                route_non_progression = (
                    (
                        not self.options.secret_exit_shortcut_logic
                        and (
                            loc_name in INTRA_WORLD_SECRET_EXITS
                            or region_name in INTRA_SECRET_DEPENDENT_REGIONS
                        )
                    )
                    or (
                        not self.options.secret_exit_world_unlock_logic
                        and (
                            loc_name in INTER_WORLD_SECRET_EXITS
                            or region_name in INTER_SECRET_DEPENDENT_REGIONS
                        )
                    )
                    or (
                        not self.options.cannon_route_logic
                        and loc_name in CANNON_ROUTE_EXITS
                    )
                )
                advanced_non_progression = (
                    self.options.advanced_location_item_placement.value == 1
                    and loc_name in ADVANCED_LOCATION_NAMES
                )
                if route_non_progression or advanced_non_progression:
                    location.item_rule = allow_non_progression_item
                    setattr(location, "is_non_progression_only", True)
                region.locations.append(location)
                if loc_id in BLOCKSANITY_LOCATION_IDS or is_bonus_area:
                    active_block_locations.append(location)

        # Apply Blocksanity global check percentage & round-robin distribution with W6-2 Bonus sub-cap (max 16)
        if active_block_locations:
            percentage = int(getattr(self.options.blocksanity_global_check_percentage, "value", self.options.blocksanity_global_check_percentage))
            total_blocks = len(active_block_locations)
            global_target_count = round(total_blocks * (percentage / 100.0))

            # Strictly cap W6-2 bonus area global multiworld checks at max 16
            bonus_area_locs = [loc for loc in active_block_locations if loc.name in WORLD_6_2_BONUS_AREA_LOCATION_NAMES]
            normal_block_locs = [loc for loc in active_block_locations if loc.name not in WORLD_6_2_BONUS_AREA_LOCATION_NAMES]

            MAX_BONUS_AREA_GLOBAL_CHECKS = 16
            if len(bonus_area_locs) > MAX_BONUS_AREA_GLOBAL_CHECKS:
                self.random.shuffle(bonus_area_locs)
                bonus_area_global_candidates = bonus_area_locs[:MAX_BONUS_AREA_GLOBAL_CHECKS]
                for loc in bonus_area_locs[MAX_BONUS_AREA_GLOBAL_CHECKS:]:
                    loc.progress_type = LocationProgressType.EXCLUDED
                    setattr(loc, "is_local_filler_only", True)
            else:
                bonus_area_global_candidates = bonus_area_locs

            candidates = normal_block_locs + bonus_area_global_candidates

            if global_target_count < len(candidates):
                by_stage: dict[str, list[NSMBDSLocation]] = {}
                for loc in candidates:
                    stage_prefix = loc.name.split(" Block")[0].split(" Flying")[0]
                    by_stage.setdefault(stage_prefix, []).append(loc)
                for locs in by_stage.values():
                    self.random.shuffle(locs)

                global_selected: set[NSMBDSLocation] = set()
                stages = sorted(by_stage.keys())
                stage_idx = 0
                while len(global_selected) < global_target_count and any(by_stage.values()):
                    stage = stages[stage_idx % len(stages)]
                    if by_stage[stage]:
                        global_selected.add(by_stage[stage].pop(0))
                    stage_idx += 1

                for loc in candidates:
                    if loc not in global_selected:
                        loc.progress_type = LocationProgressType.EXCLUDED
                        setattr(loc, "is_local_filler_only", True)

        # Connect regions via entrances
        for source_name, targets in REGION_CONNECTIONS.items():
            source = created_regions[source_name]
            for target_name in targets:
                source.connect(created_regions[target_name])

    def create_items(self) -> None:
        """Fill the item pool based on the number of active locations and user options."""
        def _val(opt: Any) -> int:
            return int(getattr(opt, "value", opt))

        def _bool(opt: Any) -> bool:
            return bool(getattr(opt, "value", opt))

        def _weighted_filler_choice(item_names: list[str] | tuple[str, ...]) -> str:
            return self.random.choices(
                item_names,
                weights=[FILLER_ITEM_WEIGHTS[name] for name in item_names],
                k=1,
            )[0]

        def _enabled_excludable_fillers() -> list[str]:
            fillers = []
            if _bool(self.options.filler_extra_lives):
                fillers.extend(["1-Up Mushroom", "3-Up Moon"])
            if _bool(self.options.filler_coins):
                fillers.append("Coin Bundle")
            if _bool(self.options.filler_time_capsule):
                fillers.append("Time Capsule")
            if _bool(self.options.filler_starman_lite):
                fillers.append("Starman Lite")
            if _bool(self.options.filler_trap_shield):
                fillers.append("Trap Shield")
            if _bool(self.options.filler_care_package):
                fillers.append("Small Care Package")
            if _bool(self.options.filler_life_insurance):
                fillers.append("Life Insurance")
            return fillers

        active_traps = []
        if _bool(self.options.trap_hyper_speed): active_traps.append("Super Speed")
        if _bool(self.options.trap_slow_speed): active_traps.append("Slowness")
        if _bool(self.options.trap_walljump_lock): active_traps.append("Slippery Gloves")
        if _bool(self.options.trap_no_jump): active_traps.append("Ground Bound")
        if _bool(self.options.trap_reverse_controls): active_traps.append("Hyper Confusion")
        if _bool(self.options.trap_no_sprint): active_traps.append("No Sprint")
        if _bool(self.options.trap_button_roulette): active_traps.append("Button Swap")
        if _bool(self.options.trap_ice_shoes): active_traps.append("Ice Shoes")
        if _bool(self.options.trap_heavy_mario): active_traps.append("Heavy Mario")
        if _bool(self.options.trap_auto_run): active_traps.append("Can't Stop")
        if _bool(self.options.trap_sticky_buttons): active_traps.append("Sticky Buttons")
        if _bool(self.options.trap_coin_tax): active_traps.append("Coin Tax")
        if _bool(self.options.trap_camera_drift): active_traps.append("Camera Drift")
        if _bool(self.options.trap_screen_flip): active_traps.append("Screen Flip")
        if _bool(self.options.trap_camera_sway): active_traps.append("Drunk Camera")
        if _bool(self.options.trap_boo_curse): active_traps.append("Boo Curse")
        if _bool(self.options.trap_im_stuck): active_traps.append("I'm Stuck")
        if _bool(self.options.trap_screen_tint): active_traps.append("Screen Tint")
        if _bool(self.options.trap_retro_filter): active_traps.append("Retro Filter")
        if _bool(self.options.trap_spotlight): active_traps.append("Spotlight")
        if _bool(self.options.trap_ground_clap): active_traps.append("Ground Clap")
        if _bool(self.options.trap_head_bonk): active_traps.append("Head Bonk")
        if _bool(self.options.trap_crazy_pixels): active_traps.append("Pixelation")
        if _bool(self.options.trap_bonk): active_traps.append("Bonk Trap")
        if _bool(self.options.trap_timer_drain): active_traps.append("Time Drain")
        if _bool(self.options.trap_coin_thief): active_traps.append("Coin Thief")
        if _bool(self.options.trap_no_turnaround): active_traps.append("No Turnaround Trap")
        if _bool(self.options.trap_powerup_pickpocket): active_traps.append("Power-Up Pickpocket Trap")

        trap_pct = _val(self.options.trap_percentage)

        # Pre-fill local-filler-only block locations with enabled local consumables and traps.
        # These locked placements bypass the regular item pool, so they must apply the
        # filler-category options independently as well.
        local_blocksanity_fillers = _enabled_excludable_fillers() or ["Nothing"]
        unfilled_locations = self.multiworld.get_unfilled_locations(self.player)
        for loc in unfilled_locations:
            if getattr(loc, "is_local_filler_only", False):
                if active_traps and trap_pct > 0 and self.random.randint(1, 100) <= trap_pct:
                    item_name = self.random.choice(active_traps)
                else:
                    item_name = _weighted_filler_choice(local_blocksanity_fillers)
                loc.place_locked_item(self.create_item(item_name))

        # Re-query unfilled locations after local pre-fill
        unfilled_locations = self.multiworld.get_unfilled_locations(self.player)
        location_count = len(unfilled_locations)
        excluded_location_count = sum(
            location.progress_type == LocationProgressType.EXCLUDED
            for location in unfilled_locations
        )
        progression_restricted_location_count = sum(
            location.progress_type == LocationProgressType.EXCLUDED
            or getattr(location, "is_non_progression_only", False)
            for location in unfilled_locations
        )
        progression_location_count = location_count - progression_restricted_location_count

        random_item_count = location_count

        prog_names = list(PROGRESSION_ITEM_NAMES)
        prog_names.extend(license_items_for_mode(self.options))
        if self.options.star_coin_gate_mode.value == 1:
            prog_names.extend(["Progressive Gate Pass"] * len(STAR_COIN_GATES))
        elif self.options.star_coin_gate_mode.value == 2:
            prog_names.extend(gate.permit_item_name for gate in STAR_COIN_GATES)
        if self.options.tower_castle_keys:
            prog_names.extend(KEY_ITEM_NAMES)

        pool = [self.create_item(name) for name in prog_names]

        # All 240 checks still contribute one Star Coin item. The first 160
        # cover every vanilla sign purchase; a higher Coin goal raises that
        # progression floor. Excess Coins remain useful currency without
        # causing Progression Balancing to pull the entire currency pool early.
        star_coin_count = len(self._star_coin_location_names)
        goal = _val(self.options.goal)
        goal_coin_target = (
            _val(self.options.required_star_coins)
            if goal in (1, 3)
            else 0
        )
        progression_star_coin_count = min(
            star_coin_count,
            max(TOTAL_STAR_COIN_GATE_COST, goal_coin_target),
        )
        star_coin_id = ITEM_TABLE["Star Coin"][0]
        pool.extend(
            NSMBDSItem(
                "Star Coin",
                ItemClassification.progression_skip_balancing,
                star_coin_id,
                self.player,
            )
            for _ in range(progression_star_coin_count)
        )
        pool.extend(
            NSMBDSItem(
                "Star Coin",
                ItemClassification.useful,
                star_coin_id,
                self.player,
            )
            for _ in range(star_coin_count - progression_star_coin_count)
        )

        progression_item_count = len(prog_names) + progression_star_coin_count
        if progression_item_count > progression_location_count:
            raise Exception(
                f"The required progression item count ({progression_item_count}) exceeds the "
                f"number of locations allowed to hold progression ({progression_location_count}). "
                f"Please enable progression placement on Blocksanity/1-Up Blocks or reduce progression options."
            )

        remaining = random_item_count - len(pool)
        if remaining < 0:
            raise Exception(
                "The active location count is smaller than the required progression item count."
            )

        # Build active filler pool from enabled filler categories
        excludable_fillers = _enabled_excludable_fillers()
        useful_fillers = []
        if self.options.filler_powerups:
            useful_fillers.extend(["Mushroom", "Fire Flower", "Blue Shell", "Mini Mushroom", "Mega Mushroom"])
        if self.options.filler_starman:
            useful_fillers.append("Starman Buff")
        guaranteed_filler_pool = excludable_fillers or ["Nothing"]
        active_fillers = [*excludable_fillers, *useful_fillers]
        if not active_fillers:
            active_fillers = ["Nothing"]

        # Build active trap pool from enabled trap toggles
        active_traps = []
        if self.options.trap_hyper_speed:
            active_traps.append("Super Speed")
        if self.options.trap_slow_speed:
            active_traps.append("Slowness")
        if self.options.trap_walljump_lock:
            active_traps.append("Slippery Gloves")
        if self.options.trap_no_jump:
            active_traps.append("Ground Bound")
        if self.options.trap_reverse_controls:
            active_traps.append("Hyper Confusion")
        if self.options.trap_no_sprint:
            active_traps.append("No Sprint")
        if self.options.trap_button_roulette:
            active_traps.append("Button Swap")
        if self.options.trap_ice_shoes:
            active_traps.append("Ice Shoes")
        if self.options.trap_heavy_mario:
            active_traps.append("Heavy Mario")
        if self.options.trap_auto_run:
            active_traps.append("Can't Stop")
        if self.options.trap_sticky_buttons:
            active_traps.append("Sticky Buttons")
        if self.options.trap_coin_tax:
            active_traps.append("Coin Tax")
        if self.options.trap_camera_drift:
            active_traps.append("Camera Drift")
        if self.options.trap_screen_flip:
            active_traps.append("Screen Flip")
        if self.options.trap_camera_sway:
            active_traps.append("Drunk Camera")
        if self.options.trap_boo_curse:
            active_traps.append("Boo Curse")
        if self.options.trap_im_stuck:
            active_traps.append("I'm Stuck")
        if self.options.trap_screen_tint:
            active_traps.append("Screen Tint")
        if self.options.trap_retro_filter:
            active_traps.append("Retro Filter")
        if self.options.trap_spotlight:
            active_traps.append("Spotlight")
        if self.options.trap_ground_clap:
            active_traps.append("Ground Clap")
        if self.options.trap_head_bonk:
            active_traps.append("Head Bonk")
        if self.options.trap_crazy_pixels:
            active_traps.append("Pixelation")
        if self.options.trap_bonk:
            active_traps.append("Bonk Trap")
        if self.options.trap_timer_drain:
            active_traps.append("Time Drain")
        if self.options.trap_coin_thief:
            active_traps.append("Coin Thief")
        if self.options.trap_no_turnaround:
            active_traps.append("No Turnaround Trap")
        if self.options.trap_powerup_pickpocket:
            active_traps.append("Power-Up Pickpocket Trap")

        trap_count, guaranteed_filler_count, flexible_count = (
            calculate_nonprogression_pool_counts(
                remaining,
                excluded_location_count,
                self.options.trap_percentage.value,
                bool(active_traps),
            )
        )

        for _ in range(guaranteed_filler_count):
            pool.append(self.create_item(_weighted_filler_choice(guaranteed_filler_pool)))

        for _ in range(flexible_count):
            pool.append(self.create_item(_weighted_filler_choice(active_fillers)))

        for _ in range(trap_count):
            pool.append(self.create_item(self.random.choice(active_traps)))

        self.multiworld.itempool += pool

    def create_item(self, name: str) -> NSMBDSItem:
        """Create a single item by name."""
        data = ITEM_TABLE[name]
        return NSMBDSItem(name, data[1], data[0], self.player)

    def get_filler_item_name(self) -> str:
        """Return a safe repeatable replacement for plando and item links."""
        return "Nothing"

    def fill_hook(
        self,
        progitempool: list[Item],
        usefulitempool: list[Item],
        filleritempool: list[Item],
        fill_locations: list[Location],
    ) -> None:
        """Place items with gated-stage restrictions before unrestricted progression."""
        # Core's restrictive fill consumes progression from the end of this
        # list. Star Coins and keys cannot be placed in Star-Coin-gated stages,
        # so give them first choice of the smaller set of valid locations.
        restricted_names = frozenset(("Star Coin", *KEY_ITEM_NAMES))
        restricted_items = [
            item
            for item in progitempool
            if item.player == self.player and item.name in restricted_names
        ]
        if not restricted_items:
            return
        progitempool[:] = [
            item
            for item in progitempool
            if item.player != self.player or item.name not in restricted_names
        ] + restricted_items

    def set_rules(self) -> None:
        """Apply logic rules to regions and locations."""
        set_rules(self)

    def generate_output(self, output_directory: str) -> None:
        """Create a per-player patch file from the verified clean A2DE ROM."""
        patch = NSMBDSProcedurePatch(
            player=self.player,
            player_name=self.multiworld.player_name[self.player],
        )
        write_patch_payload(self, patch)
        patch_path = os.path.join(
            output_directory,
            f"{self.multiworld.get_out_file_name_base(self.player)}{patch.patch_file_ending}",
        )
        patch.write(patch_path)

    def generate_basic(self) -> None:
        """Define logical completion conditions from the real boss checks."""
        set_completion_rules(self)

    def fill_slot_data(self) -> dict[str, Any]:
        """Send options data to the client via the Connected packet."""
        slot_data: dict[str, Any] = {
            # Universal Tracker needs the complete option set to reconstruct
            # exactly the same regions and rules without the original YAML.
            "options": {
                name: getattr(self.options, name).value
                for name in NSMBDSOptions.__annotations__
            },
            "goal": self.options.goal.value,
            # Keep these explicit compatibility flags for clients and trackers.
            # New seeds always use randomized Star Coin checks and items.
            "star_coin_checks": True,
            "star_coin_items": True,
            "red_coin_checks": bool(self.options.red_coin_checks.value),
            "one_up_block_checks": bool(self.options.one_up_block_checks.value),
            "one_up_block_item_placement": self.options.one_up_block_item_placement.value,
            "blocksanity": bool(self.options.blocksanity.value),
            "blocksanity_item_placement": self.options.blocksanity_item_placement.value,
            "world_6_2_bonus_area": self.options.world_6_2_bonus_area.value,
            "secret_exit_checks": bool(self.options.secret_exit_checks.value),
            "toad_house_checks": bool(self.options.toad_house_checks.value),
            "secret_exit_shortcut_logic": bool(self.options.secret_exit_shortcut_logic.value),
            "secret_exit_world_unlock_logic": bool(self.options.secret_exit_world_unlock_logic.value),
            "cannon_route_logic": bool(self.options.cannon_route_logic.value),
            "advanced_location_item_placement": self.options.advanced_location_item_placement.value,
            "required_star_coins": self.options.required_star_coins.value,
            "star_coin_gate_mode": self.options.star_coin_gate_mode.value,
            "tower_castle_keys": bool(self.options.tower_castle_keys.value),
            "license_mini_mushroom": bool(self.options.license_mini_mushroom.value),
            "license_blue_shell": bool(self.options.license_blue_shell.value),
            "license_mega_mushroom": bool(self.options.license_mega_mushroom.value),
            "license_mushroom": bool(self.options.license_mushroom.value),
            "license_fire_flower": bool(self.options.license_fire_flower.value),
            "license_touchscreen_pocket": bool(self.options.license_touchscreen_pocket.value),
            "trap_percentage": self.options.trap_percentage.value,
            "mario_palette": self.options.mario_palette.value,
            "luigi_palette": self.options.luigi_palette.value,
            "secondary_screen_background": self.options.secondary_screen_background.value,
            "bonk_trap_can_kill": bool(self.options.bonk_trap_can_kill.value),
            "filler_time_capsule": bool(self.options.filler_time_capsule.value),
            "filler_starman_lite": bool(self.options.filler_starman_lite.value),
            "filler_trap_shield": bool(self.options.filler_trap_shield.value),
            "filler_care_package": bool(self.options.filler_care_package.value),
            "filler_life_insurance": bool(self.options.filler_life_insurance.value),
            "death_link": bool(self.options.death_link.value),
            "death_link_triggers_on_insured_death": bool(self.options.death_link_triggers_on_insured_death.value),
        }
        if self.individual_gate_tiers:
            slot_data["individual_gate_tiers"] = dict(self.individual_gate_tiers)
        if self.vanilla_gate_tiers:
            slot_data["vanilla_gate_tiers"] = dict(self.vanilla_gate_tiers)
        return slot_data
