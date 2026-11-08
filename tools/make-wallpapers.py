#!/usr/bin/env python3
"""Generates the SoftglowOS wallpapers as 4K JPEGs.

Each wallpaper is a flat background with a few very soft color clouds, a fine grain (see clouds.py), and our wordmark small in the middle on top of
the grain, so it stays crisp. The output is committed to the repo,
because rendering this live at login is far too slow.

Needs numpy, Pillow and librsvg's GObject bindings (gir1.2-rsvg-2.0).
Run from the repo root:  python3 tools/make-wallpapers.py
"""
from pathlib import Path

import cairo
import gi
import numpy as np
from PIL import Image

gi.require_version("Rsvg", "2.0")
from gi.repository import Rsvg  # noqa: E402

from clouds import render  # noqa: E402

W, H = 3840, 2160
OUT = Path("files/system/usr/share/backgrounds/softglowos")
BRANDING = Path("files/system/usr/share/softglowos/branding")
LOGO_WIDTH = 560  # px at 4K (the wordmark is 400 x 96, so about 134 px high)

# Cloud positions and radii are in a 1600x900 design space, scaled to 4K.
DESIGN_WIDTH = 1600
SOFTNESS = 150  # how far each cloud edge fades out, in design space

WALLPAPERS = {
    # "Nebel": cool gray with a hint of teal
    "dark": {
        "background": "#141619",
        "grain": 4.5,
        "logo": "wordmark-white.svg",
        "logo_opacity": 0.5,
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
        "logo": "wordmark-dark.svg",
        "logo_opacity": 0.42,
        "clouds": [
            (350, 250, 480, "#9fe0e6", 0.75),
            (1250, 700, 520, "#7cc7d4", 0.55),
            (1300, 180, 320, "#bfe8d6", 0.7),
            (500, 800, 360, "#f6d3bc", 0.6),
        ],
    },
}


def logo_rgba(svg, width):
    """An SVG rendered width pixels wide (Geist must be installed for the
    text), as straight (not premultiplied) RGBA floats."""
    handle = Rsvg.Handle.new_from_file(str(svg))
    ok, svg_width, svg_height = handle.get_intrinsic_size_in_pixels()
    height = round(width * svg_height / svg_width)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    viewport = Rsvg.Rectangle()
    viewport.x, viewport.y, viewport.width, viewport.height = 0, 0, width, height
    handle.render_document(cairo.Context(surface), viewport)
    bgra = np.ndarray((height, width, 4), np.uint8, surface.get_data(), strides=(surface.get_stride(), 4, 1))
    alpha = bgra[..., 3:4].astype(np.float64) / 255
    rgb = bgra[..., 2::-1].astype(np.float64) / np.maximum(alpha, 1e-6)
    return np.concatenate([rgb, alpha], axis=2)


def center_logo(svg, opacity):
    logo = logo_rgba(svg, LOGO_WIDTH)
    height, width = logo.shape[:2]

    def paint(image):
        top, left = (H - height) // 2, (W - width) // 2
        area = image[top:top + height, left:left + width].astype(np.float64)
        alpha = logo[..., 3:4] * opacity
        area += (logo[..., :3] - area) * alpha
        image[top:top + height, left:left + width] = np.clip(np.rint(area), 0, 255).astype(np.uint8)
        return image
    return paint


for seed, (name, spec) in enumerate(WALLPAPERS.items()):
    path = OUT / f"softglowos-{name}.jpg"
    image = render(spec, W, H, DESIGN_WIDTH, SOFTNESS, seed)
    image = center_logo(BRANDING / spec["logo"], spec["logo_opacity"])(image)
    Image.fromarray(image).save(path, quality=92, subsampling=0)
    print(f"{path}  {path.stat().st_size / 1e6:.1f} MB")
