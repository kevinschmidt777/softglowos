#!/usr/bin/env python3
"""Generates the banners of our Bazaar start page as JPEGs.

Every section gets a light and a dark banner in the cloud look of the
wallpapers (see clouds.py), each with its own tint and the section name on it.
Bazaar can't localize banner images, so the names on the banners are English.

Needs numpy, Pillow and Geist Medium (github.com/vercel/geist-font):
  pip install numpy pillow
  GEIST_MEDIUM=/path/to/Geist-Medium.ttf python3 tools/make-bazaar-banners.py
Run from the repo root.
"""
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from clouds import render

# 2x the 300 px banner height in Bazaar, wide enough for large windows.
# Bazaar crops the sides (content-fit cover), so the name stays centered.
W, H = 2400, 600
DESIGN_WIDTH = 1600
SOFTNESS = 110
OUT = Path("files/system/usr/share/ublue-os/bazaar")
FONT = ImageFont.truetype(os.environ.get("GEIST_MEDIUM", "Geist-Medium.ttf"), 132)

LIGHT_BACKGROUND, DARK_BACKGROUND = "#f5f4f1", "#141619"
LIGHT_TEXT, DARK_TEXT = (30, 33, 36, 235), (255, 255, 255, 235)

# Per section: the name and the cloud colors (light, dark). No violet.
BANNERS = {
    "creator": ("Creator Tools", ["#9fe0e6", "#7cc7d4", "#f6d3bc"], ["#24555f", "#2f6f7a", "#5a4a40"]),
    "chat": ("Chat & Community", ["#a9cdf5", "#bfe8d6", "#8fd3e0"], ["#22406a", "#245a55", "#2b5f73"]),
    "gaming": ("Gaming", ["#f7c3a8", "#9fe0e6", "#f2b8a0"], ["#6a3a2a", "#24555f", "#5c2f2a"]),
    "media": ("Music & Media", ["#f5c4cf", "#f6d3bc", "#e8b4c0"], ["#5e2a38", "#5a4030", "#4f2834"]),
    "office": ("Office & Tools", ["#c9d3dc", "#bfe8d6", "#d7dde3"], ["#34404c", "#2c4a44", "#3d4752"]),
}

# Cloud layout in a 1600x400 design space; colors are filled in per banner.
LAYOUT = [(260, 90, 300, 0.75), (1250, 330, 340, 0.6), (820, 40, 220, 0.5)]


def banner(name, colors, background, text_color, seed):
    spec = {
        "background": background,
        "grain": 3.5,
        "clouds": [(x, y, r, c, o) for (x, y, r, o), c in zip(LAYOUT, colors)],
    }
    image = Image.fromarray(render(spec, W, H, DESIGN_WIDTH, SOFTNESS, seed)).convert("RGBA")
    text = Image.new("RGBA", image.size)
    ImageDraw.Draw(text).text((W / 2, H / 2), name, font=FONT, fill=text_color, anchor="mm")
    return Image.alpha_composite(image, text).convert("RGB")


for seed, (key, (name, light, dark)) in enumerate(BANNERS.items()):
    for variant, colors, background, text_color in (
        ("light", light, LIGHT_BACKGROUND, LIGHT_TEXT),
        ("dark", dark, DARK_BACKGROUND, DARK_TEXT),
    ):
        path = OUT / f"softglowos-{key}-{variant}.jpg"
        banner(name, colors, background, text_color, seed).save(path, quality=90, subsampling=0)
        print(f"{path}  {path.stat().st_size / 1e3:.0f} kB")
