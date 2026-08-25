"""
New Super Mario Bros. DS - Item Definitions
All items that can appear in the Archipelago multiworld item pool.
"""

from BaseClasses import Item, ItemClassification

from .data.star_coin_gates import STAR_COIN_GATES

# Base ID for all NSMBDS items and locations.
BASE_ID = 0xE50000


class NSMBDSItem(Item):
    game = "New Super Mario Bros. DS"


# Item table: name -> (unique_id, classification).
ITEM_TABLE: dict[str, tuple[int, ItemClassification]] = {
    # --- Progression: World Access Passes ---
    # These unlock each world on the map.
    "Desert Pass":           (BASE_ID + 0x00, ItemClassification.progression),
    "Isle Pass":             (BASE_ID + 0x01, ItemClassification.progression),
    "Jungle Pass":           (BASE_ID + 0x02, ItemClassification.progression),
    "Glacier Pass":          (BASE_ID + 0x03, ItemClassification.progression),
    "Mountain Pass":         (BASE_ID + 0x04, ItemClassification.progression),
    "Cloud Pass":            (BASE_ID + 0x05, ItemClassification.progression),
    "Volcano Pass":          (BASE_ID + 0x06, ItemClassification.progression),

    # --- Progression: Power-Up Permits ---
    # Mini Mushroom is required to enter small pipes (leads to Worlds 4 & 7).
    # Blue Shell is needed for certain block-destroying secrets.
    "Mini Mushroom Permit":  (BASE_ID + 0x07, ItemClassification.progression),
    "Blue Shell Permit":     (BASE_ID + 0x08, ItemClassification.progression),

    "Mega Mushroom Permit":       (BASE_ID + 0x0A, ItemClassification.progression),
    "Touchscreen Pocket Permit":  (BASE_ID + 0x0B, ItemClassification.progression),
    "Mushroom Permit":            (BASE_ID + 0x0C, ItemClassification.progression),
    "Fire Flower Permit":         (BASE_ID + 0x0D, ItemClassification.progression),
    # One item is generated for every active Star Coin check. The server owns
    # the lifetime total; collecting a coin in the ROM only sends its location.
    "Star Coin":                  (BASE_ID + 0x0E, ItemClassification.progression_skip_balancing),

    # --- Useful: Power-Ups ---
    # Delivered directly to the players reserve slot in-game.
    "Mushroom":              (BASE_ID + 0x10, ItemClassification.useful),
    "Fire Flower":           (BASE_ID + 0x11, ItemClassification.useful),
    "Blue Shell":            (BASE_ID + 0x12, ItemClassification.useful),
    "Mini Mushroom":         (BASE_ID + 0x13, ItemClassification.useful),
    "Mega Mushroom":         (BASE_ID + 0x14, ItemClassification.useful),
    "Starman Buff":          (BASE_ID + 0x15, ItemClassification.useful),

    # --- Filler: Small Bonuses ---
    "1-Up Mushroom":         (BASE_ID + 0x20, ItemClassification.filler),
    "3-Up Moon":             (BASE_ID + 0x21, ItemClassification.filler),
    "Coin Bundle":           (BASE_ID + 0x22, ItemClassification.filler),
    "Nothing":               (BASE_ID + 0x23, ItemClassification.filler),
    "Time Capsule":          (BASE_ID + 0x24, ItemClassification.filler),
    "Starman Lite":          (BASE_ID + 0x25, ItemClassification.filler),
    "Trap Shield":           (BASE_ID + 0x26, ItemClassification.filler),
    "Small Care Package":    (BASE_ID + 0x27, ItemClassification.filler),
    "Life Insurance":        (BASE_ID + 0x28, ItemClassification.filler),

    # --- Traps ---
    "Time Drain":            (BASE_ID + 0x31, ItemClassification.trap),  # -50 seconds from level timer
    "Coin Thief":            (BASE_ID + 0x32, ItemClassification.trap),  # Set coins to zero
    "Super Speed":           (BASE_ID + 0x34, ItemClassification.trap),  # 1.5x max speed trap
    "Slowness":              (BASE_ID + 0x35, ItemClassification.trap),  # 0.5x max speed trap
    "Slippery Gloves":       (BASE_ID + 0x36, ItemClassification.trap),  # Disables wall jumping for 15s
    "Ground Bound":          (BASE_ID + 0x38, ItemClassification.trap),  # Suppresses configured jump inputs for 4s
    "Hyper Confusion":       (BASE_ID + 0x39, ItemClassification.trap),  # Inverts D-Pad Left/Right for 15s
    "Bonk Trap":             (BASE_ID + 0x3A, ItemClassification.trap),  # Inflicts 1 hit of damage (demotes powerup / kills small Mario)
    "No Sprint":             (BASE_ID + 0x3B, ItemClassification.trap),  # Suppresses both configured dash inputs for 15s
    "Button Swap":           (BASE_ID + 0x3C, ItemClassification.trap),  # Swaps the configured jump and dash buttons for 15s
    "Ice Shoes":             (BASE_ID + 0x3D, ItemClassification.trap),  # Reduces horizontal braking and turning grip for 15s
    "Heavy Mario":           (BASE_ID + 0x71, ItemClassification.trap),  # Adds downward acceleration for 15s
    "Can't Stop":            (BASE_ID + 0x72, ItemClassification.trap),  # Forces running while direction and jump remain controllable
    "Sticky Buttons":        (BASE_ID + 0x73, ItemClassification.trap),  # Latches released directions briefly for 15s
    "Coin Tax":              (BASE_ID + 0x74, ItemClassification.trap),  # Removes up to 10 coins immediately
    # 0x75 unused.
    "Camera Drift":          (BASE_ID + 0x76, ItemClassification.trap),  # Holds the native camera off-center
    "Screen Flip":           (BASE_ID + 0x77, ItemClassification.trap),  # Rotates both DS screens by 180 degrees
    "Drunk Camera":          (BASE_ID + 0x78, ItemClassification.trap),  # Slowly rocks the native camera left and right
    # 0x79 remains reserved for a possible future item.
    "Boo Curse":             (BASE_ID + 0x7A, ItemClassification.trap),  # Periodically reverses horizontal input
    "I'm Stuck":             (BASE_ID + 0x7B, ItemClassification.trap),  # Briefly immobilizes Mario
    "Screen Tint":           (BASE_ID + 0x7C, ItemClassification.trap),  # Applies a translucent color overlay
    "Retro Filter":          (BASE_ID + 0x7D, ItemClassification.trap),  # Adds tint and lightweight scanlines
    "Spotlight":             (BASE_ID + 0x7E, ItemClassification.trap),  # Darkens gameplay outside a central viewport
    "Ground Clap":           (BASE_ID + 0x7F, ItemClassification.trap),  # Ground pounds inflict damage for 15 seconds
    "Head Bonk":             (BASE_ID + 0x80, ItemClassification.trap),  # Hitting blocks from below inflicts damage
    "Pixelation":            (BASE_ID + 0x81, ItemClassification.trap),  # Enables the native DS Mosaic effect
    "No Turnaround Trap":    (BASE_ID + 0x82, ItemClassification.trap),  # Locks movement to the first chosen direction

    # --- Progression: Tower & Castle Keys ---
    "Grassland Tower Key":   (BASE_ID + 0x40, ItemClassification.progression),
    "Grassland Castle Key":  (BASE_ID + 0x41, ItemClassification.progression),
    "Desert Tower Key":      (BASE_ID + 0x42, ItemClassification.progression),
    "Desert Castle Key":     (BASE_ID + 0x43, ItemClassification.progression),
    "Tropical Tower Key":    (BASE_ID + 0x44, ItemClassification.progression),
    "Tropical Castle Key":   (BASE_ID + 0x45, ItemClassification.progression),
    "Jungle Tower Key":      (BASE_ID + 0x46, ItemClassification.progression),
    "Jungle Castle Key":     (BASE_ID + 0x47, ItemClassification.progression),
    "Glacier Tower Key":     (BASE_ID + 0x48, ItemClassification.progression),
    "Glacier Castle Key":    (BASE_ID + 0x49, ItemClassification.progression),
    "Mountain Tower Key":    (BASE_ID + 0x4A, ItemClassification.progression),
    "Mountain Castle Key":   (BASE_ID + 0x4B, ItemClassification.progression),
    "Sky Tower Key":         (BASE_ID + 0x4C, ItemClassification.progression),
    "Sky Castle Key":        (BASE_ID + 0x4D, ItemClassification.progression),
    "Volcano Tower Key":     (BASE_ID + 0x4E, ItemClassification.progression),
    "Volcano Castle Key":    (BASE_ID + 0x4F, ItemClassification.progression),

    # --- Progression: Star-Coin Gate Passes ---
    # The progressive item and first four individual IDs remain stable.
    "Progressive Gate Pass": (BASE_ID + 0x50, ItemClassification.progression),
}

LOCAL_BLOCKSANITY_FILLER_ITEMS: tuple[str, ...] = (
    "1-Up Mushroom",
    "3-Up Moon",
    "Coin Bundle",
    "Time Capsule",
    "Starman Lite",
    "Trap Shield",
    "Small Care Package",
    "Life Insurance",
)

# Relative selection weights for the non-progression pool. Strong protection,
# invincibility, and multi-life items stay deliberately rarer than ordinary
# Power-Ups and small resource bonuses.
FILLER_ITEM_WEIGHTS: dict[str, int] = {
    "Mushroom": 8,
    "1-Up Mushroom": 8,
    "Fire Flower": 6,
    "Coin Bundle": 6,
    "Blue Shell": 5,
    "Time Capsule": 5,
    "Starman Lite": 5,
    "Mini Mushroom": 3,
    "Mega Mushroom": 2,
    "Starman Buff": 2,
    "Trap Shield": 2,
    "Small Care Package": 2,
    "3-Up Moon": 1,
    "Life Insurance": 1,
    "Nothing": 1,
}

# Individual Gate Permit IDs follow the deterministic 32-gate catalog order.
# World-1 keeps 0x51..0x54; the additional gates occupy 0x55..0x70.
for gate_offset, gate in enumerate(STAR_COIN_GATES, start=0x51):
    ITEM_TABLE[gate.permit_item_name] = (
        BASE_ID + gate_offset,
        ItemClassification.progression,
    )

item_name_to_id: dict[str, int] = {name: data[0] for name, data in ITEM_TABLE.items()}
item_id_to_name: dict[int, str] = {item_id: name for name, item_id in item_name_to_id.items()}

KEY_ITEM_NAMES: tuple[str, ...] = (
    "Grassland Tower Key",
    "Grassland Castle Key",
    "Desert Tower Key",
    "Desert Castle Key",
    "Tropical Tower Key",
    "Tropical Castle Key",
    "Jungle Tower Key",
    "Jungle Castle Key",
    "Glacier Tower Key",
    "Glacier Castle Key",
    "Mountain Tower Key",
    "Mountain Castle Key",
    "Sky Tower Key",
    "Sky Castle Key",
    "Volcano Tower Key",
    "Volcano Castle Key",
)


def calculate_nonprogression_pool_counts(
    remaining: int,
    excluded_locations: int,
    trap_percentage: int,
    traps_enabled: bool,
) -> tuple[int, int, int]:
    """Return trap, guaranteed filler, and flexible filler/useful counts."""
    if excluded_locations > remaining:
        raise ValueError(
            f"{excluded_locations} excluded locations exceed the {remaining} "
            "non-progression item slots."
        )
    trap_count = (
        max(0, int(remaining * (trap_percentage / 100)))
        if traps_enabled
        else 0
    )
    guaranteed_filler_count = max(0, excluded_locations - trap_count)
    flexible_count = remaining - trap_count - guaranteed_filler_count
    return trap_count, guaranteed_filler_count, flexible_count


PROGRESSION_ITEM_NAMES: tuple[str, ...] = (
    "Desert Pass",
    "Isle Pass",
    "Jungle Pass",
    "Glacier Pass",
    "Mountain Pass",
    "Cloud Pass",
    "Volcano Pass",
)

USEFUL_ITEM_NAMES: tuple[str, ...] = (
    "Mushroom",
    "Fire Flower",
    "Blue Shell",
    "Mini Mushroom",
    "Mega Mushroom",
    "Starman Buff",
)

FILLER_ITEM_NAMES: tuple[str, ...] = (
    "1-Up Mushroom",
    "3-Up Moon",
    "Coin Bundle",
    "Nothing",
    "Time Capsule",
    "Starman Lite",
    "Trap Shield",
    "Small Care Package",
    "Life Insurance",
)

TRAP_ITEM_NAMES: tuple[str, ...] = (
    "Time Drain",
    "Coin Thief",
    "Bonk Trap",
    "Super Speed",
    "Slowness",
    "Slippery Gloves",
    "Ground Bound",
    "Hyper Confusion",
    "No Sprint",
    "Button Swap",
    "Ice Shoes",
    "Heavy Mario",
    "Can't Stop",
    "Sticky Buttons",
    "Coin Tax",
    "Camera Drift",
    "Screen Flip",
    "Drunk Camera",
    "Boo Curse",
    "I'm Stuck",
    "Screen Tint",
    "Retro Filter",
    "Spotlight",
    "Ground Clap",
    "Head Bonk",
    "Pixelation",
    "No Turnaround Trap",
)

GENERATABLE_TRAP_ITEM_NAMES: tuple[str, ...] = (
    "Time Drain",
    "Coin Thief",
    "Super Speed",
    "Slowness",
    "Slippery Gloves",
    "Ground Bound",
    "Hyper Confusion",
    "Bonk Trap",
    "No Sprint",
    "Button Swap",
    "Ice Shoes",
    "Heavy Mario",
    "Can't Stop",
    "Sticky Buttons",
    "Coin Tax",
    "Camera Drift",
    "Screen Flip",
    "Drunk Camera",
    "Boo Curse",
    "I'm Stuck",
    "Screen Tint",
    "Retro Filter",
    "Spotlight",
    "Ground Clap",
    "Head Bonk",
    "Pixelation",
    "No Turnaround Trap",
)

# Inventory item RAM values (written to the inventory slot)
# Maps item name -> byte value for ADDR_INVENTORY_ITEM
INVENTORY_RAM_VALUES: dict[str, int] = {
    "Mushroom":      0x01,
    "Fire Flower":   0x02,
    "Blue Shell":    0x03,
    "Mini Mushroom": 0x04,
    "Mega Mushroom": 0x05,
}
