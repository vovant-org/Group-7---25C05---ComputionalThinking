"""ANIMATION from AI pictures: the picture of each claim is cut out of its plain background and animated by code.

Pipeline per scene (all deterministic apart from the picture itself):
  1. the picture comes from `ArtService` (same prompt/style as the INFOGRAPHIC pictures: ONE subject, plain white
     background, wide margin, no text), so every scene of the video shares one style prompt
  2. `make_cutout` removes the plain background (fill from the border, so white INSIDE the subject stays)
     and gives a transparent sprite plus the subject's dominant colour
  3. `compose_ai_scene` builds an `AnimatedScene` from the existing Layer / Track / LayerRenderer parts:
     a backdrop tinted with the picture's colour, a soft glow, a shadow and the subject, which slides in from
     the side, pops, then floats and zooms slowly (Ken Burns). The Motion Planner's `energy` scales every movement,
     so the hook, the summary and important scenes are livelier.
  The result has the interface the renderer, `check_animation` and the report builder already use.

Fallback policy "A" (agreed with the team): `collect_pictures` retries the scenes that have no picture; when some
are still missing it returns None and `make_video` draws the WHOLE video with the code-drawn animation, so the video
never mixes AI pictures with stick figures. The report says why.

ASSUMPTIONS (not measured): the tolerance for "plain background" (38 of 255 per channel), the 1 %-92 % subject area
that counts as a successful cut-out, sizes and movement amplitudes are our own choice.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Mapping, Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from core.models import Scene
from modules.video.animation import AnimatedScene, Layer, Track, fade, hold, join, pop, wiggle
from modules.video.composer import Style
from modules.video.motion_planner import plan_motion
from modules.visual_engine.kits import SUB_TOP, _header

MAX_W, MAX_H = 660, 380          # the subject is fitted into this box (720p)
FLOOR_Y = 548                    # the subject stands here; the subtitle band starts at SUB_TOP (600)
BG_TOL = 38                      # per-channel distance from the background colour that still counts as background
BORDER_PLAIN = 0.85              # share of border pixels that must be background for a cut-out to be tried
MIN_SUBJECT, MAX_SUBJECT = 0.01, 0.92
WORK = 384                       # the mask is computed on a copy no larger than this
ROUNDS = 2                       # retries for scenes without a picture (after the first pass)
WHITE = (255, 255, 255)


def _mix(a: Sequence[float], b: Sequence[float], t: float) -> tuple:
    return tuple(int(round(x * (1 - t) + y * t)) for x, y in zip(a, b))


# ------------------------------------------------------------------ cut-out
def _border_connected(near: np.ndarray) -> np.ndarray:
    """Pixels of `near` (bool HxW) that are 4-connected to the image border (plain breadth-first fill)."""
    h, w = near.shape
    seen = np.zeros_like(near, dtype=bool)
    stack = [(y, x) for y in range(h) for x in (0, w - 1) if near[y, x]] + \
            [(y, x) for x in range(w) for y in (0, h - 1) if near[y, x]]
    for y, x in stack:
        seen[y, x] = True
    while stack:
        y, x = stack.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and near[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                stack.append((ny, nx))
    return seen


def subject_mask(rgb: Image.Image) -> Optional[Image.Image]:
    """L mask (255 = subject) at the size of `rgb`, or None when the picture has no plain background to remove.

    Background = pixels close to the colour of the picture's border, CONNECTED to the border. White inside the
    subject (an eye, a plate, a hole) is not connected to the border, so it stays."""
    small = rgb.copy()
    small.thumbnail((WORK, WORK), Image.LANCZOS)
    arr = np.asarray(small).astype(np.int16)
    h, w = arr.shape[:2]
    if h < 8 or w < 8:
        return None
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bg = np.median(border, axis=0)
    if (np.abs(border - bg).max(axis=1) <= BG_TOL).mean() < BORDER_PLAIN:
        return None                                              # busy border: not a "subject on plain background"
    near = (np.abs(arr - bg).max(axis=2) <= BG_TOL)
    outside = _border_connected(near)
    subject = ~outside
    frac = float(subject.mean())
    if not MIN_SUBJECT <= frac <= MAX_SUBJECT:
        return None
    mask = Image.fromarray((subject * 255).astype(np.uint8))
    mask = mask.filter(ImageFilter.MinFilter(3))                 # shave the white halo around the edge
    return mask.resize(rgb.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.0))


def dominant_tone(rgba: Image.Image, fallback: tuple = (110, 140, 200)) -> tuple:
    """Mean colour of the saturated opaque pixels (the 'colour' of the picture); `fallback` for a grey picture."""
    small = rgba.copy()
    small.thumbnail((96, 96))
    arr = np.asarray(small)
    rgb, alpha = arr[:, :, :3].reshape(-1, 3), arr[:, :, 3].reshape(-1)
    hsv = np.asarray(Image.fromarray(arr[:, :, :3]).convert("HSV")).reshape(-1, 3)
    keep = (alpha > 200) & (hsv[:, 1] > 70) & (hsv[:, 2] > 70)
    if keep.sum() < 20:
        return fallback
    return tuple(int(v) for v in rgb[keep].mean(axis=0))


@dataclass
class Cutout:
    sprite: Image.Image              # RGBA, fitted into MAX_W x MAX_H
    tone: tuple                      # dominant colour of the subject
    cut: bool                        # True: the background was removed; False: the whole picture is shown as a card
    note: str = ""


def _fit(sprite: Image.Image) -> Image.Image:
    k = min(MAX_W / sprite.width, MAX_H / sprite.height)
    return sprite.resize((max(1, round(sprite.width * k)), max(1, round(sprite.height * k))), Image.LANCZOS)


def make_cutout(img: Image.Image) -> Cutout:
    rgb = img.convert("RGB")
    mask = subject_mask(rgb)
    if mask is not None:
        box = mask.point(lambda v: 255 if v > 40 else 0).getbbox()
        if box:
            pad = 4
            box = (max(0, box[0] - pad), max(0, box[1] - pad), min(rgb.width, box[2] + pad), min(rgb.height, box[3] + pad))
            rgba = rgb.convert("RGBA")
            rgba.putalpha(mask)
            rgba = rgba.crop(box)
            return Cutout(_fit(rgba), dominant_tone(rgba), True)
    card = rgb.convert("RGBA")                                   # no plain background: keep the whole picture, rounded
    round_mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(round_mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), max(8, card.width // 14), fill=255)
    card.putalpha(round_mask)
    return Cutout(_fit(card), dominant_tone(card), False,
                  "the picture has no plain background: the whole picture is shown as a card")


# ------------------------------------------------------------------ one scene
def _backdrop(st: Style, tone: tuple, facet: str, index: int, total: int, accent: tuple) -> Image.Image:
    w, h = st.size
    top, bottom = _mix(tone, WHITE, 0.90), _mix(tone, WHITE, 0.70)
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    arr = np.broadcast_to(np.array(top, np.float32) * (1 - t) + np.array(bottom, np.float32) * t, (h, w, 3)).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle((0, FLOOR_Y + 8, w, SUB_TOP), fill=_mix(tone, WHITE, 0.55) + (255,))
    d.line((0, FLOOR_Y + 9, w, FLOOR_Y + 9), fill=(255, 255, 255, 140), width=3)
    _header(img, st, facet, index, total, accent, False)
    return img


GLOW_SCALE_MAX = 1.1             # pop 1.05 + wiggle: the glow never grows past this


def _glow(tone: tuple, rx: float, ry: float) -> Image.Image:
    """Soft elliptical glow of size 2rx x 2ry; the visible part stays inside the sprite (4 sigma margin)."""
    blur = max(5.0, ry * 0.08)
    ex, ey = max(10.0, rx - 4 * blur), max(10.0, ry - 4 * blur)
    img = Image.new("RGBA", (int(2 * rx), int(2 * ry)), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((rx - ex, ry - ey, rx + ex, ry + ey), fill=_mix(tone, WHITE, 0.45) + (150,))
    return img.filter(ImageFilter.GaussianBlur(blur))


def _shadow() -> Image.Image:
    img = Image.new("RGBA", (440, 60), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((20, 14, 420, 46), fill=(40, 44, 66, 90))
    return img.filter(ImageFilter.GaussianBlur(5))


def compose_ai_scene(scene: Scene, claim_text: str, art: Image.Image, st: Style = Style(), index: int = 0,
                     total: int = 1) -> AnimatedScene:
    """Animated scene from one AI picture. Raises ValueError for a position outside the video (like the planner)."""
    plan = replace(plan_motion(scene, index, total), pose="", prop="ai_picture")
    cut = make_cutout(art)
    sp = cut.sprite
    w, h = sp.size
    s = -1 if plan.mirror else 1                                  # enters from its own side, alternating
    cx, cy, e = st.size[0] / 2, FLOOR_Y - h / 2, plan.energy
    accent = st.accent(scene.facet)
    base = _backdrop(st, cut.tone, scene.facet, index, total, accent)

    glow_ry = max(40.0, min(230.0, (SUB_TOP - 4 - cy) / GLOW_SCALE_MAX))   # stays above the subtitle band
    glow_rx = min(420.0, w * 0.6 + 80)

    x_in = Track(((0.0, cx - 300 * s), (0.22, cx)))
    bob = Track(join(((0.0, cy),), wiggle(cy, 6.0 * e, 3, 0.22, 1.0, n=8)), ease=False)
    zoom = Track(join(pop(0.03, 0.22, 1.12), ((1.0, 1.045 + 0.02 * e),)))
    layers = [
        Layer("glow", _glow(cut.tone, glow_rx, glow_ry), hold(cx), hold(cy),
              scale=Track(join(pop(0.02, 0.25, 1.05), wiggle(1.0, 0.04 * e, 3, 0.3, 1.0, n=8))),
              alpha=Track(fade(0.02, 0.15)), z=1),
        Layer("shadow", _shadow(), x_in, hold(FLOOR_Y + 6), scale=hold(min(1.2, max(0.5, w / 440))),
              alpha=Track(fade(0.03, 0.14)), z=2),
        Layer("picture", sp, x_in, bob, scale=zoom, alpha=Track(fade(0.03, 0.12)), z=3),
    ]
    warnings = [f"scene {scene.scene_id}: {cut.note}"] if cut.note else []
    return AnimatedScene(scene_id=scene.scene_id, plan=plan, base=base, layers=layers, claim_text=claim_text,
                         layout="cutout:ai_picture", requested_layout=scene.layout, warnings=warnings)


def compose_ai_scenes(scenes: Sequence[Scene], pictures: Mapping[int, Image.Image], st: Style = Style()) -> dict:
    """All scenes of a video, in order: scene_id -> AnimatedScene."""
    total = len(scenes)
    return {s.scene_id: compose_ai_scene(s, s.narration, pictures[s.scene_id], st, i, total) for i, s in enumerate(scenes)}


# ------------------------------------------------------------------ getting the pictures (fallback policy A)
def collect_pictures(art, scenes: Sequence[Scene], visuals: Mapping[str, str], *, rounds: int = ROUNDS,
                     progress: Optional[Callable[[float, str], None]] = None) -> tuple[Optional[dict], str]:
    """(pictures by scene_id, "") when EVERY scene has one; otherwise (None, why) so the caller draws the whole video
    with the code-drawn animation. Scenes without a picture are tried again `rounds` times (circuit breaker re-opened,
    another seed); pictures already obtained are kept."""
    total = len(scenes)
    cid = lambda s: s.claim_ids[0] if s.claim_ids else ""
    undescribed = [s.scene_id for s in scenes if cid(s) not in visuals]
    if undescribed:
        return None, f"no picture description for scene(s) {undescribed}"
    pics: dict = {}
    for r in range(rounds + 1):
        if r and hasattr(art, "reset_failures"):
            art.reset_failures()
        for i, s in enumerate(scenes):
            if s.scene_id in pics:
                continue
            if progress:
                progress(0.0, f"AI picture {i + 1}/{total}")
            img = art.get(cid(s), visuals[cid(s)], seed=7 + 11 * r)
            if img is not None:
                pics[s.scene_id] = img
        if len(pics) == total:
            return pics, ""
    missing = [s.scene_id for s in scenes if s.scene_id not in pics]
    last = "; ".join(e[:120] for e in getattr(art, "errors", [])[-2:])
    return None, (f"{len(missing)} of {total} scene(s) have no AI picture after {rounds} retries"
                  + (f" ({last})" if last else ""))
