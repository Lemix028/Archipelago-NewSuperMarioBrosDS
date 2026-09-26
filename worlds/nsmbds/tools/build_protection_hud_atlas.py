"""Build the cached BizHawk HUD sprites from the original box-drawn icons.

Requires Pillow for asset generation only; the client loads the generated PNGs.
"""

from pathlib import Path

from PIL import Image, ImageDraw


TILE_WIDTH = 27
TILE_HEIGHT = 13
COUNTS_PER_ROW = 10
MAX_COUNT = 99  # notifications.is_ready rejects larger mailbox values
BLACK = (0, 0, 0, 255)
WHITE = (255, 255, 255, 255)
COLORS = ((0, 255, 255, 255), (0, 128, 0, 255))

# Five-pixel-wide digits keep both icon counters inside their original HUD slots.
DIGITS = {
    "0": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("11110", "00001", "00001", "01110", "10000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("10001", "10001", "10001", "11111", "00001", "00001", "00001"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01111", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00001", "00010", "00010", "00100", "00100"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "11110"),
}


def draw_box(draw: ImageDraw.ImageDraw, tile_x: int, tile_y: int,
             x: int, y: int, width: int, height: int, color: tuple[int, ...]) -> None:
    # The original Lua icon origin is (tile_x + 1, tile_y + 2).
    left = tile_x + 1 + x
    top = tile_y + 2 + y
    draw.rectangle((left, top, left + width - 1, top + height - 1), fill=color)


def icon_boxes(kind: int) -> tuple[tuple[int, int, int, int], ...]:
    if kind == 0:  # Trap Shield
        return ((0, 0, 9, 5), (1, 5, 7, 2), (2, 7, 5, 2), (4, 9, 1, 1))
    # Life Insurance heart
    return ((1, 0, 3, 3), (5, 0, 3, 3), (0, 2, 9, 3),
            (1, 5, 7, 2), (2, 7, 5, 2), (4, 9, 1, 1))


def draw_icon(draw: ImageDraw.ImageDraw, kind: int, tile_x: int, tile_y: int) -> None:
    boxes = icon_boxes(kind)
    for outline_x, outline_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        for x, y, width, height in boxes:
            draw_box(draw, tile_x, tile_y, x + outline_x, y + outline_y,
                     width, height, BLACK)
    for x, y, width, height in boxes:
        draw_box(draw, tile_x, tile_y, x, y, width, height, COLORS[kind])


def draw_count(image: Image.Image, count: int, tile_x: int, tile_y: int) -> None:
    pixels = []
    for digit_index, digit in enumerate(str(count)):
        for y, row in enumerate(DIGITS[digit]):
            for x, pixel in enumerate(row):
                if pixel == "1":
                    pixels.append((tile_x + 12 + digit_index * 6 + x, tile_y + 3 + y))
    for x, y in pixels:
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            image.putpixel((x + dx, y + dy), BLACK)
    for x, y in pixels:
        image.putpixel((x, y), WHITE)


def main() -> None:
    atlas = Image.new("RGBA", (TILE_WIDTH * 20, TILE_HEIGHT * 10))
    draw = ImageDraw.Draw(atlas)
    for kind in range(2):
        for count in range(1, MAX_COUNT + 1):
            index = count - 1
            tile_x = (kind * COUNTS_PER_ROW + index % COUNTS_PER_ROW) * TILE_WIDTH
            tile_y = (index // COUNTS_PER_ROW) * TILE_HEIGHT
            draw_icon(draw, kind, tile_x, tile_y)
            draw_count(atlas, count, tile_x, tile_y)

    output = Path(__file__).resolve().parents[1] / "lua_runtime" / "nsmbds" / "assets"
    output.mkdir(parents=True, exist_ok=True)
    atlas.save(output / "protection_hud_1x.png", optimize=True)
    atlas.resize((atlas.width * 2, atlas.height * 2), Image.Resampling.NEAREST).save(
        output / "protection_hud_2x.png", optimize=True)


if __name__ == "__main__":
    main()
