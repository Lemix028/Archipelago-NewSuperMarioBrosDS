"""
New Super Mario Bros. DS - RAM Address Constants
Central reference for all verified memory addresses.

All addresses are expressed as 0-indexed offsets inside the 4MB "Main RAM" domain
"""

# BizHawk memory domain name for Nintendo DS games.
# "Main RAM" (4 MB) is supported natively across melonDS and DeSmuME cores in BizHawk.
MEMORY_DOMAIN = "Main RAM"

# ---------------------------------------------------------------------------
# Player State Addresses
# ---------------------------------------------------------------------------

# Current power-up state when on the world map or entering a level.
# Values: 0x00=Small, 0x01=Big/Mushroom, 0x02=Fire, 0x04=Mini, 0x05=Blue Shell
ADDR_POWERUP_MAP = 0x0008B324  # 1 byte

# Current power-up state while inside a level (live, plays transform animation).
# Writing here changes Mario's appearance immediately.
ADDR_POWERUP_LEVEL = 0x001B7187  # 1 byte

# Inventory item held in the inventory slot.
# Values: 0x00=None, 0x01=Mushroom, 0x02=Fire, 0x03=Shell, 0x04=Mini, 0x05=Mega
ADDR_INVENTORY_ITEM = 0x0008B32C  # 1 byte

# Number of lives remaining (0-99).
ADDR_LIVES = 0x0008B364  # 1 byte

# Number of coins collected (0-99).
ADDR_COINS = 0x0008B37C  # 1 byte

# Remaining level time as a 32-bit fixed-point countdown. One visible second
# equals 4096 units. Writing zero starts the native "Time Up" death sequence.
ADDR_TIMER = 0x000CA8B4  # 4 bytes, uint32_le
TIMER_UNITS_PER_SECOND = 4096

# Red Coin Challenge counter. It increments from 0 through 8 while a
# Red Coin Ring is active, then immediately resets to 0 on success or timeout.
ADDR_RED_COIN_COUNTER = 0x000CA2D4  # 1 byte, uint8

# Starman invincibility timer. Writing a frame count (e.g. 900 = 15 seconds)
# activates native Starman invincibility.
ADDR_STARMAN_TIMER = 0x0008B350  # 4 bytes, uint32_le
STARMAN_DURATION_FRAMES = 900

# Mario horizontal speed and max speed vector (4 bytes each, int32_le / 20.12 fixed point).
# Manipulated temporarily by Hyper Speed Trap and Slow Speed Trap inside a level.
ADDR_X_SPEED = 0x001B6A90          # 4 bytes, int32_le
ADDR_MARIO_MAX_SPEED = 0x001B6A94  # 4 bytes, int32_le
HYPER_SPEED_MULTIPLIER = 1.6
SLOW_SPEED_MULTIPLIER = 0.5
SPEED_TRAP_DURATION_SECONDS = 15.0
# Mario wall jump action timers (1 byte each, uint8). Zeroed by Walljump Lock Trap.
ADDR_WALLJUMP_TIMER = 0x001B759B   # 1 byte, uint8
ADDR_LEFT_WALL_TIMER = 0x001B7597  # 1 byte, uint8
ADDR_RIGHT_WALL_TIMER = 0x001B7598 # 1 byte, uint8

# 1-byte AP trap trigger address read by the bundled BizHawk Lua runtime.
# 0x00 = Idle; 0x01..0x16 are the verified Lua-side Trap commands.
# 0x12 is retired; Camera Drift/Screen Flip/Sway use 0x13..0x15; Boo Curse uses 0x16.
ADDR_AP_TRAP_TRIGGER = 0x003FFF00  # 1 byte, uint8

# Persistent positive-filler state lives in verified permanent ARM9 padding
# after the two live-tested Power-Up License bytes. The next native code starts
# at system address 0x02003000, leaving 0x02002FEA..0x02002FFF available.
ADDR_AP_TRAP_SHIELD_COUNT = 0x00002FEA       # system 0x02002FEA, 1 byte
ADDR_AP_LIFE_INSURANCE_COUNT = 0x00002FEB    # system 0x02002FEB, 1 byte
ADDR_AP_INSURED_DEATH_SEQUENCE = 0x00002FEC  # system 0x02002FEC, 1 byte

# Protection HUD readiness and the client-to-Lua notification mailbox. Two
# magic bytes prevent uninitialized high-RAM contents from appearing as valid
# shield or insurance charges before the AP client initializes this session.
ADDR_AP_BONUS_STATE_MAGIC_1 = 0x00002FED
ADDR_AP_BONUS_STATE_MAGIC_2 = 0x00002FEE
AP_BONUS_STATE_MAGIC_1 = 0x4E  # "N"
AP_BONUS_STATE_MAGIC_2 = 0x53  # "S"
ADDR_AP_NOTIFICATION_SEQUENCE = 0x00002FEF
ADDR_AP_NOTIFICATION_TYPE = 0x00002FF0
ADDR_AP_NOTIFICATION_DETAIL = 0x00002FF1
ADDR_AP_NOTIFICATION_ACK_SEQUENCE = 0x00002FF2

AP_NOTIFICATION_TIME_CAPSULE = 0x01
AP_NOTIFICATION_STARMAN_LITE = 0x02
AP_NOTIFICATION_TRAP_SHIELD = 0x03
AP_NOTIFICATION_CARE_PACKAGE = 0x04
AP_NOTIFICATION_LIFE_INSURANCE = 0x05
AP_NOTIFICATION_TRAP_BLOCKED = 0x06
AP_NOTIFICATION_STARMAN_BUFF = 0x07
AP_NOTIFICATION_GOAL_COMPLETE = 0x08
AP_NOTIFICATION_ITEM_RECEIVED = 0x09

# Power-Up License state read by the native main-ARM9 pickup/reserve hooks. These
# bytes are reserved directly after the hook binary in verified linker padding.
# Bits: 0=Mini, 1=Blue Shell, 2=Mega, 3=Reserve, 4=Mushroom, 5=Fire.
ADDR_AP_POWERUP_LICENSE_MODE = 0x00002FE8  # system 0x02002FE8, 1 byte
ADDR_AP_POWERUP_LICENSE_MASK = 0x00002FE9  # system 0x02002FE9, 1 byte

# Red Coin completion mailbox shared by the 60 Hz Lua hook and the Python
# client. Lua writes the payload first and the sequence byte last; Python
# acknowledges the processed sequence only after it has submitted or safely
# discarded that event. These bytes are separate from the trap
# trigger at 0x003FFF00.
ADDR_AP_RED_COIN_EVENT_SEQUENCE = 0x003FFF04  # 1 byte, uint8
ADDR_AP_RED_COIN_EVENT_TYPE = 0x003FFF05      # 1 byte, uint8
ADDR_AP_RED_COIN_EVENT_WORLD = 0x003FFF08     # 4 bytes, uint32_le
ADDR_AP_RED_COIN_EVENT_LEVEL = 0x003FFF0C     # 4 bytes, uint32_le
ADDR_AP_RED_COIN_EVENT_ACK_SEQUENCE = 0x003FFF10  # 1 byte, uint8
ADDR_AP_RED_COIN_EVENT_AREA = 0x003FFF14      # 4 bytes, uint32_le
ADDR_AP_RED_COIN_EVENT_PLAYER_X = 0x003FFF18  # 4 bytes, int32_le
ADDR_AP_RED_COIN_EVENT_COUNTER = 0x003FFF1C   # 1 byte, uint8 (Lua index 1..2)
AP_EVENT_TYPE_RED_COIN_COMPLETE = 0x10

# Shared mailbox for 1-Up and Blocksanity block checks. The Lua-side software
# queue retains rapid hits until this single safe, previously live-tested slot
# has been acknowledged by Python.
ADDR_AP_BLOCK_EVENT_SEQUENCE = 0x003FFF20  # 1 byte, uint8
ADDR_AP_BLOCK_EVENT_TYPE = 0x003FFF21      # 1 byte, uint8
ADDR_AP_BLOCK_EVENT_WORLD = 0x003FFF24     # 4 bytes, uint32_le
ADDR_AP_BLOCK_EVENT_LEVEL = 0x003FFF28     # 4 bytes, uint32_le
ADDR_AP_BLOCK_EVENT_AREA = 0x003FFF2C      # 4 bytes, uint32_le
ADDR_AP_BLOCK_EVENT_TILE_X = 0x003FFF30    # 4 bytes, int32_le
ADDR_AP_BLOCK_EVENT_TILE_Y = 0x003FFF34    # 4 bytes, int32_le
ADDR_AP_BLOCK_EVENT_ACK_SEQUENCE = 0x003FFF38  # 1 byte, uint8

AP_EVENT_TYPE_BLOCK_BUMP = 0x11
AP_EVENT_TYPE_BLOCK_GROUND_POUND = 0x12
AP_EVENT_TYPE_MOVING_BLOCK_OPEN = 0x13

# Live Mini Mario Castle Secret Exit completion flags (written by Lua, read by Python client in level_data offset 0x2F4)
ADDR_AP_MINI_CASTLE_FLAGS = 0x00088F40  # system 0x02088F40, 1 byte, uint8
ADDR_AP_MINI_CASTLE_FLAGS_PERM = 0x00002FF3  # system 0x02002FF3, 1 byte, uint8
AP_MINI_CASTLE_W2_BIT = 0x01
AP_MINI_CASTLE_W5_BIT = 0x02

# ROM-hook mailbox for the Star-Coin Gate Permit mode.
# Eight bytes, one per world; each bit authorizes one gate in that world's
# deterministic STAR_COIN_GATES order.
# This mailbox lives inside Overlay 8 (system 0x020CC2E0..0x020EFFFF).
# Only write it when Overlay 8 is confirmed loaded in RAM (i.e. when the
# HOOK_CAVE first word matches the patched STAR_COIN_GATE_HOOK_BYTES[0:4]).
ADDR_AP_STAR_COIN_GATE_PERMIT_MASK = 0x000EE100  # system 0x020EE100
AP_STAR_COIN_GATE_PERMIT_MASK_SIZE = 8

# AP Star-Coin currency mailbox consumed by the native ROM hook. The four-byte
# magic is present only in Star-Coin-item seeds; the uint32 value is available.
ADDR_AP_STAR_COIN_CURRENCY_MAILBOX = 0x000EE108  # system 0x020EE108, 8 bytes
AP_STAR_COIN_CURRENCY_MAGIC = b"APSC"

# Do not write system address 0x02088BDC directly. It is the base of the
# vanilla Star-Coin state structure; the getter reads fields at +0x18/+0x1C.
# AP currency is supplied exclusively through the mailbox above.

# Guard: first 4 bytes of the hook cave - present only when Overlay 8 is loaded.
# HOOK_CAVE = 0x020EDFC4 -> Main RAM offset 0x000EDFC4
ADDR_AP_STAR_COIN_GATE_HOOK_MARKER = 0x000EDFC4
AP_STAR_COIN_GATE_HOOK_MARKER = bytes.fromhex("10002de9")  # STAR_COIN_GATE_HOOK_BYTES[0:4]

# ---------------------------------------------------------------------------
# World Unlock Flags
# ---------------------------------------------------------------------------

# Base address of the world unlock flag array.
# Layout: 2 bytes per world, 8 worlds consecutively.
#   +0x00 = World 1, +0x02 = World 2, ..., +0x0E = World 8
# Write 0x0043 to the 2-byte slot to unlock the corresponding world.
ADDR_WORLD_FLAGS_BASE = 0x00088C3C  # 16 bytes total
WORLD_ENABLED_VALUE = 0x0043         # Value to write to enable a world

# World 8-Tower 2 -> World 8-Bowser's Castle overworld connection. Clearing both bits
# blocks the route; setting them opens it. This is used only for the
# Completionist Bowser gate.
ADDR_W8_CASTLE_APPROACH_PATH = 0x00088DF1  # 1 byte
W8_CASTLE_APPROACH_PATH_MASK = 0xC0


# ---------------------------------------------------------------------------
# Level Completion & Star Coin Flags
# ---------------------------------------------------------------------------

# Base address of the level data block.
# Contains completion status, star coins, and secret exit flags for every level.
# The eight world records occupy 0xC8 bytes (200 bytes), including headers.
# Layout: 25 bytes per world: one header byte followed by up to 24 level slots.
# Some original tools only scanned the first 0xC0 bytes. World 8 map rewards
# use offsets through 192, so the complete record span is 0xC8 bytes.
# Status flags:
#       Bit 0 (0x01): Star Coin 1 collected
#       Bit 1 (0x02): Star Coin 2 collected
#       Bit 2 (0x04): Star Coin 3 collected
#       Bit 4 (0x10): Level Completed (Normal exit / Flag pole)
#       Bit 6 (0x40): Set for ALL completed levels (not secret exit)
#       Bit 7 (0x80): Level node appears on world map (level unlocked)
ADDR_LEVEL_DATA_BASE = 0x00088C4C

# The client also reads adjacent persistent world-map flags used by active
# Secret Exit checks (e.g. 0x02088F39 at offset 0x2ED).
LEVEL_AND_SECRET_FLAG_READ_SIZE = 0x300

FLAG_STAR_COIN_1    = 0x01  # Bit 0: Star Coin 1 collected
FLAG_STAR_COIN_2    = 0x02  # Bit 1: Star Coin 2 collected
FLAG_STAR_COIN_3    = 0x04  # Bit 2: Star Coin 3 collected
FLAG_LEVEL_COMPLETE = 0x10  # Bit 4: Normal exit reached
FLAG_ALWAYS_ON_DONE = 0x40  # Bit 6: Set whenever level completed
FLAG_NODE_ACTIVE    = 0x80  # Bit 7: Level node shown on world map

# Reference value for Action Replay "all coins + completed" code
ACTION_REPLAY_FULL_BYTE = 0xD7

# ---------------------------------------------------------------------------
# Game State
# ---------------------------------------------------------------------------

# Runtime course identity. The pair (world, level) identifies the active
# course. The current area can change inside a course and must not be used as its AP key.
# Values are uint32_le and world indices are zero-based (World 1 = 0).
# Stable selected-world byte retained while its course is running.
ADDR_CURRENT_COURSE_WORLD = 0x00088BFC  # 1 byte, uint8
ADDR_CURRENT_COURSE_LEVEL = 0x00085A9C  # 1 byte, uint8
ADDR_CURRENT_COURSE_AREA = 0x00085A94   # 1 byte, uint8


# ---------------------------------------------------------------------------
# Expected ROM identification
# ---------------------------------------------------------------------------

# NDS ROM header game code for the verified NSMB DS USA ROM.
# The header is read from BizHawk's ROM memory domain, not assumed to be mirrored in RAM.
ROM_GAME_CODE = b"A2DE"
ROM_GAME_CODE_ADDRESS = 0x0000000C
ROM_GAME_CODE_SIZE = 4
ROM_MEMORY_DOMAIN = "ROM"

# BizHawk's melonDS core exposes the cartridge header under different domain
# names depending on core/version. Try the flat ROM domains first, then the
# ARM9/System Bus cartridge mapping at 0x08000000.
ROM_GAME_CODE_LOCATIONS = (
    (ROM_GAME_CODE_ADDRESS, "ROM"),
    (ROM_GAME_CODE_ADDRESS, "CART ROM"),
    (0x0800000C, "ARM9 System Bus"),
    (0x0800000C, "System Bus"),
)

# Client readiness guard: Worlds 2-7 begin with a 0xD* header state, but a
# progressed world can switch to a small state ID such as 0x02. Accept both
# observed forms and guard writes with the exact live values. World 8 uses a
# different mutable header and is intentionally excluded.
LEVEL_DATA_WORLD_HEADER_OFFSETS = tuple(range(25, 175, 25))
LEVEL_DATA_WORLD_HEADER_VALUE = 0xD0
LEVEL_DATA_WORLD_HEADER_MASK = 0xF0
LEVEL_DATA_WORLD_HEADER_MAX_STATE = 0x0F

# ---------------------------------------------------------------------------
# Overworld path bytes owned by Tower & Castle Keys.
#
# Tower Keys only control paths leading into a Tower.  Paths leaving a Tower
# must remain vanilla-owned so completing the stage can open them normally.
# Worlds 6 and 8 intentionally have two Tower entries because they contain two
# separate Towers; both addresses are entrance paths, not post-Tower exits.
# ---------------------------------------------------------------------------

KEY_PATH_GATE_ADDRESSES: dict[str, tuple[int, ...]] = {
    "Grassland Tower Key":  (0x00088D18,),
    "Grassland Castle Key": (0x00088D1D,),
    "Desert Tower Key":     (0x00088D36,),
    "Desert Castle Key":    (0x00088D3B, 0x00088D45),
    "Tropical Tower Key":   (0x00088D54,),
    "Tropical Castle Key":  (0x00088D59,),
    "Jungle Tower Key":     (0x00088D71,),
    "Jungle Castle Key":    (0x00088D78,),
    "Glacier Tower Key":    (0x00088D90,),
    "Glacier Castle Key":   (0x00088D96, 0x00088DA4),
    "Mountain Tower Key":   (0x00088DAE, 0x00088DB1),
    "Mountain Castle Key":  (0x00088DB5,),
    "Sky Tower Key":        (0x00088DCC,),
    "Sky Castle Key":       (0x00088DD1,),
    "Volcano Tower Key":    (0x00088DE8, 0x00088DF0),
    "Volcano Castle Key":   (0x00088DEB,),
}
