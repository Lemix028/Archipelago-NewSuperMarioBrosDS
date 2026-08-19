"""
New Super Mario Bros. DS - YAML Options
Player-facing settings exposed in the Archipelago YAML configuration file.
"""

from dataclasses import dataclass

from Options import Choice, DeathLink, PerGameCommonOptions, Range, Toggle

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
    world_tour:      Defeat all 8 Castle boss goals across Worlds 1 through 8.
    completionist:   Defeat Bowser AND collect all required Star Coins.
    """
    display_name = "Goal"
    option_defeat_bowser  = 0
    option_star_coin_hunt = 1
    option_world_tour     = 2
    option_completionist  = 3
    default = 0


class RequiredStarCoins(Range):
    """
    (Relevant for 'Star Coin Hunt' and 'Completionist' goals.)
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
    default = 1


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
    """Include verified static and flying Coin/Power-up Blocks as Archipelago checks."""
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
    default = 1


class SecretExitChecks(Toggle):
    """Include the 18 Secret Exit locations across the world map in the check pool."""
    display_name = "Secret Exit Checks"
    default = 1


class ToadHouseChecks(Toggle):
    """Include Toad House locations on the world map as check locations."""
    display_name = "Toad House Checks"
    default = 1


# =============================================================================
# 2. OVERWORLD & PROGRESSION LOGIC OPTIONS
# =============================================================================

class StarCoinGateMode(Choice):
    """
    Controls Star-Coin signs on the overworld map.

    vanilla:     Original Star-Coin purchase behavior.
    progressive: Each received Progressive Star Coin Gate Pass authorizes the
                 next gate in the deterministic 32-gate catalog.
    individual:  Each Star Coin Gate requires its own named Gate Pass.
    """
    display_name = "Star Coin Gate Mode"
    option_vanilla = 0
    option_progressive = 1
    option_individual = 2
    default = 0


class TowerCastleKeys(Toggle):
    """
    Include physical Tower Keys and Castle Keys in the item pool.
    When enabled, players must find key items to unlock path gates leading to Towers and Castles.
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
    default = 1


class LicenseFireFlower(Toggle):
    """Include Fire Flower Permit in the item pool and logic."""
    display_name = "License: Fire Flower"
    default = 1


class LicenseTouchscreenPocket(Toggle):
    """Include Touchscreen Pocket Permit (reserve item storage) in the item pool and logic.
       If enabled, players cannot use the Touchscreen Pocket until they find the Permit item in the multiworld."""
    display_name = "License: Touchscreen Pocket"
    default = 1


# =============================================================================
# 3. FILLER ITEM OPTIONS
# =============================================================================

class FillerPowerups(Toggle):
    """Include standard power-ups (Super Mushroom, Fire Flower, Blue Shell, Mini Mushroom, Mega Mushroom) in filler item pool."""
    display_name = "Filler: Power-Ups"
    default = 1


class FillerStarman(Toggle):
    """Include full Starman invincibility bonuses in the filler item pool."""
    display_name = "Filler: Starman"
    default = 1


class FillerExtraLives(Toggle):
    """Include 1-Up Mushrooms and 3-Up Moons in the filler item pool."""
    display_name = "Filler: Extra Lives"
    default = 1


class FillerCoins(Toggle):
    """Include 50-Coin Bundles in the filler item pool."""
    display_name = "Filler: Coins"
    default = 1


class FillerTimeCapsule(Toggle):
    """Include Time Capsules (+30 level seconds) in the filler pool."""
    display_name = "Filler: Time Capsule"
    default = 1


class FillerStarmanLite(Toggle):
    """Include five-second Starman Lite bonuses in the filler pool."""
    display_name = "Filler: Starman Lite"
    default = 1


class FillerTrapShield(Toggle):
    """Include shields that cancel the next received AP trap."""
    display_name = "Filler: Trap Shield"
    default = 1


class FillerCarePackage(Toggle):
    """Include small packages that grant time, coins, and one life together."""
    display_name = "Filler: Small Care Package"
    default = 1


class FillerLifeInsurance(Toggle):
    """Include charges that prevent the next death from consuming a life."""
    display_name = "Filler: Life Insurance"
    default = 1


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
    default     = 20


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


# Individual Trap Toggles
class TrapHyperSpeed(Toggle):
    """Enable Super Speed traps (speeds up Mario's movement by +60% for 15s)."""
    display_name = "Trap: Super Speed"
    default = 1


class TrapSlowSpeed(Toggle):
    """Enable Slowness traps (reduces Mario's movement by -50% for 15s)."""
    display_name = "Trap: Slowness"
    default = 1


class TrapWalljumpLock(Toggle):
    """Enable Slippery Gloves traps (disables wall-jumping mechanics for 15s)."""
    display_name = "Trap: Slippery Gloves"
    default = 1


class TrapNoJump(Toggle):
    """Enable Ground Bound traps (disables jumping input for 15s)."""
    display_name = "Trap: Ground Bound"
    default = 1


class TrapReverseControls(Toggle):
    """Enable Hyper Confusion traps (inverts left and right movement for 15s)."""
    display_name = "Trap: Hyper Confusion"
    default = 1


class TrapNoSprint(Toggle):
    """Enable No Sprint traps (disables both configured dash buttons for 15s)."""
    display_name = "Trap: No Sprint"
    default = 1


class TrapButtonRoulette(Toggle):
    """Enable Button Swap traps (swaps configured jump and dash buttons for 15s)."""
    display_name = "Trap: Button Swap"
    default = 1


class TrapIceShoes(Toggle):
    """Enable Ice Shoes traps (reduces horizontal braking and turning grip for 15s)."""
    display_name = "Trap: Ice Shoes"
    default = 1


class TrapHeavyMario(Toggle):
    """Enable Heavy Mario traps (lowers jumps and accelerates falling for 15s)."""
    display_name = "Trap: Heavy Mario"
    default = 1


class TrapAutoRun(Toggle):
    """Enable Can't Stop traps (forces running while direction and jump remain controllable for 15s)."""
    display_name = "Trap: Can't Stop"
    default = 1


class TrapStickyButtons(Toggle):
    """Enable Sticky Buttons traps (briefly latches released directions for 15s)."""
    display_name = "Trap: Sticky Buttons"
    default = 1


class TrapCoinTax(Toggle):
    """Enable Coin Tax traps (removes up to 10 coins immediately)."""
    display_name = "Trap: Coin Tax"
    default = 1


class TrapCameraDrift(Toggle):
    """Enable native camera drift to one side for 15 seconds."""
    display_name = "Trap: Camera Drift"
    default = 1


class TrapScreenFlip(Toggle):
    """Enable a reversible 180-degree DS screen rotation for 15 seconds."""
    display_name = "Trap: Screen Flip"
    default = 1


class TrapCameraSway(Toggle):
    """Enable Drunk Camera traps (slow native camera swaying for 15 seconds)."""
    display_name = "Trap: Drunk Camera"
    default = 1


class TrapBooCurse(Toggle):
    """Enable periodic horizontal control reversal for 15 seconds."""
    display_name = "Trap: Boo Curse"
    default = 1


class TrapImStuck(Toggle):
    """Enable three-second I'm Stuck traps that immobilize Mario."""
    display_name = "Trap: I'm Stuck"
    default = 1


class TrapScreenTint(Toggle):
    """Enable translucent color overlays for 15 seconds."""
    display_name = "Trap: Screen Tint"
    default = 1


class TrapRetroFilter(Toggle):
    """Enable a lightweight tint and scanline filter for 15 seconds."""
    display_name = "Trap: Retro Filter"
    default = 1


class TrapSpotlight(Toggle):
    """Enable a darkened gameplay view with a central spotlight for 10 seconds."""
    display_name = "Trap: Spotlight"
    default = 1


class TrapGroundClap(Toggle):
    """Enable damage when Mario performs a ground-pound impact for 15 seconds."""
    display_name = "Trap: Ground Clap"
    default = 1


class TrapHeadBonk(Toggle):
    """Enable damage when Mario hits a block from below for 15 seconds."""
    display_name = "Trap: Head Bonk"
    default = 1


class TrapCrazyPixels(Toggle):
    """Enable Pixelation traps (native DS hardware Mosaic effect for 15 seconds)."""
    display_name = "Trap: Pixelation"
    default = 1


class TrapBonk(Toggle):
    """Enable Bonk Trap traps (inflicts a damage hit on Mario)."""
    display_name = "Trap: Bonk Trap"
    default = 1


class TrapTimerDrain(Toggle):
    """Enable Time Drain traps (subtracts 50s from level timer)."""
    display_name = "Trap: Time Drain"
    default = 1


class TrapCoinThief(Toggle):
    """Enable Coin Thief traps (empties Mario's coins to 0)."""
    display_name = "Trap: Coin Thief"
    default = 1


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

    # Overworld & Progression Logic
    star_coin_gate_mode:                  StarCoinGateMode
    tower_castle_keys:                    TowerCastleKeys
    license_mini_mushroom:               LicenseMiniMushroom
    license_blue_shell:                  LicenseBlueShell
    license_mega_mushroom:               LicenseMegaMushroom
    license_mushroom:                    LicenseMushroom
    license_fire_flower:                 LicenseFireFlower
    license_touchscreen_pocket:          LicenseTouchscreenPocket

    # Filler Item Categories
    filler_powerups:                      FillerPowerups
    filler_starman:                       FillerStarman
    filler_extra_lives:                   FillerExtraLives
    filler_coins:                         FillerCoins
    filler_time_capsule:                  FillerTimeCapsule
    filler_starman_lite:                  FillerStarmanLite
    filler_trap_shield:                   FillerTrapShield
    filler_care_package:                  FillerCarePackage
    filler_life_insurance:                FillerLifeInsurance

    # Traps & Death Link
    trap_percentage:                      TrapPercentage
    bonk_trap_can_kill:                   BonkTrapCanKill
    death_link:                           DeathLink
    death_link_triggers_on_insured_death: DeathLinkTriggersOnInsuredDeath

    # Individual Trap Toggles
    trap_hyper_speed:                     TrapHyperSpeed
    trap_slow_speed:                      TrapSlowSpeed
    trap_walljump_lock:                   TrapWalljumpLock
    trap_no_jump:                         TrapNoJump
    trap_reverse_controls:                TrapReverseControls
    trap_no_sprint:                       TrapNoSprint
    trap_button_roulette:                 TrapButtonRoulette
    trap_ice_shoes:                       TrapIceShoes
    trap_heavy_mario:                     TrapHeavyMario
    trap_auto_run:                        TrapAutoRun
    trap_sticky_buttons:                  TrapStickyButtons
    trap_coin_tax:                        TrapCoinTax
    trap_camera_drift:                    TrapCameraDrift
    trap_screen_flip:                     TrapScreenFlip
    trap_camera_sway:                     TrapCameraSway
    trap_boo_curse:                       TrapBooCurse
    trap_im_stuck:                        TrapImStuck
    trap_screen_tint:                     TrapScreenTint
    trap_retro_filter:                    TrapRetroFilter
    trap_spotlight:                       TrapSpotlight
    trap_ground_clap:                     TrapGroundClap
    trap_head_bonk:                       TrapHeadBonk
    trap_crazy_pixels:                    TrapCrazyPixels
    trap_bonk:                            TrapBonk
    trap_timer_drain:                     TrapTimerDrain
    trap_coin_thief:                      TrapCoinThief

    # Character Palettes
    mario_palette:                        MarioPalette
    luigi_palette:                        LuigiPalette
