"""A2DE Sprite-290 flying-block placements.

All placements are from mapped playable areas. The 128-record F02 area-2 row
is the live-verified World 6-2 flying-block bonus area. Item-nibble value 3 is
the live-verified 1-Up variant.
"""

SPRITE_290_ID = 290
SPRITE_290_ACTOR_TYPE = 0x0104
SPRITE_290_ONE_UP_ITEM = 3

# source course, block-7 record offset, editor X, editor Y, actor settings
_IRREGULAR_SPRITE_290_PLACEMENTS = (
    ("E01_1", 0x018C, 191, 24, 0x00200000),
    ("F02_1", 0x0150, 49, 6, 0x00001100),
    ("F02_1", 0x015C, 56, 5, 0x00001001),
    ("F02_1", 0x0168, 64, 9, 0x00002000),
    ("F02_1", 0x01A4, 71, 53, 0x00001000),
    ("F02_1", 0x01B0, 82, 50, 0x00001001),
    ("F02_1", 0x01BC, 90, 53, 0x00001000),
    ("F02_1", 0x01C8, 50, 42, 0x00002000),
    ("F02_1", 0x01E0, 47, 40, 0x00002000),
    ("F02_1", 0x0204, 101, 52, 0x00001001),
    ("F02_1", 0x0210, 96, 51, 0x00001000),
    ("F02_1", 0x0270, 54, 41, 0x00002000),
    ("F02_1", 0x027C, 58, 42, 0x00002000),
    ("G01_1", 0x01E0, 104, 36, 0x00000103),
    ("G04_1", 0x0300, 9, 29, 0x00002000),
    ("G09_1", 0x0084, 21, 56, 0x10120001),
    ("G09_1", 0x0138, 15, 27, 0x10110004),
    ("G09_3", 0x0018, 32, 9, 0x00000000),
    ("H09_1", 0x00CC, 56, 84, 0x00000000),
)

_F02_AREA_2_ONE_UP_X = frozenset({33, 51, 67, 87, 119, 123, 151, 159})
_F02_AREA_2_SPRITE_290_PLACEMENTS = tuple(
    (
        "F02_2",
        0x0018 + (editor_x - 32) * 12,
        editor_x,
        19,
        0x00000003 if editor_x in _F02_AREA_2_ONE_UP_X else 0x00000000,
    )
    for editor_x in range(32, 160)
)

SPRITE_290_PLACEMENTS = tuple(
    sorted(
        (*_IRREGULAR_SPRITE_290_PLACEMENTS, *_F02_AREA_2_SPRITE_290_PLACEMENTS),
        key=lambda placement: (placement[0], placement[1]),
    )
)
SPRITE_290_UNVERIFIED_PLACEMENTS = ()
SPRITE_290_PLACEMENT_COUNT = 147
SPRITE_290_ONE_UP_COUNT = 9
SPRITE_290_BLOCKSANITY_COUNT = 138

if len(SPRITE_290_PLACEMENTS) != SPRITE_290_PLACEMENT_COUNT:
    raise ValueError("The active A2DE Sprite-290 catalog must contain exactly 147 placements.")
if sum(
    settings & 0x0F == SPRITE_290_ONE_UP_ITEM
    for _course, _offset, _x, _y, settings in SPRITE_290_PLACEMENTS
) != SPRITE_290_ONE_UP_COUNT:
    raise ValueError("The active A2DE Sprite-290 catalog must contain exactly nine 1-Up variants.")
