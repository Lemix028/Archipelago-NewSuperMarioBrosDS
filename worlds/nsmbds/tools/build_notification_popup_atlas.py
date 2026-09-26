"""Build cached notification cards for BizHawk's in-game popup.

The existing Lua text tables provide the variable item, trap, and DeathLink
labels. Pillow is only needed while rebuilding assets, never at game runtime.
"""

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "lua_runtime" / "nsmbds"
ASSETS = RUNTIME / "assets"
HUD_SOURCE = RUNTIME / "hud.lua"
COLUMNS = 6
COLORS = {
    "cyan": (68, 222, 240, 255),
    "green": (74, 215, 139, 255),
    "yellow": (255, 211, 92, 255),
    "red": (255, 105, 113, 255),
}
BLACK = (0, 0, 0, 255)
WHITE = (245, 248, 255, 255)
BACKGROUND = (17, 20, 31, 222)
GRAY = (85, 96, 113, 255)


def lua_map(source: str, marker: str) -> dict[int, str]:
    section = re.split(r"\n\s*}", source.split(marker, 1)[1], maxsplit=1)[0]
    return {
        int(number, 0): label
        for number, label in re.findall(r'\[(0x[\da-fA-F]+|\d+)\]\s*=\s*"([^"]+)"', section)
    }


def descriptions(source: str) -> list[tuple[str, str, str]]:
    items = lua_map(source, "local RECEIVED_ITEM_NAMES = {")
    blocked = lua_map(source, "local blocked_names = {")
    deathlink = lua_map(source, "local death_link_names = {")
    cards = [
        ("TIME CAPSULE", "+30 SEC", "cyan"),
        ("STARMAN LITE", "+5 SEC INVINCIBLE", "yellow"),
        ("TRAP SHIELD", "+1 CHARGE", "cyan"),
        ("SMALL CARE PACKAGE", "+15 SEC +5 COINS +1 LIFE", "green"),
        ("LIFE INSURANCE", "+1 CHARGE", "green"),
        ("STARMAN BUFF", "+15 SEC INVINCIBLE", "yellow"),
        ("GOAL COMPLETE!", "CONGRATULATIONS!", "green"),
        ("SMALL COIN BUNDLE", "+10 COINS", "green"),
        ("COIN BUNDLE", "+25 COINS", "green"),
        ("LARGE COIN BUNDLE", "+50 COINS", "green"),
        ("ITEM RECEIVED", "STAR COIN GATE PASS", "green"),
        ("ITEM RECEIVED", "PROGRESSION ITEM", "green"),
        ("BONUS RECEIVED", "", "green"),
        ("TRAP BLOCKED", "SHIELD CONSUMED", "cyan"),
        ("DEATH LINK", "DEATH", "red"),
    ]
    cards.extend(("ITEM RECEIVED", name, "green") for key, name in items.items()
                 if key not in (0x22, 0x29, 0x2A))
    cards.extend(("TRAP BLOCKED", name, "cyan") for name in blocked.values())
    cards.extend(("DEATH LINK", name, "green" if key == 4 else "red")
                 for key, name in deathlink.items())
    # Drop repeated descriptions while keeping stable sprite indices.
    return list(dict.fromkeys(cards))


@lru_cache(maxsize=None)
def font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    # Rendered glyphs are bundled as PNGs; no font is needed at game runtime.
    windows_font = "segoeuib.ttf" if bold else "segoeui.ttf"
    for name in (f"C:/Windows/Fonts/{windows_font}", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def draw_fitting_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int],
                      text: str, color: tuple[int, ...], size: int,
                      available_width: int, raster_scale: int,
                      bold: bool = False) -> None:
    pixel_size = size * raster_scale
    while pixel_size > 7 * raster_scale and draw.textlength(
            text, font=font(pixel_size, bold)) > available_width * raster_scale:
        pixel_size -= raster_scale
    draw.text((xy[0] * raster_scale, xy[1] * raster_scale),
              text, font=font(pixel_size, bold), fill=color)


def build_layout(cards: list[tuple[str, str, str]], name: str,
                 scale: float, title_size: int, subtitle_size: int,
                 output_scale: int = 1) -> None:
    native_width = math.floor(145 * scale + 0.5)
    native_height = math.floor(30 * scale + 0.5)
    width = native_width * output_scale
    height = native_height * output_scale
    rows = math.ceil(len(cards) / COLUMNS)
    atlas = Image.new("RGBA", (COLUMNS * width, rows * height))
    accent_width = max(3, math.floor(3 * scale + 0.5))
    text_x = math.floor(7 * scale)
    # Horizontal keeps the normal title size, so it needs the same row spacing.
    subtitle_y = 12 if name == "horizontal" else math.floor(12 * scale)
    bar_x1 = math.floor(4 * scale)
    bar_x2 = native_width - 1 - math.floor(3 * scale)
    bar_y = native_height - 1 - math.floor(3 * scale)

    for index, (title, subtitle, color_name) in enumerate(cards):
        x = index % COLUMNS * width
        y = index // COLUMNS * height
        color = COLORS[color_name]
        card = Image.new("RGBA", (width, height))
        card_draw = ImageDraw.Draw(card)
        card_draw.rectangle((0, 0, width - 1, height - 1), fill=BACKGROUND)
        card_draw.rectangle((0, 0, width - 1, output_scale - 1), fill=BLACK)
        card_draw.rectangle((0, height - output_scale, width - 1, height - 1), fill=BLACK)
        card_draw.rectangle((0, 0, output_scale - 1, height - 1), fill=BLACK)
        card_draw.rectangle((width - output_scale, 0, width - 1, height - 1), fill=BLACK)
        card_draw.rectangle((0, 0, accent_width * output_scale - 1, height - 1),
                            fill=color)
        raster_scale = max(2, output_scale)
        text_layer = Image.new("RGBA", (native_width * raster_scale,
                                        native_height * raster_scale))
        text_draw = ImageDraw.Draw(text_layer)
        draw_fitting_text(text_draw, (text_x, math.floor(2 * scale)),
                          title, WHITE, title_size, native_width - text_x - 3,
                          raster_scale, bold=True)
        draw_fitting_text(text_draw, (text_x, subtitle_y),
                          subtitle, color, subtitle_size, native_width - text_x - 3,
                          raster_scale)
        if raster_scale != output_scale:
            text_layer = text_layer.resize((width, height), Image.Resampling.BOX)
        card.alpha_composite(text_layer)
        card_draw.rectangle((bar_x1 * output_scale, bar_y * output_scale,
                             (bar_x2 + 1) * output_scale - 1,
                             (bar_y + 1) * output_scale - 1), fill=GRAY)
        atlas.alpha_composite(card, (x, y))

    suffix = f"_{output_scale}x" if output_scale > 1 else ""
    atlas.save(ASSETS / f"notification_popup_{name}{suffix}.png", optimize=True)


def main() -> None:
    cards = descriptions(HUD_SOURCE.read_text(encoding="utf-8"))
    ASSETS.mkdir(parents=True, exist_ok=True)
    for output_scale in (1, 2, 3):
        build_layout(cards, "normal", 1, 10, 7, output_scale)
        build_layout(cards, "horizontal", 0.85, 10, 6, output_scale)
        build_layout(cards, "hybrid", 1.2, 11, 8, output_scale)
    index = {"\t".join(card): number for number, card in enumerate(cards)}
    (RUNTIME / "notification_popup_sprites.lua").write_text(
        "-- Generated by tools/build_notification_popup_atlas.py.\nreturn {\n"
        + "".join(f"    [{json.dumps(key)}] = {value},\n"
                  for key, value in index.items())
        + "}\n",
        encoding="utf-8",
    )
    print(f"Built {len(cards)} notification cards in three layouts")


if __name__ == "__main__":
    main()
