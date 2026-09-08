"""
New Super Mario Bros. DS - YAML Options
Player-facing settings exposed in the Archipelago YAML configuration file.
"""

from dataclasses import dataclass

from Options import Choice, DeathLink, OptionSet, PerGameCommonOptions, Range, Toggle

from .locations import ACTIVE_STAR_COIN_COUNT

ITEM_PLACEMENT_EXCLUDED = 0
ITEM_PLACEMENT_PROGRESSION = 1
ITEM_PLACEMENT_NON_PROGRESSION = 2


# =============================================================================
# 1. GOAL & LOCATION CHECK OPTIONS
# =============================================================================

class Goal(Choice):
    """
    Choose the victory condition.

    defeat_bowser:   Reach World 8 and defeat Bowser in World 8-Bowser's Castle. (Default)
    star_coin_hunt:  Collect the required number of Star Coins across the multiworld.
    world_tour:      Defeat all 9 Castle bosses.
    completionist:   Defeat all 9 Castle bosses AND collect all required Star Coins.
    """
    display_name = "Goal"
    option_defeat_bowser  = 0
    option_star_coin_hunt = 1
    option_world_tour     = 2
    option_completionist  = 3
    default = 0


class RequiredStarCoins(Range):
    """
    Relevant for 'Star Coin Hunt' and 'Completionist' goals.
    The number of Star Coins required for victory goal.
    You can set this to any target (e.g. 40, 80, 120) while keeping all 240 Star Coin check locations active!
    """
    display_name = "Required Star Coins"
    range_start = 30
    range_end   = ACTIVE_STAR_COIN_COUNT
    default     = 80


class RedCoinChecks(Toggle):
    """Include all 29 Red Coin Ring challenges across the world map as check locations."""
    display_name = "Red Coin Checks"
    default = 1


class OneUpBlockChecks(Toggle):
    """Include 1-Up Blocks across all levels as check locations."""
    display_name = "1-Up Block Checks"
    default = 0


class OneUpBlockItemPlacement(Choice):
    """
    Controls which items may be placed at enabled 1-Up Block checks.

    excluded:        Only filler or enabled traps; useful and progression items are forbidden.
    non_progression: Allow filler, useful items, and enabled traps, but no progression. (Default)
    progression:     Treat these checks as normal locations that may contain progression.
    """
    display_name = "1-Up Block Item Placement"
    option_excluded = ITEM_PLACEMENT_EXCLUDED
    option_progression = ITEM_PLACEMENT_PROGRESSION
    option_non_progression = ITEM_PLACEMENT_NON_PROGRESSION
    default = ITEM_PLACEMENT_NON_PROGRESSION


class Blocksanity(Toggle):
    """Include static and flying Coin/Power-up Blocks as Archipelago checks."""
    display_name = "Blocksanity"
    default = 0


class BlocksanityItemPlacement(Choice):
    """
    Controls which items may be placed at enabled Blocksanity checks.

    excluded:        Only filler or enabled traps; useful and progression items are forbidden.
    non_progression: Allow filler, useful items, and enabled traps, but no progression. (Default)
    progression:     Treat these checks as normal locations that may contain progression.
    """
    display_name = "Blocksanity Item Placement"
    option_excluded = ITEM_PLACEMENT_EXCLUDED
    option_progression = ITEM_PLACEMENT_PROGRESSION
    option_non_progression = ITEM_PLACEMENT_NON_PROGRESSION
    default = ITEM_PLACEMENT_NON_PROGRESSION


class BlocksanityGlobalCheckPercentage(Range):
    """
    Percentage of active Blocksanity and World 6-2 Bonus Area block checks that
    serve as global multiworld locations (containing items for other players).

    The remaining percentage is restricted to local filler items and traps for the NSMBDS player.
    0% = All block checks are local filler and traps.
    30% = Standard host safety maximum (values above 30% require host setting 'allow_unsafe_nsmbds_options: true').
    100% = All block checks are global multiworld locations.
    """
    display_name = "Blocksanity Global Check Percentage"
    range_start = 0
    range_end   = 100
    default     = 30


class WorldSixTwoBonusArea(Toggle):
    """
    Controls the 128 flying blocks in the World 6-2 bonus room.
    When enabled, these checks are included in the block check pool.

    Safety & Balance:
    - Never contains progression items.
    - Capped at a strict maximum of 16 global multiworld checks for other players;
      all remaining 112+ blocks in the room are reserved for local filler and traps.
    """
    display_name = "World 6-2 Bonus Area"
    default = 0


class SecretExitChecks(Toggle):
    """Include the 18 Secret Exit locations across the world map in the check pool."""
    display_name = "Secret Exit Checks"
    default = 0


class ToadHouseChecks(Toggle):
    """Include Toad House locations on the world map as check locations."""
    display_name = "Toad House Checks"
    default = 1


class SecretExitShortcutLogic(Toggle):
    """Allow secret-exit paths as shortcuts in world logic."""
    display_name = "Secret Exit Shortcut Logic"
    default = 0


class SecretExitWorldUnlockLogic(Toggle):
    """Allow the Mini-Mario castle exits to Worlds 4 and 7 in world logic."""
    display_name = "Secret Exit World Unlock Logic"
    default = 0


class CannonRouteLogic(Toggle):
    """Allow Warp Cannon routes to other worlds in world logic."""
    display_name = "Cannon Route Logic"
    default = 0


class AdvancedLocationItemPlacement(Choice):
    """
    Controls whether hard-to-reach or well-hidden locations (such as hidden
    blocks) can contain required progression items.

    allow_progression: Hard and hidden locations are treated normally and can
                       hold required items. (Default)
    non_progression:  Keeps required items out of hard or obscure checks.
    """
    display_name = "Advanced Location Item Placement"
    option_allow_progression = 0
    option_non_progression = 1
    default = 0


# =============================================================================
# 2. OVERWORLD & PROGRESSION LOGIC OPTIONS
# =============================================================================

class LevelRandomization(Choice):
    """
    [Alpha] Randomize which compatible course is loaded by each overworld level slot.

    off:           Keep every course in its vanilla slot. (Default)
    global:        Shuffle courses across all eight worlds.
    within_world:  Shuffle courses only among compatible slots in the same world.

    Secret-exit courses, Towers, Castles, and normal courses are separate pools.
    World 8-Bowser's Castle always remains fixed.
    """
    display_name = "[Alpha] Level Randomization"
    option_off = 0
    option_global = 1
    option_within_world = 2
    default = 0


class StarCoinGateMode(Choice):
    """
    Controls Star-Coin signs on the overworld map.

    In every mode, gates are arranged in tiers. Early tiers are cheaper and
    later tiers require more Star Coins.

    vanilla:     Collect enough Star Coins to open each tier.
    progressive: Collect Star Coins and Progressive Gate Passes to unlock the
                 tiers one after another.
    individual:  Collect Star Coins and the matching named Gate Pass for each tier.
    """
    display_name = "Star Coin Gate Mode"
    option_vanilla = 0
    option_progressive = 1
    option_individual = 2
    default = 0


class TowerCastleKeys(Toggle):
    """
    Include one physical key for every Tower and Castle in the item pool.
    When enabled, players must find each matching key to unlock its path gate.
    """
    display_name = "Tower & Castle Keys"
    default = 1

class LicenseMiniMushroom(Toggle):
    """
    Include Mini Mushroom Permit in the item pool and logic.
    Needed for Secret Exits.
    """
    display_name = "License: Mini Mushroom"
    default = 1


class LicenseBlueShell(Toggle):
    """
    Include Blue Shell Permit in the item pool and logic.
    Needed for Secret Exits.
    """
    display_name = "License: Blue Shell"
    default = 1


class LicenseMegaMushroom(Toggle):
    """Include Mega Mushroom Permit in the item pool and logic."""
    display_name = "License: Mega Mushroom"
    default = 1


class LicenseMushroom(Toggle):
    """Include Super Mushroom Permit in the item pool and logic."""
    display_name = "License: Super Mushroom"
    default = 0


class LicenseFireFlower(Toggle):
    """Include Fire Flower Permit in the item pool and logic."""
    display_name = "License: Fire Flower"
    default = 1


class LicenseTouchscreenPocket(Toggle):
    """Include Touchscreen Pocket Permit (reserve item storage) in the item pool and logic.
       If enabled, players cannot use the Touchscreen Pocket until they find the Permit item in the multiworld."""
    display_name = "License: Touchscreen Pocket"
    default = 0


# =============================================================================
# 3. FILLER ITEM OPTIONS
# =============================================================================

FILLER_ITEMS_BY_KEY: dict[str, tuple[str, ...]] = {
    "powerups": ("Mushroom", "Fire Flower", "Blue Shell", "Mini Mushroom", "Mega Mushroom"),
    "starman": ("Starman Buff",),
    "extra_lives": ("1-Up Mushroom", "3-Up Moon"),
    "coins": ("Coin Bundle",),
    "time_capsule": ("Time Capsule",),
    "starman_lite": ("Starman Lite",),
    "trap_shield": ("Trap Shield",),
    "care_package": ("Small Care Package",),
    "life_insurance": ("Life Insurance",),
}


class FillerItems(OptionSet):
    """
    Filler item categories enabled for the item pool. Remove an entry to disable
    that category. At least one entry must remain enabled.

    powerups:      Mushrooms, Fire Flowers, Blue Shells, Mini Mushrooms, and Mega Mushrooms.
    starman:       15 seconds of invincibility.
    extra_lives:   1-Up Mushrooms and rare 3-Up Moons.
    coins:         Bundles of 50 Coins.
    time_capsule:  Adds 30 seconds to the current level timer.
    starman_lite:  Five seconds of invincibility.
    trap_shield:   Blocks the next received trap.
    care_package:  Grants time, Coins, and one life.
    life_insurance: Prevents the next death from consuming a life.
    """
    display_name = "Filler Items"
    valid_keys = frozenset(FILLER_ITEMS_BY_KEY)
    default = valid_keys


# =============================================================================
# 4. TRAP & DEATH LINK OPTIONS
# =============================================================================

class TrapPercentage(Range):
    """
    Percentage of filler item slots that will be replaced with traps.
    Set to 0 to disable all traps.

    Values above 50% require host setting 'allow_unsafe_nsmbds_options: true'.
    """
    display_name = "Trap Percentage"
    range_start = 0
    range_end   = 100
    default     = 15


class BonkTrapCanKill(Toggle):
    """
    If enabled, receiving a Bonk / Damage Trap while already Small Mario (no power-up)
    will killing Mario and triggering Death Link if enabled.
    If disabled (default), receiving a Bonk / Damage Trap as Small Mario will be non-lethal.
    """
    display_name = "Bonk Trap Can Kill"
    default = 0


class DeathLinkTriggersOnInsuredDeath(Toggle):
    """
    Whether dying locally while holding a Life Insurance charge should trigger a Death Link to other players.
    If true, insured local deaths send a Death Link.
    If false (default), insured local deaths do not send a Death Link to other players.
    """
    display_name = "Death Link: Trigger on Insured Deaths"
    default = 0


class DeathLinkGracePercentage(Range):
    """
    Percentage chance that an incoming Death Link is ignored completely.
    A value of 0 applies every incoming Death Link. The maximum of 75 still
    allows one quarter of incoming Death Links through on average.
    Local eligible deaths are always sent while Death Link is enabled.
    """
    display_name = "Death Link: Grace Percentage"
    range_start = 0
    range_end = 75
    default = 0


class DeathLinkCooldownSeconds(Range):
    """
    Number of seconds after an incoming Death Link effect is applied during which
    further incoming Death Links are ignored. The cooldown starts only after the
    queued effect is successfully applied in a level.
    """
    display_name = "Death Link: Cooldown Seconds"
    range_start = 0
    range_end = 300
    default = 0


class DeathLinkEffect(Choice):
    """
    Effect used for incoming Death Links.

    death:          Defeat Mario by expiring the level timer.
    damage:         Apply a normal hit; powered-up Mario loses a power-up and Small Mario dies.
    timer_drain:    Remove 100 seconds from the level timer, possibly reducing it to zero.
    lose_all_coins: Set the current normal Coin counter to zero.
    random_effect:  Choose one of the four effects independently for every accepted Death Link.
    """
    display_name = "Death Link: Effect"
    option_death = 0
    option_damage = 1
    option_timer_drain = 2
    option_lose_all_coins = 3
    option_random_effect = 4
    default = 0


class DeathLinkRandomEffects(OptionSet):
    """
    Effects that may be selected when Death Link: Effect is set to random_effect.
    At least one effect must remain enabled.
    """
    display_name = "Death Link: Random Effects"
    valid_keys = frozenset({"death", "damage", "timer_drain", "lose_all_coins"})
    default = valid_keys


TRAP_ITEMS_BY_KEY: dict[str, str] = {
    "hyper_speed": "Super Speed",
    "slow_speed": "Slowness",
    "walljump_lock": "Slippery Gloves",
    "no_jump": "Ground Bound",
    "reverse_controls": "Hyper Confusion",
    "no_sprint": "No Sprint",
    "button_roulette": "Button Swap",
    "ice_shoes": "Ice Shoes",
    "heavy_mario": "Heavy Mario",
    "auto_run": "Can't Stop",
    "sticky_buttons": "Sticky Buttons",
    "coin_tax": "Coin Tax",
    "camera_drift": "Camera Drift",
    "screen_flip": "Screen Flip",
    "camera_sway": "Drunk Camera",
    "boo_curse": "Boo Curse",
    "im_stuck": "I'm Stuck",
    "screen_tint": "Screen Tint",
    "retro_filter": "Retro Filter",
    "spotlight": "Spotlight",
    "ground_clap": "Ground Clap",
    "head_bonk": "Head Bonk",
    "crazy_pixels": "Pixelation",
    "bonk": "Bonk Trap",
    "timer_drain": "Time Drain",
    "coin_thief": "Coin Thief",
    "no_turnaround": "No Turnaround Trap",
    "powerup_pickpocket": "Power-Up Pickpocket Trap",
}


class Traps(OptionSet):
    """
    Trap types enabled for the item pool. Remove an entry to disable that trap.
    An empty list disables all traps, regardless of Trap Percentage.

    hyper_speed:         Makes Mario run much faster.
    slow_speed:          Makes Mario move more slowly.
    walljump_lock:       Temporarily disables wall jumps.
    no_jump:             Temporarily prevents jumping.
    reverse_controls:    Reverses left and right.
    no_sprint:           Temporarily disables sprinting.
    button_roulette:     Swaps the jump and sprint buttons.
    ice_shoes:           Makes stopping and turning slippery.
    heavy_mario:         Lowers jumps and makes Mario fall faster.
    auto_run:            Forces Mario to keep running.
    sticky_buttons:      Briefly keeps released directions held.
    coin_tax:            Removes up to ten Coins.
    camera_drift:        Pulls the camera to one side.
    screen_flip:         Turns both DS screens upside down.
    camera_sway:         Makes the camera sway left and right.
    boo_curse:           Repeatedly reverses horizontal controls.
    im_stuck:            Holds Mario in place for three seconds.
    screen_tint:         Covers the game with a colored tint.
    retro_filter:        Adds an old-screen color and scanline effect.
    spotlight:           Darkens everything outside a small visible area.
    ground_clap:         Ground pounds damage Mario temporarily.
    head_bonk:           Hitting a block from below damages Mario temporarily.
    crazy_pixels:        Makes the game view appear pixelated.
    bonk:                Immediately damages Mario.
    timer_drain:         Removes 50 seconds from the level timer.
    coin_thief:          Removes all normal Coins.
    no_turnaround:       Temporarily locks movement to the first chosen direction.
    powerup_pickpocket:  Steals the touchscreen reserve Power-Up.
    """
    display_name = "Traps"
    valid_keys = frozenset(TRAP_ITEMS_BY_KEY)
    default = valid_keys


# =============================================================================
# 5. COSMETIC & CHARACTER CUSTOMIZATION
# =============================================================================

class PlayerPalette(Choice):
    """
    Choose a per-seed color palette for a level character model.

    vanilla:        Original character colors. (Default)
    crimson:        Vibrant red palette.
    emerald:        Rich green palette.
    sapphire:       Deep blue palette.
    purple:         Royal purple palette.
    monochrome:     Black & white grayscale palette.
    random_preset:  Single prepared palette per seed.
    crazy_random:   Wild random palette.
    pastel_rosa:    Soft pastel pink palette.
    gold:           Shining golden palette.
    silver:         Sleek silver palette.
    peach:          Princess Peach color palette.
    """

    option_vanilla = 0
    option_crimson = 1
    option_emerald = 2
    option_sapphire = 3
    option_purple = 4
    option_monochrome = 5
    option_random_preset = 6
    option_crazy_random = 7
    option_pastel_rosa = 8
    option_gold = 9
    option_silver = 10
    option_peach = 11
    default = 0


class MarioPalette(PlayerPalette):
    """Color palette used by Mario's in-level body and head models."""
    display_name = "Mario Palette"


class LuigiPalette(PlayerPalette):
    """Color palette used by Luigi's in-level body and head models."""
    display_name = "Luigi Palette"


class SecondaryScreenBackground(Choice):
    """
    Choose whether the in-level lower-screen backgrounds retain their normal
    assignments, are shuffled, or use one specific background in every level.

    vanilla:           Keep the original secondary-screen backgrounds. (Default)
    randomized:        Shuffle all five backgrounds so every assignment changes.
    white_bricks:      Use the white brick background everywhere.
    star_pattern:      Use the yellow star pattern everywhere.
    blue_bricks:       Use the dark blue brick background everywhere.
    mario_silhouette:  Use the red Mario silhouette everywhere.
    classic_overworld: Use the classic overworld scene everywhere.
    """
    display_name = "Secondary Screen Background"
    option_vanilla = 0
    option_randomized = 1
    option_white_bricks = 2
    option_star_pattern = 3
    option_blue_bricks = 4
    option_mario_silhouette = 5
    option_classic_overworld = 6
    default = 0


# =============================================================================
# 6. NSMBDS OPTIONS DATACLASS
# =============================================================================

@dataclass
class NSMBDSOptions(PerGameCommonOptions):
    # Goal & Location Checks
    goal:                                 Goal
    required_star_coins:                  RequiredStarCoins
    red_coin_checks:                      RedCoinChecks
    one_up_block_checks:                  OneUpBlockChecks
    one_up_block_item_placement:         OneUpBlockItemPlacement
    blocksanity:                          Blocksanity
    blocksanity_item_placement:           BlocksanityItemPlacement
    blocksanity_global_check_percentage:  BlocksanityGlobalCheckPercentage
    world_6_2_bonus_area:                 WorldSixTwoBonusArea
    secret_exit_checks:                   SecretExitChecks
    toad_house_checks:                    ToadHouseChecks
    secret_exit_shortcut_logic:           SecretExitShortcutLogic
    secret_exit_world_unlock_logic:       SecretExitWorldUnlockLogic
    cannon_route_logic:                    CannonRouteLogic
    advanced_location_item_placement:     AdvancedLocationItemPlacement

    # Overworld & Progression Logic
    level_randomization:                  LevelRandomization
    star_coin_gate_mode:                  StarCoinGateMode
    tower_castle_keys:                    TowerCastleKeys
    license_mini_mushroom:               LicenseMiniMushroom
    license_blue_shell:                  LicenseBlueShell
    license_mega_mushroom:               LicenseMegaMushroom
    license_mushroom:                    LicenseMushroom
    license_fire_flower:                 LicenseFireFlower
    license_touchscreen_pocket:          LicenseTouchscreenPocket

    # Filler & Trap Pools
    filler_items:                         FillerItems
    traps:                                Traps

    # Traps & Death Link
    trap_percentage:                      TrapPercentage
    bonk_trap_can_kill:                   BonkTrapCanKill
    death_link:                           DeathLink
    death_link_grace_percentage:          DeathLinkGracePercentage
    death_link_cooldown_seconds:           DeathLinkCooldownSeconds
    death_link_effect:                    DeathLinkEffect
    death_link_random_effects:            DeathLinkRandomEffects
    death_link_triggers_on_insured_death: DeathLinkTriggersOnInsuredDeath

    # Character Palettes
    mario_palette:                        MarioPalette
    luigi_palette:                        LuigiPalette
    secondary_screen_background:          SecondaryScreenBackground
