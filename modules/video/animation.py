"""Cut-out animation (render mode LAYERED, report 4(b) and 5.9.10 option L2) drawn entirely by code.

A scene is a stack of LAYERS. Every layer is a small transparent picture (a "sprite") plus KEYFRAME
tracks that say where it is, how it is turned and scaled, and how visible it is, at every moment of the
scene. Time is a fraction u in [0, 1] of the scene length, so the same movement fits a 5 s scene and a
10 s scene, and everything is deterministic: the same scene gives the same frames.

  Track     value over time: key points (u, value), eased between them        (keyframes)
  Layer     sprite + tracks x, y, rot (degrees, counter-clockwise), scale, sy, alpha
  sprite    drawn 2x larger and shrunk (anti-aliasing); padded so that its CENTRE is the pivot,
            which makes rotation and scaling about the pivot a plain "rotate / resize the image"
  Character a stick figure. Default (RIG = "jointed"): the jointed figure of `stickman.py` (knees, elbows,
            walking, lip-sync, ~13 actions). RIG = "cutout": the older figure of four rigid sprites (body, head,
            two arms that turn about the shoulders); kept for comparison and as a fallback
  Props     what the character talks about: cause -> effect, bars, steps, chart, light bulb, bubble

What the character does and which prop is drawn comes from `motion_planner.plan_motion`.
No text is drawn inside an animation scene (the narration is shown by the subtitles), so there is
nothing that an image model could misspell (report 1.2.4). The bottom band stays free for subtitles;
`check_animation` verifies this on real frames.

ASSUMPTIONS (not measured): the look (colours, sizes, 4-8 keyframes per movement) is our own choice.
The AI image-to-video mode CLIP is NOT used: no provider is connected (see make_video).
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw

from core.models import Scene
from modules.video.composer import Style, draw_base
from modules.video.motion_planner import MotionPlan, plan_motion

SS = 2                                   # sprite supersampling factor
INK = (28, 34, 48)
WHITE = (255, 255, 255)
GREY = (150, 165, 190)
YELLOW = (250, 205, 70)
GROUND_Y = 540                           # feet and prop baselines (720p); the subtitle band starts at 600
RIG = "jointed"                          # "jointed" (stickman.py) or "cutout" (the older rigid figure below)


# ------------------------------------------------------------------ keyframe tracks
def smooth(f: float) -> float:
    """Ease in and out: 0 -> 0, 1 -> 1, slope 0 at both ends."""
    return f * f * (3.0 - 2.0 * f)


@dataclass(frozen=True)
class Track:
    """A value that changes over the scene. keys = ((u0, v0), (u1, v1), ...) with increasing u."""
    keys: tuple
    ease: bool = True

    def __post_init__(self):
        if not self.keys:
            raise ValueError("a track needs at least one key")
        us = [k[0] for k in self.keys]
        if any(b <= a for a, b in zip(us, us[1:])):
            raise ValueError(f"track keys must have strictly increasing u, got {us}")
        object.__setattr__(self, "_us", us)

    def __call__(self, u: float) -> float:
        k, us = self.keys, self._us
        if u <= us[0]:
            return float(k[0][1])
        if u >= us[-1]:
            return float(k[-1][1])
        i = bisect_right(us, u) - 1
        (u0, v0), (u1, v1) = k[i], k[i + 1]
        f = (u - u0) / (u1 - u0)
        return v0 + (v1 - v0) * (smooth(f) if self.ease else f)


def hold(v: float) -> Track:
    return Track(((0.0, v),))


def wiggle(center: float, amp: float, cycles: float, u0: float, u1: float, n: int = 10) -> tuple:
    """Key points of a sine movement between u0 and u1 (starts and ends at `center`)."""
    steps = max(2, int(math.ceil(cycles * n)))
    return tuple((u0 + (u1 - u0) * i / steps, center + amp * math.sin(2 * math.pi * cycles * i / steps))
                 for i in range(steps + 1))


def pop(u0: float, u1: float, peak: float = 1.15) -> tuple:
    """Scale keys: 0 before u0, overshoots to `peak`, settles at 1 at u1."""
    mid = u0 + (u1 - u0) * 0.65
    return ((0.0, 0.0), (u0, 0.0), (mid, peak), (u1, 1.0))


def fade(u0: float, u1: float) -> tuple:
    return ((0.0, 0.0), (u0, 0.0), (u1, 1.0))


def join(*parts: tuple) -> tuple:
    """Concatenate key lists (later parts win when u values collide)."""
    out: dict[float, float] = {}
    for p in parts:
        for u, v in p:
            out[round(u, 6)] = v
    return tuple(sorted(out.items()))


# ------------------------------------------------------------------ layers
@dataclass
class Layer:
    name: str
    sprite: Image.Image                      # RGBA, pivot at the centre
    x: Track
    y: Track
    rot: Track = field(default_factory=lambda: hold(0.0))
    scale: Track = field(default_factory=lambda: hold(1.0))
    sy: Track = field(default_factory=lambda: hold(1.0))        # extra vertical scale (bars grow)
    alpha: Track = field(default_factory=lambda: hold(1.0))
    z: int = 0


def make_sprite(size: tuple[int, int], pivot: tuple[int, int], draw: Callable) -> Image.Image:
    """Draw a sprite. `size` and `pivot` are in 1x pixels; `draw(d, k)` draws with coordinates times k.
    The result is padded so that the pivot is exactly its centre."""
    w, h = size
    px, py = pivot
    r = int(math.ceil(max(math.hypot(x - px, y - py) for x in (0, w) for y in (0, h)))) + 2
    piece = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    draw(ImageDraw.Draw(piece), SS)
    big = Image.new("RGBA", (2 * r * SS, 2 * r * SS), (0, 0, 0, 0))
    big.paste(piece, ((r - px) * SS, (r - py) * SS), piece)
    return big.resize((2 * r, 2 * r), Image.LANCZOS)


def _line(d, k, p0, p1, color, width):
    d.line([(p0[0] * k, p0[1] * k), (p1[0] * k, p1[1] * k)], fill=color, width=int(width * k))
    for p in (p0, p1):                                          # round caps
        r = width * k / 2
        d.ellipse((p[0] * k - r, p[1] * k - r, p[0] * k + r, p[1] * k + r), fill=color)


def _circle(d, k, c, r, fill=None, outline=None, width=0):
    d.ellipse(((c[0] - r) * k, (c[1] - r) * k, (c[0] + r) * k, (c[1] + r) * k),
              fill=fill, outline=outline, width=int(width * k))


def _rrect(d, k, box, radius, fill=None, outline=None, width=0):
    d.rounded_rectangle(tuple(v * k for v in box), radius * k, fill=fill, outline=outline, width=int(width * k))


# ------------------------------------------------------------------ the character
@dataclass(frozen=True)
class Stage:
    """Where things stand in one scene."""
    fx: int                  # x of the character
    cx: int                  # x of the centre of the prop
    s: int                   # +1: the character stands on the left and points right; -1: mirrored
    gy: int                  # ground line
    accent: tuple
    accent2: tuple
    energy: float


def _arm_keys(pose: str, e: float, back: bool) -> tuple:
    """Arm angle keys (degrees, +90 = horizontal towards the prop, +180 = straight up)."""
    if pose == "wave":
        if back:
            return ((0.0, -8.0),)
        return join(((0.0, 0.0), (0.12, 0.0), (0.28, 150.0)), wiggle(150.0, 22 * e, 3, 0.28, 0.78),
                    ((0.9, 20.0), (1.0, 0.0)))
    if pose == "point":
        if back:
            return ((0.0, -8.0),)
        return join(((0.0, 0.0), (0.2, 0.0), (0.38, 85.0)), wiggle(85.0, 5 * e, 2, 0.38, 0.9))
    if pose == "think":
        if back:
            return ((0.0, -8.0),)
        return ((0.0, 0.0), (0.2, 0.0), (0.42, 152.0))
    if pose == "shrug":
        sign = -1.0 if back else 1.0
        return join(((0.0, 0.0), (0.2, 0.0), (0.34, sign * 38.0)), wiggle(sign * 38.0, 9 * e, 2, 0.34, 0.9))
    raise ValueError(f"unknown pose {pose!r}")


def arm_angle(pose: str, u: float, energy: float = 1.0, back: bool = False) -> float:
    """Angle of an arm (before mirroring) at time u; used by the tests and by the character builder."""
    return Track(_arm_keys(pose, energy, back))(u)


def _enter(x: float, s: int) -> Track:
    """The character slides in from its own side during the first 16 % of the scene."""
    return Track(((0.0, x - 260 * s), (0.16, x)))


def _bob(y0: float, e: float) -> Track:
    return Track(join(((0.0, y0),), wiggle(y0, 4.0 * e, 4, 0.16, 1.0, n=8)), ease=False)


def character_layers(stage: Stage, pose: str, *, rig: Optional[str] = None, role: str = "body",
                     narration: str = "", audio_s: Optional[float] = None, script=None) -> list[Layer]:
    """The figure of a scene. rig None = RIG. The jointed figure walks in, acts out `pose` (or `script`, a list of
    stickman.Beat) and moves its mouth with `narration`; the cut-out figure ignores role / narration / script."""
    if (rig or RIG) == "jointed":
        from modules.video.stickman import stickman_layer
        return [stickman_layer(stage, pose, role=role, narration=narration, audio_s=audio_s, script=script)]
    if (rig or RIG) != "cutout":
        raise ValueError(f"unknown rig {rig!r}")
    s, e, fx, gy = stage.s, stage.energy, stage.fx, stage.gy
    hip_y = gy - 106
    neck_y = hip_y - 100

    def body(d, k):
        _line(d, k, (70, 120), (70, 20), INK, 10)                            # torso
        _line(d, k, (70, 120), (34, 224), INK, 10)                           # legs
        _line(d, k, (70, 120), (106, 224), INK, 10)
        _line(d, k, (34, 224), (22, 226), INK, 10)                           # feet
        _line(d, k, (106, 224), (118, 226), INK, 10)

    def head(d, k):
        _circle(d, k, (40, 40), 32, fill=WHITE, outline=INK, width=7)
        _circle(d, k, (31, 36), 3.5, fill=INK)
        _circle(d, k, (49, 36), 3.5, fill=INK)
        d.arc((28 * k, 36 * k, 52 * k, 58 * k), 20, 160, fill=INK, width=int(4 * k))   # smile

    def arm(d, k):
        _line(d, k, (20, 10), (20, 96), INK, 9)
        _circle(d, k, (20, 100), 9, fill=WHITE, outline=INK, width=5)

    body_sp = make_sprite((140, 230), (70, 120), body)
    head_sp = make_sprite((80, 80), (40, 72), head)
    arm_sp = make_sprite((40, 120), (20, 10), arm)

    bob_body, bob_neck, bob_sh = _bob(hip_y, e), _bob(neck_y, e), _bob(neck_y + 14, e)
    head_rot = Track(wiggle(0.0, 4.0 * e, 3, 0.2, 0.9)) if pose != "think" else \
        Track(((0.0, 0.0), (0.3, 0.0), (0.5, 11.0 * s)))
    front = Track(tuple((u, v * s) for u, v in _arm_keys(pose, e, False)))
    back = Track(tuple((u, v * s) for u, v in _arm_keys(pose, e, True)))
    return [
        Layer("arm_back", arm_sp, _enter(fx - 4 * s, s), bob_sh, rot=back, z=1),
        Layer("body", body_sp, _enter(fx, s), bob_body, z=2),
        Layer("head", head_sp, _enter(fx, s), bob_neck, rot=head_rot, z=3),
        Layer("arm_front", arm_sp, _enter(fx + 4 * s, s), bob_sh, rot=front, z=4),
    ]


# ------------------------------------------------------------------ props
def _line_sprite(p0, p1, color, width):
    """Sprite of a line between two points; returns (sprite, midpoint)."""
    x0, y0 = min(p0[0], p1[0]) - width, min(p0[1], p1[1]) - width
    x1, y1 = max(p0[0], p1[0]) + width, max(p0[1], p1[1]) + width
    w, h = int(x1 - x0) + 1, int(y1 - y0) + 1
    q0, q1 = (p0[0] - x0, p0[1] - y0), (p1[0] - x0, p1[1] - y0)
    mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    return make_sprite((w, h), (w // 2, h // 2), lambda d, k: _line(d, k, q0, q1, color, width)), mid


def _static(x, y):
    return hold(x), hold(y)


def prop_cause_effect(st: Stage) -> list[Layer]:
    cx, gy, e = st.cx, st.gy, st.energy
    a = make_sprite((110, 110), (55, 55), lambda d, k: (
        _rrect(d, k, (3, 3, 107, 107), 20, fill=st.accent, outline=INK, width=5),
        _circle(d, k, (55, 55), 22, fill=WHITE)))
    b = make_sprite((140, 140), (70, 70), lambda d, k: (
        _rrect(d, k, (3, 3, 137, 137), 24, fill=st.accent2, outline=INK, width=5),
        d.polygon([(p[0] * k, p[1] * k) for p in
                   [(70, 22), (82, 54), (116, 54), (88, 74), (99, 108), (70, 88), (41, 108), (52, 74),
                    (24, 54), (58, 54)]], fill=WHITE)))
    arrow = make_sprite((150, 50), (75, 25), lambda d, k: (
        _line(d, k, (8, 25), (128, 25), INK, 10),
        _line(d, k, (106, 6), (132, 25), INK, 10), _line(d, k, (106, 44), (132, 25), INK, 10)))
    by = gy - 70
    pulse = wiggle(1.0, 0.08 * e, 2 if e > 1.2 else 1, 0.74, 0.96, n=6)
    return [
        Layer("cause", a, hold(cx - 170), hold(by), scale=Track(pop(0.20, 0.36)), alpha=Track(fade(0.20, 0.26)), z=5),
        Layer("arrow", arrow, Track(((0.0, cx - 40), (0.38, cx - 40), (0.50, cx - 5))), hold(by),
              alpha=Track(fade(0.38, 0.46)), z=5),
        Layer("effect", b, hold(cx + 160), hold(by - 8),
              scale=Track(join(pop(0.52, 0.68, 1.2), pulse)), alpha=Track(fade(0.52, 0.58)), z=5),
    ]


def prop_bars(st: Stage) -> list[Layer]:
    cx, gy = st.cx, st.gy

    def bar(h, color):
        return make_sprite((100, h), (50, h), lambda d, k: _rrect(d, k, (2, 2, 98, h - 1), 10, fill=color,
                                                                  outline=INK, width=5))

    base = make_sprite((340, 12), (170, 6), lambda d, k: _line(d, k, (6, 6), (334, 6), INK, 8))
    top = make_sprite((70, 70), (35, 35), lambda d, k: (
        _line(d, k, (35, 58), (35, 14), st.accent2, 12),
        _line(d, k, (14, 34), (35, 12), st.accent2, 12), _line(d, k, (56, 34), (35, 12), st.accent2, 12)))
    grow1, grow2 = Track(((0.0, 0.0), (0.20, 0.0), (0.45, 1.0))), Track(((0.0, 0.0), (0.45, 0.0), (0.75, 1.0)))
    return [
        Layer("baseline", base, hold(cx), hold(gy), z=4),
        Layer("bar_a", bar(150, GREY), hold(cx - 85), hold(gy), sy=grow1, z=5),
        Layer("bar_b", bar(260, st.accent), hold(cx + 85), hold(gy), sy=grow2, z=5),
        Layer("up", top, hold(cx + 85), Track(join(((0.0, gy - 300),), wiggle(gy - 300, -9 * st.energy, 2, 0.8, 1.0, n=6))),
              scale=Track(pop(0.76, 0.86)), alpha=Track(fade(0.76, 0.82)), z=6),
    ]


def prop_steps(st: Stage) -> list[Layer]:
    cx, gy = st.cx, st.gy

    def block(h, color):
        return make_sprite((110, h), (55, h), lambda d, k: _rrect(d, k, (2, 2, 108, h - 1), 8, fill=color,
                                                                  outline=INK, width=5))

    flag = make_sprite((70, 90), (10, 86), lambda d, k: (
        _line(d, k, (10, 86), (10, 8), INK, 7),
        d.polygon([(p[0] * k, p[1] * k) for p in [(12, 8), (62, 24), (12, 42)]], fill=st.accent2, outline=INK)))
    layers = []
    for i, (dx, h, u0) in enumerate([(-120, 70, 0.20), (0, 140, 0.38), (120, 210, 0.56)]):
        color = st.accent if i == 2 else tuple(int(c * 0.55 + 255 * 0.45) for c in st.accent)
        layers.append(Layer(f"step{i}", block(h, color), hold(cx + dx), hold(gy),
                            sy=Track(((0.0, 0.0), (u0, 0.0), (u0 + 0.14, 1.0))), z=5))
    layers.append(Layer("flag", flag, hold(cx + 120), hold(gy - 210),
                        rot=Track(wiggle(0.0, 7 * st.energy, 3, 0.74, 1.0)),
                        scale=Track(pop(0.72, 0.8)), alpha=Track(fade(0.72, 0.76)), z=6))
    return layers


def prop_chart(st: Stage) -> list[Layer]:
    cx, gy = st.cx, st.gy
    oy = gy - 125
    axes = make_sprite((340, 250), (170, 125), lambda d, k: (
        _line(d, k, (22, 20), (22, 226), INK, 7), _line(d, k, (22, 226), (322, 226), INK, 7)))
    pts = [(-135, 80), (-65, 35), (5, 50), (75, -30), (145, -85)]
    layers = [Layer("axes", axes, hold(cx), hold(oy), z=4)]
    for i, (p0, p1) in enumerate(zip(pts, pts[1:])):
        spr, mid = _line_sprite((cx + p0[0], oy + p0[1]), (cx + p1[0], oy + p1[1]), st.accent, 9)
        u0 = 0.20 + 0.15 * i
        layers.append(Layer(f"seg{i}", spr, hold(mid[0]), hold(mid[1]), alpha=Track(fade(u0, u0 + 0.12)), z=5))
    dot = make_sprite((36, 36), (18, 18), lambda d, k: _circle(d, k, (18, 18), 13, fill=st.accent2, outline=INK, width=4))
    last = pts[-1]
    layers.append(Layer("peak", dot, hold(cx + last[0]), hold(oy + last[1]),
                        scale=Track(join(pop(0.78, 0.88, 1.3), wiggle(1.0, 0.12 * st.energy, 2, 0.9, 1.0, n=5))),
                        alpha=Track(fade(0.78, 0.82)), z=6))
    return layers


def prop_bulb(st: Stage) -> list[Layer]:
    cx, gy, e = st.cx, st.gy, st.energy
    bulb = make_sprite((140, 190), (70, 95), lambda d, k: (
        _circle(d, k, (70, 70), 56, fill=YELLOW, outline=INK, width=6),
        _rrect(d, k, (46, 118, 94, 150), 6, fill=GREY, outline=INK, width=5),
        _rrect(d, k, (54, 150, 86, 172), 6, fill=GREY, outline=INK, width=5),
        _line(d, k, (56, 80), (70, 56), INK, 5), _line(d, k, (70, 56), (84, 80), INK, 5)))
    rays = make_sprite((260, 260), (130, 130), lambda d, k: [
        _line(d, k, (130 + 78 * math.cos(a), 130 + 78 * math.sin(a)),
              (130 + 108 * math.cos(a), 130 + 108 * math.sin(a)), st.accent2, 8)
        for a in [i * math.pi / 4 for i in range(8)]])
    y = gy - 170
    return [
        Layer("rays", rays, hold(cx), hold(y - 5), rot=Track(((0.0, 0.0), (1.0, 40.0)), ease=False),
              alpha=Track(join(fade(0.36, 0.46), wiggle(1.0, -0.35, 3, 0.5, 1.0, n=6))), scale=Track(pop(0.36, 0.5, 1.1)), z=4),
        Layer("bulb", bulb, hold(cx), hold(y), scale=Track(join(pop(0.22, 0.36, 1.18), wiggle(1.0, 0.05 * e, 3, 0.6, 1.0, n=6))),
              alpha=Track(fade(0.22, 0.28)), z=5),
    ]


def prop_bubble(st: Stage) -> list[Layer]:
    cx, gy = st.cx, st.gy
    bubble = make_sprite((300, 190), (150, 95), lambda d, k: (
        _rrect(d, k, (4, 4, 296, 150), 40, fill=WHITE, outline=INK, width=6),
        d.polygon([(p[0] * k, p[1] * k) for p in [(70, 146), (50, 186), (112, 148)]], fill=WHITE, outline=INK)))
    dot = make_sprite((34, 34), (17, 17), lambda d, k: _circle(d, k, (17, 17), 12, fill=st.accent))
    y = gy - 190
    layers = [Layer("bubble", bubble, hold(cx), hold(y), scale=Track(pop(0.22, 0.38)), alpha=Track(fade(0.22, 0.28)), z=5)]
    for i, dx in enumerate((-70, 0, 70)):
        u0 = 0.44 + 0.1 * i
        layers.append(Layer(f"dot{i}", dot, hold(cx + dx), hold(y - 18),
                            scale=Track(join(pop(u0, u0 + 0.1), wiggle(1.0, 0.18 * st.energy, 2, 0.8, 1.0, n=6))),
                            alpha=Track(fade(u0, u0 + 0.05)), z=6))
    return layers


PROP_BUILDERS = {"cause_effect": prop_cause_effect, "bars": prop_bars, "steps": prop_steps,
                 "chart": prop_chart, "bulb": prop_bulb, "bubble": prop_bubble}


# ------------------------------------------------------------------ one animated scene
@dataclass
class AnimatedScene:
    """What `compose_animation_scene` returns. It has the same fields that the report builder reads from
    a ComposedScene (layout, labels, warnings ...) and a factory for its frame renderer."""
    scene_id: int
    plan: MotionPlan
    base: Image.Image                        # RGB: background, header, ground line
    layers: list[Layer]
    claim_text: str = ""
    layout: str = ""
    requested_layout: Optional[str] = None
    labels: list = field(default_factory=list)        # nothing is drawn as text
    min_font_used: int = 0
    warnings: list[str] = field(default_factory=list)
    overflow: bool = False

    def make_renderer(self, duration_s: float, audio_s: float, index: int, st: Style) -> "LayerRenderer":
        for layer in self.layers:                      # the jointed figure moves its mouth with the real audio length
            if hasattr(layer, "audio_s"):
                layer.audio_s = audio_s
        return LayerRenderer(self, duration_s, st)


class LayerRenderer:
    """Frames of one animated scene as uint8 arrays (HxWx3), without subtitles."""

    def __init__(self, scene: AnimatedScene, duration_s: float, st: Style = Style()):
        self.scene, self.dur, self.st = scene, max(float(duration_s), 1e-6), st
        self._cache: dict[tuple, Image.Image] = {}

    def _variant(self, i: int, layer: Layer, rot: float, sc: float, sy: float, a: float) -> Image.Image:
        key = (i, round(rot * 2) / 2, round(sc, 2), round(sy, 2), round(a, 2))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        spr = layer.sprite
        if key[2] != 1.0 or key[3] != 1.0:
            spr = spr.resize((max(1, round(spr.width * key[2])), max(1, round(spr.height * key[2] * key[3]))),
                             Image.BILINEAR)
        if key[1]:
            spr = spr.rotate(key[1], resample=Image.BICUBIC)         # about the centre = the pivot
        if key[4] < 1.0:
            spr = spr.copy()
            spr.putalpha(spr.getchannel("A").point(lambda v, f=key[4]: int(v * f)))
        if len(self._cache) > 600:
            self._cache.clear()
        self._cache[key] = spr
        return spr

    def frame(self, t: float) -> np.ndarray:
        u = min(1.0, max(0.0, t / self.dur))
        img = self.scene.base.copy()
        for i, layer in enumerate(self.scene.layers):
            if hasattr(layer, "paint"):                # drawn every frame (stickman.StickmanLayer)
                layer.paint(img, u, u * self.dur, self.dur)
                continue
            a, sc, sy = layer.alpha(u), layer.scale(u), layer.sy(u)
            if a <= 0.01 or sc <= 0.01 or sy <= 0.01:
                continue
            spr = self._variant(i, layer, layer.rot(u), sc, sy, min(1.0, a))
            img.paste(spr, (int(round(layer.x(u) - spr.width / 2)), int(round(layer.y(u) - spr.height / 2))), spr)
        return np.asarray(img)


def compose_animation_scene(scene: Scene, claim_text: str, st: Style = Style(), index: int = 0,
                            total: int = 1) -> AnimatedScene:
    """Build the layers of one scene. Raises ValueError for a position outside the video."""
    plan = plan_motion(scene, index, total)
    w, h = st.size
    accent, accent2 = st.accent(scene.facet), st.accent(scene.facet, 2)
    s = -1 if plan.mirror else 1
    stage = Stage(fx=w - 300 if plan.mirror else 300, cx=440 if plan.mirror else 840, s=s, gy=GROUND_Y,
                  accent=accent, accent2=accent2, energy=plan.energy)

    base = draw_base(st, scene.facet, index, total, accent)
    d = ImageDraw.Draw(base, "RGBA")
    d.line((st.margin, GROUND_Y + 2, w - st.margin, GROUND_Y + 2), fill=(176, 186, 208, 255), width=4)
    d.ellipse((stage.fx - 70, GROUND_Y - 2, stage.fx + 70, GROUND_Y + 12), fill=(120, 130, 155, 70))

    layers = character_layers(stage, plan.pose, role=plan.role, narration=scene.narration) + PROP_BUILDERS[plan.prop](stage)
    layers.sort(key=lambda l: l.z)
    return AnimatedScene(scene_id=scene.scene_id, plan=plan, base=base, layers=layers, claim_text=claim_text,
                         layout=f"cutout:{plan.prop}", requested_layout=scene.layout)


def check_animation(cs: AnimatedScene, st: Style = Style(), samples: int = 6) -> list[str]:
    """Automatic checks on real frames. Returns problems (empty = fine):
    the subtitle band stays untouched, and the scene really moves."""
    problems = []
    renderer = cs.make_renderer(8.0, 8.0, 0, st)
    h = st.size[1]
    band = np.asarray(cs.base)[h - st.sub_h:]
    first = renderer.frame(0.0)
    moved = False
    for i in range(samples + 1):
        fr = renderer.frame(8.0 * i / samples)
        if not np.array_equal(fr[h - st.sub_h:], band):
            problems.append(f"scene {cs.scene_id}: drawing enters the subtitle band")
            break
        moved = moved or not np.array_equal(fr, first)
    if not moved:
        problems.append(f"scene {cs.scene_id}: nothing moves (S11)")
    return problems
