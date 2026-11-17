"""Step 2 - the visual kit of a domain: backdrop, whether a presenter figure stands in the scene, and the pool of
objects used when the narration of a scene names nothing the engine can draw (or to avoid a repeated picture).

Pools are lookup tables (fixed mapping, report Part 3 "pattern -> lookup table"). Backdrops are drawn by code
with a seeded random generator: the same scene gives the same picture, but different scenes of one video get
different skylines, stars and hills, so even a scene with the same objects does not look identical.
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw

from modules.video.animation import GROUND_Y
from modules.video.composer import Style
from modules.video.fonts import get_font

POOLS: dict[str, tuple[str, ...]] = {
    "sleep": ("moon", "bed", "brain", "clock", "heart", "star"),
    "economy": ("coin", "bank", "basket", "tag", "bars_up"),
    "nature": ("tree", "sprout", "animal", "sun", "cloud", "bird", "fish"),
    "space": ("planet", "rocket", "moon", "star", "earth"),
    "weather": ("cloud", "building", "flood", "drop", "earth"),
    "tech": ("chip", "signal", "bars_up", "rocket", "book"),
    "generic": ("bulb", "book", "bars_up", "clock", "brain"),
}
# (gradient top, gradient bottom, ground colour, dark?)  -- dark backdrops use light header text
LOOK = {
    "sleep": ((96, 108, 184), (205, 192, 232), (92, 88, 156), False),
    "economy": ((255, 247, 226), (246, 232, 196), (214, 194, 154), False),
    "nature": ((176, 220, 248), (232, 246, 226), (112, 176, 96), False),
    "space": ((10, 12, 36), (34, 26, 70), (28, 30, 60), True),
    "weather": ((140, 160, 190), (204, 214, 230), (98, 106, 122), False),
    "tech": ((14, 34, 50), (26, 66, 84), (20, 48, 62), True),
}
SUB_TOP = 600                                  # the subtitle band starts here (720p); nothing is drawn below it


def is_dark(domain: str) -> bool:
    return LOOK.get(domain, (0, 0, 0, False))[3]


def _gradient(st: Style, top, bottom) -> Image.Image:
    w, h = st.size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = np.broadcast_to(np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t, (h, w, 3)).astype(np.uint8)
    return Image.fromarray(arr)


def _header(img: Image.Image, st: Style, facet: str, index: int, total: int, accent: tuple, dark: bool) -> None:
    w = st.size[0]
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, int(w * (index + 1) / max(1, total)), 8), fill=accent)
    chip = facet.replace("_", " ").upper()
    f = get_font(24, True)
    cw = int(f.getlength(chip)) + 40
    d.rounded_rectangle((st.margin, 34, st.margin + cw, 76), 21, fill=accent)
    d.text((st.margin + 20, 40), chip, font=f, fill=st.white)
    counter = f"{index + 1} / {total}"
    d.text((w - st.margin - get_font(24).getlength(counter), 42), counter, font=get_font(24),
           fill=(200, 210, 230) if dark else (90, 100, 120))


def draw_backdrop(domain: str, st: Style, facet: str, scene_id: int, index: int, total: int, accent: tuple) -> Image.Image:
    """Background, header and ground of one scene. Never touches the subtitle band."""
    rnd = random.Random(scene_id * 7919 + index * 104729 + len(domain))
    w, _ = st.size
    top, bottom, ground, dark = LOOK.get(domain, (st.bg_top, st.bg_bottom, (176, 186, 208), False))
    img = _gradient(st, top, bottom)
    d = ImageDraw.Draw(img, "RGBA")
    if domain in ("sleep", "space"):
        for _ in range(45 if domain == "sleep" else 140):
            x, y, r = rnd.randrange(w), rnd.randrange(110, 360 if domain == "sleep" else 560), rnd.choice((1, 1, 2, 3))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rnd.choice((120, 170, 230))))
    elif domain in ("economy", "weather"):
        col = (232, 218, 184, 255) if domain == "economy" else (118, 132, 158, 255)
        x = 0
        while x < w:
            bw, bh = rnd.randrange(60, 130), rnd.randrange(90, 250 if domain == "economy" else 300)
            d.rectangle((x, GROUND_Y - bh, x + bw, GROUND_Y), fill=col)
            x += bw + rnd.randrange(4, 30)
    elif domain == "nature":
        for _ in range(3):
            cx, cw = rnd.randrange(w), rnd.randrange(260, 480)
            d.ellipse((cx - cw, GROUND_Y - rnd.randrange(60, 130), cx + cw, GROUND_Y + 200), fill=(120 + rnd.randrange(30), 190, 120, 255))
        for _ in range(3):
            x, y = rnd.randrange(w), rnd.randrange(130, 260)
            d.ellipse((x, y, x + 110, y + 34), fill=(255, 255, 255, 150))
    elif domain == "tech":
        for x in range(0, w, 60):
            d.line((x, 100, x, GROUND_Y), fill=(255, 255, 255, 22), width=1)
        for y in range(100, GROUND_Y, 60):
            d.line((0, y, w, y), fill=(255, 255, 255, 22), width=1)
    if domain != "space":
        d.rectangle((0, GROUND_Y, w, SUB_TOP), fill=ground + (255,))
        d.line((0, GROUND_Y + 1, w, GROUND_Y + 1), fill=(255, 255, 255, 90), width=3)
    else:
        d.rectangle((0, SUB_TOP - 40, w, SUB_TOP), fill=ground + (255,))
    _header(img, st, facet, index, total, accent, dark)
    return img
