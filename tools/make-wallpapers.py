#!/usr/bin/env python3
"""Generates the SoftglowOS wallpapers as 4K JPEGs.

Each wallpaper is a flat background with a few very soft color clouds and a
fine grain on top (see clouds.py). The output is committed to the repo,
because rendering this live at login is far too slow.

Needs numpy and Pillow:  pip install numpy pillow
Run from the repo root:  python3 tools/make-wallpapers.py
"""
from pathlib import Path

from PIL import Image

from clouds import render

W, H = 3840, 2160
OUT = Path("files/system/usr/share/backgrounds/softglowos")

# Cloud positions and radii are in a 1600x900 design space, scaled to 4K.
DESIGN_WIDTH = 1600
SOFTNESS = 150  # how far each cloud edge fades out, in design space

WALLPAPERS = {
    # "Nebel": cool gray with a hint of teal
    "dark": {
        "background": "#141619",
        "grain": 4.5,
        "clouds": [
            (400, 300, 520, "#3a4a52", 0.8),
            (1200, 650, 560, "#24555f", 0.6),
            (1350, 200, 300, "#6d8c93", 0.3),
            (500, 820, 320, "#2c3b45", 0.6),
        ],
    },
    # "Lagune": cyan, mint and a touch of peach on off-white
    "light": {
        "background": "#f5f4f1",
        "grain": 3.5,
        "clouds": [
            (350, 250, 480, "#9fe0e6", 0.75),
            (1250, 700, 520, "#7cc7d4", 0.55),
            (1300, 180, 320, "#bfe8d6", 0.7),
            (500, 800, 360, "#f6d3bc", 0.6),
        ],
    },
}


for seed, (name, spec) in enumerate(WALLPAPERS.items()):
    path = OUT / f"softglowos-{name}.jpg"
    Image.fromarray(render(spec, W, H, DESIGN_WIDTH, SOFTNESS, seed)).save(path, quality=92, subsampling=0)
    print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")
