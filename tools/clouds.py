"""Soft color clouds with grain, the look of the SoftglowOS wallpapers and banners.

The clouds are computed as exact smooth falloffs and the grain also dithers
them, so there is no banding.
"""
import numpy as np


def rgb(hex_color):
    return np.array([int(hex_color[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64)


def render(spec, width, height, design_width, softness, seed):
    """Renders a spec to an RGB uint8 array.

    Cloud positions and radii in the spec are given in a design space that is
    design_width wide; softness (how far each cloud edge fades out) too.
    """
    scale = width / design_width
    softness *= scale
    y, x = np.mgrid[0:height, 0:width].astype(np.float64)
    image = np.empty((height, width, 3))
    image[:] = rgb(spec["background"])
    for cx, cy, r, color, opacity in spec["clouds"]:
        dist = np.hypot(x - cx * scale, y - cy * scale)
        # Smooth step from 1 inside the cloud to 0 outside (blurred disc)
        alpha = opacity * 0.5 * (1 - np.tanh(0.85 * (dist - r * scale) / softness))
        image += (rgb(color) - image) * alpha[..., None]
    noise = np.random.default_rng(seed).normal(0, spec["grain"], (height, width, 1))
    return np.clip(image + noise, 0, 255).astype(np.uint8)
