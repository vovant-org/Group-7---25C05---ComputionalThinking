"""Step 3 - the objects the engine can draw, each with the motion that fits what it is.

  animal / bird / fish   walk, fly and swim across the stage (legs swing, wings flap, tails wag)
  tree / sprout          grow from the ground, then sway; the sprout ends in a flower
  planet / earth         a sun in the middle and planets going round it on their orbits
  coin (+ bank/basket)   money circulating on a loop between two places; alone, coins fall into a pile
  tag / bars_up          prices stepping up (or down), bars growing one after another
  cloud / drop / flood   clouds drift and rain, drops fall, flood water rises over the city
  moon / star / bed / brain / clock / heart / chip / signal / book / bulb / rocket / building / sun

Everything is built from the same parts as the generic animation (`Layer` = sprite + keyframe tracks over the
scene fraction u in [0, 1]), so the renderer is shared. Every object starts at `ctx.u0`, the moment the narrator
says its word (sync.py). No text is drawn. Colours and sizes are our own choice (assumption, not measured).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from PIL import Image

from modules.video.animation import (GREY, INK, WHITE, YELLOW, Layer, Track, _circle, _line, _rrect, fade, hold,
                                     join, make_sprite, pop, wiggle)

SKY = (80, 150, 230)
GREEN = (84, 170, 98)
BROWN = (160, 112, 70)


@dataclass(frozen=True)
class Ctx:
    x: float                       # centre of the object's slot
    gy: float                      # ground line (y)
    u0: float                      # moment (fraction of the scene) at which the object appears
    accent: tuple
    accent2: tuple
    energy: float = 1.0
    slot_w: float = 300.0
    x0: float = 100.0              # the whole stage (wide objects use all of it)
    x1: float = 1180.0
    variant: str = ""
    trend: int = 1                 # +1 rising, -1 falling
    partners: tuple = ()           # x of the other objects of the scene (money flows between them)
    rain: bool = False

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2


# ------------------------------------------------------------------ small helpers
_CACHE: dict = {}


def spr(key: tuple, size, pivot, draw) -> Image.Image:
    if key not in _CACHE:
        _CACHE[key] = make_sprite(size, pivot, draw)
    return _CACHE[key]


def _ell(d, k, box, fill=None, outline=None, width=0):
    d.ellipse(tuple(v * k for v in box), fill=fill, outline=outline, width=int(width * k))


def _poly(d, k, pts, fill=None, outline=None):
    d.polygon([(x * k, y * k) for x, y in pts], fill=fill, outline=outline)


def _star_pts(cx, cy, r1, r2, n=5):
    return [(cx + (r1 if i % 2 == 0 else r2) * math.sin(math.pi * i / n),
             cy - (r1 if i % 2 == 0 else r2) * math.cos(math.pi * i / n)) for i in range(2 * n)]


def sample(fn, u0: float, u1: float, n: int = 16) -> tuple:
    u1 = min(1.0, max(u1, u0 + 0.04))
    return tuple((u0 + (u1 - u0) * i / n, fn(i / n)) for i in range(n + 1))


def lin(keys: tuple) -> Track:
    """Linear track through sampled keys (value before the first key = the first value)."""
    return Track(join(((0.0, keys[0][1]),), keys), ease=False)


def offset(keys: tuple, d: float) -> Track:
    return lin(tuple((u, v + d) for u, v in keys))


def periodic(u0: float, period: float, fn, spc: int = 10) -> tuple:
    """Keys of a repeating movement: fn(phase in [0, 1)) sampled `spc` times per period."""
    out, j = [], 0
    while True:
        u = u0 + j * period / spc
        if u > 1.0:
            break
        out.append((u, fn((j % spc) / spc)))
        j += 1
    return tuple(out) if len(out) > 1 else ((u0, fn(0.0)), (min(1.0, u0 + 0.05), fn(0.0)))


def _in(c: Ctx, span: float = 0.05, peak: float = 1.12) -> dict:
    return dict(alpha=Track(fade(c.u0, c.u0 + span)), scale=Track(pop(c.u0, c.u0 + 2.4 * span, peak)))


def _pulse(c: Ctx, amp: float, cycles: float, start: float = 0.15) -> Track:
    return Track(join(pop(c.u0, c.u0 + 0.12, 1.12), wiggle(1.0, amp * c.energy, cycles, c.u0 + start, 1.0, 8)))


def _scl(tr: Track, f: float) -> Track:
    """The same scale track, f times bigger (single-sprite objects drawn at a readable size)."""
    return Track(tuple((u, v * f) for u, v in tr.keys), ease=tr.ease)


def _end(u: float, length: float) -> float:
    return min(1.0, u + length)


def _rain_alpha(phase: float) -> float:
    return max(0.0, min(1.0, phase * 10, (0.92 - phase) * 12))


# ------------------------------------------------------------------ sky and sleep
def moon(c: Ctx) -> list[Layer]:
    body = spr(("moon",), (120, 120), (60, 60), lambda d, k: (
        _circle(d, k, (60, 60), 50, fill=(250, 240, 190), outline=INK, width=5),
        [_circle(d, k, p, r, fill=(232, 218, 160)) for p, r in (((42, 48), 9), ((76, 70), 12), ((66, 36), 6))]))
    glow = spr(("moon_glow",), (210, 210), (105, 105), lambda d, k: _circle(d, k, (105, 105), 100, fill=(255, 250, 210, 70)))
    y, xs = c.gy - 330, sample(lambda f: c.x - 70 + 140 * f, c.u0, 1.0, 12)
    pin = _in(c)
    return [Layer("moon_glow", glow, lin(xs), hold(y), scale=_scl(_pulse(c, 0.08, 3), 1.3), alpha=Track(fade(c.u0, c.u0 + 0.06)), z=3),
            Layer("moon", body, lin(xs), hold(y), scale=_scl(pin["scale"], 1.3), alpha=pin["alpha"], z=4)]


def star(c: Ctx) -> list[Layer]:
    s = spr(("star",), (60, 60), (30, 30), lambda d, k: _poly(d, k, _star_pts(30, 31, 26, 11), fill=YELLOW, outline=INK))
    out = []
    for i, (dx, dy) in enumerate(((-100, -20), (0, 40), (105, -5))):
        u = min(0.8, c.u0 + 0.05 * i)
        out.append(Layer(f"star{i}", s, hold(c.x + dx), hold(c.gy - 330 + dy),
                         alpha=Track(join(fade(u, u + 0.05), wiggle(0.8, 0.2, 3 + i, u + 0.08, 1.0, 6))),
                         scale=_scl(Track(pop(u, u + 0.12, 1.3)), 1.4), rot=Track(((0.0, 0.0), (1.0, 25.0 * (i - 1))), ease=False), z=4))
    return out


def bed(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _rrect(d, k, (10, 92, 250, 118), 6, fill=BROWN, outline=INK, width=4)
        for x in (14, 230):
            _rrect(d, k, (x, 118, x + 16, 150), 3, fill=BROWN, outline=INK, width=3)
        _rrect(d, k, (14, 66, 246, 96), 12, fill=WHITE, outline=INK, width=4)
        _rrect(d, k, (100, 56, 246, 96), 14, fill=c.accent, outline=INK, width=4)
        _rrect(d, k, (22, 52, 84, 80), 12, fill=(236, 240, 250), outline=INK, width=4)
        _circle(d, k, (62, 58), 16, fill=(250, 225, 200), outline=INK, width=4)
    z = spr(("zzz",), (40, 40), (20, 20), lambda d, k: _line(d, k, (6, 8), (32, 8), (60, 50, 130), 6) or _line(d, k, (32, 8), (6, 32), (60, 50, 130), 6)
            or _line(d, k, (6, 32), (32, 32), (60, 50, 130), 6))
    out = [Layer("bed", spr(("bed", c.accent), (260, 150), (130, 150), draw), hold(c.x), hold(c.gy), **_in(c), z=5)]
    for i in range(3):
        u = min(0.85, c.u0 + 0.10 + 0.10 * i)
        ys = periodic(u, 0.32, lambda p, i=i: c.gy - 150 - 150 * p)
        xs = periodic(u, 0.32, lambda p: c.x - 10 + 50 * p)
        al = periodic(u, 0.32, lambda p: _rain_alpha(p))
        out.append(Layer(f"z{i}", z, lin(xs), lin(ys), alpha=lin(al), scale=hold(1.1 + 0.3 * i), z=6))
    return out


def brain(c: Ctx) -> list[Layer]:
    def draw(d, k):
        for box in ((14, 14, 92, 116), (68, 14, 146, 116)):
            _ell(d, k, box, fill=(244, 170, 190), outline=INK, width=5)
        _line(d, k, (80, 20), (80, 110), INK, 4)
        for box in ((28, 30, 64, 62), (96, 30, 132, 62), (30, 66, 66, 100), (94, 66, 130, 100)):
            d.arc(tuple(v * k for v in box), 200, 340, fill=INK, width=int(4 * k))
    dot = spr(("spark",), (24, 24), (12, 12), lambda d, k: _circle(d, k, (12, 12), 9, fill=YELLOW, outline=INK, width=3))
    out = [Layer("brain", spr(("brain",), (160, 130), (80, 65), draw), hold(c.x), hold(c.gy - 270), scale=_scl(_pulse(c, 0.07, 4), 1.35), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=5)]
    for i, (dx, dy) in enumerate(((-70, -70), (0, -90), (72, -66))):
        u = min(0.88, c.u0 + 0.10 + 0.07 * i)
        out.append(Layer(f"spark{i}", dot, hold(c.x + dx), hold(c.gy - 270 + dy), scale=Track(join(pop(u, u + 0.08, 1.4), wiggle(1.0, 0.2, 3, u + 0.1, 1.0, 6))),
                         alpha=Track(fade(u, u + 0.04)), z=6))
    return out


def clock(c: Ctx) -> list[Layer]:
    def face(d, k):
        _circle(d, k, (65, 65), 58, fill=WHITE, outline=INK, width=6)
        for i in range(12):
            a = i * math.pi / 6
            _line(d, k, (65 + 46 * math.sin(a), 65 - 46 * math.cos(a)), (65 + 53 * math.sin(a), 65 - 53 * math.cos(a)), INK, 4)
    mh = spr(("clock_min",), (14, 60), (7, 52), lambda d, k: _line(d, k, (7, 52), (7, 8), INK, 6))
    hh = spr(("clock_hour",), (14, 44), (7, 38), lambda d, k: _line(d, k, (7, 38), (7, 12), INK, 8))
    y, u1 = c.gy - 250, _end(c.u0, 0.9)
    pin = _in(c)
    S = 1.35
    return [Layer("clock", spr(("clock",), (130, 130), (65, 65), face), hold(c.x), hold(y), scale=_scl(pin["scale"], S), alpha=pin["alpha"], z=5),
            Layer("hour", hh, hold(c.x), hold(y), scale=hold(S), rot=Track(((0.0, 0.0), (c.u0, 0.0), (u1, -90.0)), ease=False), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=6),
            Layer("minute", mh, hold(c.x), hold(y), scale=hold(S), rot=Track(((0.0, 0.0), (c.u0, 0.0), (u1, -720.0)), ease=False), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=7)]


def heart(c: Ctx) -> list[Layer]:
    def draw(d, k):
        red = (225, 70, 90)
        _circle(d, k, (38, 38), 28, fill=red)
        _circle(d, k, (82, 38), 28, fill=red)
        _poly(d, k, [(12, 52), (108, 52), (60, 106)], fill=red)
        _circle(d, k, (30, 30), 7, fill=(250, 170, 180))
    return [Layer("heart", spr(("heart",), (120, 110), (60, 55), draw), hold(c.x), hold(c.gy - 230),
                  scale=_scl(Track(join(pop(c.u0, c.u0 + 0.1, 1.2), wiggle(1.0, 0.13 * c.energy, 7, c.u0 + 0.12, 1.0, 8))), 1.4),
                  alpha=Track(fade(c.u0, c.u0 + 0.05)), z=5)]


# ------------------------------------------------------------------ economy
def _coin_sprite():
    def draw(d, k):
        _circle(d, k, (30, 30), 28, fill=YELLOW, outline=INK, width=5)
        _circle(d, k, (30, 30), 18, outline=(210, 160, 30), width=3)
        _line(d, k, (30, 20), (30, 40), (210, 160, 30), 4)
    return spr(("coin",), (60, 60), (30, 30), draw)


def coin(c: Ctx) -> list[Layer]:
    s = _coin_sprite()
    if c.partners:                                          # money circulates between this place and its partner
        a, b = c.x, c.partners[0]
        cx, rx, y, ry = (a + b) / 2, max(60.0, abs(a - b) / 2), c.gy - 120, 95
        u1 = 1.0
        out = []
        for i in range(3):
            ph = i / 3.0
            ang = lambda f, ph=ph: 2 * math.pi * (ph + 1.4 * f)
            xs = sample(lambda f: cx + rx * math.cos(ang(f)), c.u0, u1, 36)
            ys = sample(lambda f: y - ry * math.sin(ang(f)), c.u0, u1, 36)
            pin = _in(c, 0.05 + 0.03 * i)
            out.append(Layer(f"flow{i}", s, lin(xs), lin(ys), scale=_scl(pin["scale"], 1.4), alpha=pin["alpha"], z=7))
        return out
    out = []                                                # alone: coins drop into a pile
    spots = [(-34, 0), (34, 0), (0, -26), (-70, 0), (70, 0)]
    for i, (dx, dy) in enumerate(spots):
        u = min(0.82, c.u0 + 0.07 * i)
        end = c.gy - 30 + dy
        out.append(Layer(f"coin{i}", s, hold(c.x + dx * 1.3), Track(((0.0, end - 330), (u, end - 330), (min(1.0, u + 0.12), end))),
                         scale=hold(1.3), alpha=Track(fade(u, u + 0.03)), z=6 + i))
    return out


def bank(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _poly(d, k, [(8, 62), (105, 8), (202, 62)], fill=c.accent, outline=INK)
        for x in (30, 76, 122, 168):
            _rrect(d, k, (x, 70, x + 22, 140), 4, fill=WHITE, outline=INK, width=4)
        _rrect(d, k, (14, 140, 196, 160), 4, fill=(226, 230, 240), outline=INK, width=4)
        _rrect(d, k, (4, 160, 206, 178), 4, fill=(206, 212, 226), outline=INK, width=4)
    arrow = spr(("up_arrow", c.accent2), (60, 70), (30, 35), lambda d, k: (
        _line(d, k, (30, 58), (30, 14), c.accent2, 12), _line(d, k, (10, 34), (30, 12), c.accent2, 12), _line(d, k, (50, 34), (30, 12), c.accent2, 12)))
    ay = c.gy - 215
    sgn = -1 if c.trend >= 0 else 1
    return [Layer("bank", spr(("bank", c.accent), (210, 180), (105, 180), draw), hold(c.x), hold(c.gy), **_in(c), z=5),
            Layer("rate", arrow, hold(c.x), Track(join(((0.0, ay),), wiggle(ay, sgn * 10 * c.energy, 3, _end(c.u0, 0.15), 1.0, 6))),
                  rot=hold(0.0 if c.trend >= 0 else 180.0), scale=Track(pop(c.u0 + 0.1, c.u0 + 0.2)), alpha=Track(fade(c.u0 + 0.1, c.u0 + 0.16)), z=6)]


def basket(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _poly(d, k, [(15, 60), (155, 60), (135, 146), (35, 146)], fill=(205, 150, 90), outline=INK)
        for x in (50, 85, 120):
            _line(d, k, (x, 64), (x - 10 + (x - 85) // 6, 142), (150, 100, 55), 4)
        d.arc((35 * k, 5 * k, 135 * k, 95 * k), 180, 360, fill=INK, width=int(6 * k))
    items = [("bread", (230, 180, 100)), ("apple", (220, 70, 70)), ("bottle", (120, 190, 240))]
    out = [Layer("basket", spr(("basket",), (170, 150), (85, 150), draw), hold(c.x), hold(c.gy), **_in(c), z=6)]
    for i, (name, col) in enumerate(items):
        s = spr(("item", name), (50, 50), (25, 25), lambda d, k, col=col, name=name: (
            _rrect(d, k, (14, 4, 36, 46), 6, fill=col, outline=INK, width=3) if name == "bottle"
            else _circle(d, k, (25, 25), 18, fill=col, outline=INK, width=3)))
        u = min(0.85, c.u0 + 0.10 * (i + 1))
        x = c.x - 38 + 38 * i
        out.append(Layer(name, s, hold(x), Track(((0.0, c.gy - 320), (u, c.gy - 320), (_end(u, 0.14), c.gy - 112))),
                         alpha=Track(fade(u, u + 0.03)), z=5))
    return out


def tag(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _poly(d, k, [(6, 50), (34, 14), (122, 14), (122, 86), (34, 86)], fill=WHITE, outline=INK)
        _circle(d, k, (36, 50), 7, fill=INK)
        _line(d, k, (62, 38), (106, 38), GREY, 6)
        _line(d, k, (62, 60), (96, 60), GREY, 6)
    low, high = c.gy - 110, c.gy - 290
    ys = [low, (low + high) / 2, high] if c.trend >= 0 else [high, (low + high) / 2, low]
    steps = [(0.0, ys[0]), (c.u0, ys[0])]
    for i in (1, 2):
        u = min(0.97, c.u0 + 0.22 * i)
        steps += [(u, ys[i - 1]), (min(1.0, u + 0.1) if u + 0.1 < 1.0 else 1.0, ys[i])]
    return [Layer("tag", spr(("tag",), (130, 100), (65, 50), draw), hold(c.x), Track(join(steps)),
                  rot=Track(join(((0.0, 0.0),), wiggle(0.0, 6 * c.energy, 3, c.u0 + 0.05, 1.0, 6))),
                  scale=_scl(_in(c)["scale"], 1.4), alpha=_in(c)["alpha"], z=6)]


def bars_up(c: Ctx) -> list[Layer]:
    hs = [60, 100, 150, 210] if c.trend >= 0 else [210, 150, 100, 60]

    def bar(h, color):
        return spr(("bar", h, color), (70, h), (35, h), lambda d, k: _rrect(d, k, (2, 2, 68, h - 1), 8, fill=color, outline=INK, width=4))
    base = spr(("bars_base",), (340, 12), (170, 6), lambda d, k: _line(d, k, (6, 6), (334, 6), INK, 8))
    arrow = spr(("trend_arrow", c.accent2), (60, 70), (30, 35), lambda d, k: (
        _line(d, k, (30, 58), (30, 14), c.accent2, 12), _line(d, k, (10, 34), (30, 12), c.accent2, 12), _line(d, k, (50, 34), (30, 12), c.accent2, 12)))
    out = [Layer("base", base, hold(c.x), hold(c.gy), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=4)]
    for i, h in enumerate(hs):
        u = min(0.8, c.u0 + 0.07 * i)
        out.append(Layer(f"bar{i}", bar(h, c.accent if i == 3 else GREY), hold(c.x - 112 + 75 * i), hold(c.gy),
                         sy=Track(((0.0, 0.0), (u, 0.0), (_end(u, 0.14), 1.0))), z=5))
    u = min(0.85, c.u0 + 0.36)
    out.append(Layer("arrow", arrow, hold(c.x + 113 if c.trend >= 0 else c.x - 112), hold(c.gy - (hs[3 if c.trend >= 0 else 0]) - 40),
                     rot=hold(0.0 if c.trend >= 0 else 180.0), scale=Track(pop(u, u + 0.1, 1.3)), alpha=Track(fade(u, u + 0.05)), z=6))
    return out


# ------------------------------------------------------------------ nature
def _animal_color(c: Ctx) -> tuple:
    return (160, 170, 186) if c.variant == "elephant" else (196, 142, 92)


def animal(c: Ctx) -> list[Layer]:
    col, big = _animal_color(c), c.variant == "elephant"
    body = spr(("body", col), (170, 100), (85, 50), lambda d, k: _ell(d, k, (10, 10, 160, 90), fill=col, outline=INK, width=5))

    def head_draw(d, k):
        _circle(d, k, (40, 40), 28, fill=col, outline=INK, width=5)
        _circle(d, k, (48, 34), 4, fill=INK)
        if big:
            _line(d, k, (62, 46), (72, 90), col, 14)
            _ell(d, k, (6, 18, 34, 60), fill=(140, 150, 168), outline=INK, width=4)
        else:
            _poly(d, k, [(24, 18), (30, -2), (38, 16)], fill=col, outline=INK)
    head = spr(("head", col, big), (80, 100), (14, 60), head_draw)
    leg = spr(("leg", col), (26, 80), (13, 6), lambda d, k: _rrect(d, k, (4, 2, 22, 76), 8, fill=col, outline=INK, width=4))
    tail = spr(("tail", col), (40, 40), (4, 20), lambda d, k: _line(d, k, (4, 20), (34, 8), INK, 6))
    x_a, x_b = c.x0 + 130, c.x1 - 130
    path = sample(lambda f: x_a + (x_b - x_a) * f, c.u0, 1.0, 30)
    by = c.gy - 108
    cycles = max(3.0, 9 * (1.0 - c.u0))
    n = int(cycles * 8)
    swing = lambda ph: Track(join(((0.0, 0.0),), sample(lambda f: 26 * math.sin(2 * math.pi * (cycles * f + ph)), c.u0, 1.0, n)), ease=False)
    bob = Track(join(((0.0, by),), sample(lambda f: by + 5 * abs(math.sin(2 * math.pi * cycles * f)), c.u0, 1.0, n)), ease=False)
    al = Track(fade(c.u0, c.u0 + 0.05))
    out = [Layer("body", body, lin(path), bob, alpha=al, z=6), Layer("head", head, offset(path, 80), offset(tuple((u, v) for u, v in bob.keys), -22), alpha=al,
                                                                    rot=Track(join(((0.0, 0.0),), wiggle(0.0, 5, cycles, c.u0, 1.0, 8))), z=7),
           Layer("tail", tail, offset(path, -82), offset(tuple((u, v) for u, v in bob.keys), -18), alpha=al,
                 rot=Track(join(((0.0, 0.0),), wiggle(0.0, 22, cycles * 1.5, c.u0, 1.0, 8))), z=5)]
    for i, (dx, ph, z) in enumerate(((55, 0.0, 7), (38, 0.5, 5), (-38, 0.5, 7), (-55, 0.0, 5))):
        out.append(Layer(f"leg{i}", leg, offset(path, dx), offset(tuple((u, v) for u, v in bob.keys), 38), rot=swing(ph), alpha=al, z=z))
    return out


def bird(c: Ctx) -> list[Layer]:
    body = spr(("bird",), (110, 60), (55, 30), lambda d, k: (
        _ell(d, k, (4, 12, 80, 50), fill=c.accent, outline=INK, width=4), _circle(d, k, (80, 26), 14, fill=c.accent, outline=INK, width=4),
        _poly(d, k, [(92, 22), (108, 28), (92, 34)], fill=YELLOW, outline=INK), _circle(d, k, (84, 22), 3, fill=INK)))
    wing = spr(("wing", c.accent2), (70, 60), (35, 52), lambda d, k: _poly(d, k, [(35, 52), (5, 6), (65, 12)], fill=c.accent2, outline=INK))
    x_a, x_b = c.x0 + 80, c.x1 - 80
    path = sample(lambda f: x_a + (x_b - x_a) * f, c.u0, 1.0, 30)
    wave = lambda f: c.gy - 300 + 45 * math.sin(2 * math.pi * 1.5 * f)
    ys = sample(wave, c.u0, 1.0, 30)
    flaps = max(4.0, 14 * (1.0 - c.u0))
    flap = Track(join(((0.0, 0.0),), sample(lambda f: 32 * math.sin(2 * math.pi * flaps * f), c.u0, 1.0, int(flaps * 8))), ease=False)
    al = Track(fade(c.u0, c.u0 + 0.05))
    return [Layer("bird", body, lin(path), lin(ys), scale=hold(1.4), alpha=al, z=6),
            Layer("wing", wing, offset(path, -3), offset(ys, -11), scale=hold(1.4), rot=flap, alpha=al, z=7)]


def fish(c: Ctx) -> list[Layer]:
    pond = spr(("pond",), (940, 190), (470, 190), lambda d, k: _rrect(d, k, (0, 0, 940, 190), 40, fill=(70, 150, 225, 175)))
    body = spr(("fish",), (120, 70), (60, 35), lambda d, k: (
        _ell(d, k, (10, 12, 100, 58), fill=(240, 150, 60), outline=INK, width=4), _circle(d, k, (84, 30), 4, fill=INK)))
    tail = spr(("fish_tail",), (50, 60), (4, 30), lambda d, k: _poly(d, k, [(4, 30), (46, 6), (46, 54)], fill=(240, 150, 60), outline=INK))
    x_a, x_b = c.cx - 330, c.cx + 330
    path = sample(lambda f: x_a + (x_b - x_a) * f, c.u0, 1.0, 30)
    ys = sample(lambda f: c.gy - 100 + 36 * math.sin(2 * math.pi * 2.0 * f), c.u0, 1.0, 30)
    wag = Track(join(((0.0, 0.0),), sample(lambda f: 22 * math.sin(2 * math.pi * 9 * (1 - c.u0) * f), c.u0, 1.0, 60)), ease=False)
    al = Track(fade(c.u0, c.u0 + 0.05))
    return [Layer("pond", pond, hold(c.cx), hold(c.gy), alpha=Track(fade(c.u0, c.u0 + 0.06)), z=3),
            Layer("fish", body, lin(path), lin(ys), scale=hold(1.4), alpha=al, z=6),
            Layer("tail", tail, offset(path, -72), lin(ys), scale=hold(1.4), rot=wag, alpha=al, z=5)]


def tree(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _rrect(d, k, (72, 150, 98, 258), 6, fill=BROWN, outline=INK, width=4)
        for p, r, col in (((85, 90), 70, (62, 150, 84)), ((45, 130), 48, (74, 166, 96)), ((125, 130), 48, (74, 166, 96)), ((85, 70), 36, (96, 186, 112))):
            _circle(d, k, p, r, fill=col)
    u1 = _end(c.u0, 0.38)
    return [Layer("tree", spr(("tree",), (170, 260), (85, 260), draw), hold(c.x), hold(c.gy),
                  scale=Track(((0.0, 0.03), (c.u0, 0.05), (u1, 1.0))), alpha=Track(fade(c.u0, c.u0 + 0.04)),
                  rot=Track(join(((0.0, 0.0),), wiggle(0.0, 1.6 * c.energy, 3, _end(u1, 0.02), 1.0, 8))), z=5)]


def sprout(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _line(d, k, (55, 146), (55, 60), GREEN, 8)
        _ell(d, k, (8, 50, 56, 88), fill=(110, 190, 110), outline=INK, width=3)
        _ell(d, k, (54, 36, 102, 74), fill=(110, 190, 110), outline=INK, width=3)
    soil = spr(("soil",), (150, 40), (75, 40), lambda d, k: _ell(d, k, (0, 10, 150, 46), fill=(120, 84, 56), outline=INK, width=4))
    flower = spr(("flower", c.accent2), (60, 60), (30, 30), lambda d, k: (
        [_circle(d, k, (30 + 17 * math.cos(a), 30 + 17 * math.sin(a)), 11, fill=c.accent2, outline=INK, width=2) for a in [i * math.pi * 2 / 5 for i in range(5)]],
        _circle(d, k, (30, 30), 9, fill=YELLOW, outline=INK, width=2)))
    u1 = _end(c.u0, 0.4)
    uf = min(0.9, u1 + 0.02)
    return [Layer("soil", soil, hold(c.x), hold(c.gy + 6), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=4),
            Layer("sprout", spr(("sprout",), (110, 150), (55, 150), draw), hold(c.x), hold(c.gy),
                  scale=Track(((0.0, 0.02), (c.u0, 0.05), (u1, 1.35))), alpha=Track(fade(c.u0, c.u0 + 0.04)),
                  rot=Track(join(((0.0, 0.0),), wiggle(0.0, 3 * c.energy, 3, uf, 1.0, 8))), z=5),
            Layer("flower", flower, hold(c.x), hold(c.gy - 128), scale=Track(pop(uf, uf + 0.1, 1.4)), alpha=Track(fade(uf, uf + 0.04)), z=6)]


def sun(c: Ctx) -> list[Layer]:
    disc = spr(("sun",), (120, 120), (60, 60), lambda d, k: _circle(d, k, (60, 60), 44, fill=YELLOW, outline=INK, width=5))
    rays = spr(("sun_rays",), (260, 260), (130, 130), lambda d, k: [
        _line(d, k, (130 + 62 * math.cos(a), 130 + 62 * math.sin(a)), (130 + 96 * math.cos(a), 130 + 96 * math.sin(a)), (250, 190, 60), 9)
        for a in [i * math.pi / 6 for i in range(12)]])
    y = c.gy - 350
    return [Layer("rays", rays, hold(c.x), hold(y), rot=Track(((0.0, 0.0), (1.0, 70.0)), ease=False), scale=_pulse(c, 0.06, 3), alpha=Track(fade(c.u0, c.u0 + 0.06)), z=3),
            Layer("sun", disc, hold(c.x), hold(y), **_in(c), z=4)]


def _drop_sprite():
    return spr(("drop",), (30, 46), (15, 23), lambda d, k: (_circle(d, k, (15, 31), 13, fill=SKY, outline=INK, width=3),
                                                           _poly(d, k, [(15, 2), (4, 26), (26, 26)], fill=SKY)))


def _rain(c: Ctx, x_lo: float, x_hi: float, y_top: float, n: int = 7) -> list[Layer]:
    s, out = _drop_sprite(), []
    for i in range(n):
        u = min(0.85, c.u0 + 0.025 * i)
        x = x_lo + (x_hi - x_lo) * ((i * 0.618) % 1.0)
        period = 0.20 + 0.01 * (i % 3)
        out.append(Layer(f"drop{i}", s, hold(x), lin(periodic(u, period, lambda p: y_top + (c.gy - 20 - y_top) * p, 12)),
                         alpha=lin(periodic(u, period, _rain_alpha, 12)), z=6))
    return out


def drop(c: Ctx) -> list[Layer]:
    return _rain(c, c.x - c.slot_w * 0.4, c.x + c.slot_w * 0.4, c.gy - 420)


def cloud(c: Ctx) -> list[Layer]:
    col = (168, 178, 198) if c.rain else (246, 249, 255)
    s = spr(("cloud", col), (200, 110), (100, 70), lambda d, k: (
        [_circle(d, k, p, r, fill=col) for p, r in (((60, 60), 36), ((100, 46), 44), ((142, 62), 34))], _rrect(d, k, (40, 60, 170, 96), 18, fill=col)))
    xs = sample(lambda f: c.x - 70 + 140 * f, c.u0, 1.0, 12)
    y = c.gy - 380
    out = [Layer("cloud", s, lin(xs), hold(y), scale=Track(pop(c.u0, c.u0 + 0.12, 1.1)), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=7)]
    if c.rain:
        out += _rain(Ctx(**{**c.__dict__, "u0": min(0.85, c.u0 + 0.12)}), c.x - 90, c.x + 90, y + 40)
    return out


# ------------------------------------------------------------------ space
def planet(c: Ctx) -> list[Layer]:
    cx, cy = c.cx, c.gy - 250
    rx, ry = min(330.0, (c.x1 - c.x0) / 2 - 80), 95.0
    core = spr(("sun_core",), (120, 120), (60, 60), lambda d, k: (_circle(d, k, (60, 60), 46, fill=(250, 190, 60, 110)), _circle(d, k, (60, 60), 34, fill=YELLOW, outline=INK, width=5)))
    orbit = spr(("orbit", int(rx), int(ry)), (int(2 * rx + 12), int(2 * ry + 12)), (int(rx + 6), int(ry + 6)),
                lambda d, k: _ell(d, k, (6, 6, 2 * rx + 6, 2 * ry + 6), outline=(255, 255, 255, 150), width=3))
    earthlike = c.variant == "earth"
    inner = spr(("planet_in", earthlike, c.accent), (60, 60), (30, 30), lambda d, k: (
        _circle(d, k, (30, 30), 26, fill=(70, 140, 220) if earthlike else c.accent, outline=INK, width=4),
        [_poly(d, k, pts, fill=(96, 180, 100)) for pts in ([(16, 22), (26, 16), (28, 28), (18, 32)], [(34, 34), (44, 30), (42, 42)])] if earthlike else None))
    outer = spr(("planet_out", c.accent2), (110, 70), (55, 35), lambda d, k: (
        _circle(d, k, (55, 35), 24, fill=c.accent2, outline=INK, width=4), _ell(d, k, (2, 26, 108, 46), outline=(250, 235, 200), width=5)))
    out = [Layer("orbit", orbit, hold(cx), hold(cy), alpha=Track(fade(c.u0, c.u0 + 0.06)), z=2),
           Layer("core", core, hold(cx), hold(cy), scale=_scl(_pulse(c, 0.05, 3), 1.5), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=4)]
    for name, sp, k_r, turns, phase in (("inner", inner, 0.52, 2.6, 0.1), ("outer", outer, 1.0, 1.2, 0.55)):
        pin = _in(c, 0.05)
        ang = lambda f, t=turns, p=phase: 2 * math.pi * (p + t * f)
        n = int(turns * 28)
        out.append(Layer(name, sp, lin(sample(lambda f: cx + rx * k_r * math.cos(ang(f)), c.u0, 1.0, n)),
                         lin(sample(lambda f: cy + ry * k_r * math.sin(ang(f)), c.u0, 1.0, n)),
                         scale=_scl(pin["scale"], 1.6), alpha=pin["alpha"], z=5))
    return out


def rocket(c: Ctx) -> list[Layer]:
    def draw(d, k):
        _rrect(d, k, (14, 30, 56, 110), 12, fill=WHITE, outline=INK, width=4)
        _poly(d, k, [(14, 34), (35, 0), (56, 34)], fill=c.accent, outline=INK)
        _circle(d, k, (35, 62), 10, fill=(120, 190, 240), outline=INK, width=3)
        _poly(d, k, [(14, 86), (0, 120), (14, 108)], fill=c.accent2, outline=INK)
        _poly(d, k, [(56, 86), (70, 120), (56, 108)], fill=c.accent2, outline=INK)
    flame = spr(("flame",), (40, 60), (20, 0), lambda d, k: _poly(d, k, [(8, 0), (32, 0), (20, 56)], fill=(250, 160, 50), outline=INK))
    a = math.atan2(c.x1 - c.x0 - 260, 340)
    h = (math.sin(a), -math.cos(a))
    p0, p1 = (c.x0 + 130, c.gy - 50), (c.x1 - 140, c.gy - 400)
    xs = sample(lambda f: p0[0] + (p1[0] - p0[0]) * f, c.u0, 1.0, 20)
    ys = sample(lambda f: p0[1] + (p1[1] - p0[1]) * f, c.u0, 1.0, 20)
    rot = -math.degrees(a)
    return [Layer("rocket", spr(("rocket", c.accent, c.accent2), (70, 120), (35, 70), draw), lin(xs), lin(ys), scale=hold(1.5), rot=hold(rot), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=6),
            Layer("flame", flame, offset(xs, -h[0] * 90), offset(ys, -h[1] * 90), rot=hold(rot),
                  scale=_scl(Track(join(((0.0, 0.0),), wiggle(1.0, 0.3, 14, _end(c.u0, 0.02), 1.0, 6))), 1.5), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=5)]


# ------------------------------------------------------------------ city, weather, tech, ideas
def building(c: Ctx) -> list[Layer]:
    specs = [(0.12, 90, 170), (0.36, 112, 240), (0.60, 84, 135), (0.84, 100, 200)]
    out = []
    for i, (fx, w, h) in enumerate(specs):
        def draw(d, k, w=w, h=h):
            _rrect(d, k, (2, 2, w - 2, h - 1), 6, fill=(108, 122, 154), outline=INK, width=4)
            for yy in range(18, h - 22, 30):
                for xx in range(14, w - 24, 26):
                    _rrect(d, k, (xx, yy, xx + 14, yy + 16), 2, fill=(250, 226, 140))
        u = min(0.8, c.u0 + 0.06 * i)
        out.append(Layer(f"b{i}", spr(("building", w, h), (w, h), (w // 2, h), draw), hold(c.x0 + (c.x1 - c.x0) * fx), hold(c.gy),
                         sy=Track(((0.0, 0.02), (u, 0.02), (_end(u, 0.14), 1.0))), z=3))
    return out


def flood(c: Ctx) -> list[Layer]:
    def draw(d, k):
        col = (50, 120, 205, 195)
        _rrect(d, k, (0, 40, 1100, 220), 6, fill=col)
        for x in range(10, 1100, 46):
            _circle(d, k, (x, 40), 18, fill=col)
    ripple = spr(("ripple",), (120, 30), (60, 15), lambda d, k: _ell(d, k, (4, 4, 116, 26), outline=(255, 255, 255, 190), width=3))
    u1 = _end(c.u0, 0.7)
    out = [Layer("water", spr(("flood",), (1100, 220), (550, 220), draw), hold(c.cx), hold(c.gy),
                 sy=Track(((0.0, 0.04), (c.u0, 0.04), (u1, 1.0))), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=8)]
    for i, fx in enumerate((0.2, 0.5, 0.78)):
        u = min(0.9, u1 * 0.9 + 0.03 * i)
        out.append(Layer(f"ripple{i}", ripple, hold(c.x0 + (c.x1 - c.x0) * fx), hold(c.gy - 170 + 6 * i),
                         scale=lin(periodic(u, 0.14, lambda p: 0.5 + 1.0 * p)), alpha=lin(periodic(u, 0.14, lambda p: _rain_alpha(p))), z=9))
    return out


def chip(c: Ctx) -> list[Layer]:
    def draw(d, k):
        for i in range(5):
            p = 34 + 16 * i
            for a, b in (((p, 6), (p, 24)), ((p, 106), (p, 124)), ((6, p), (24, p)), ((106, p), (124, p))):
                _line(d, k, a, b, GREY, 5)
        _rrect(d, k, (24, 24, 106, 106), 10, fill=(40, 70, 90), outline=c.accent, width=5)
        _rrect(d, k, (46, 46, 84, 84), 6, fill=c.accent)
    ring = spr(("chip_ring", c.accent), (200, 200), (100, 100), lambda d, k: _circle(d, k, (100, 100), 94, outline=c.accent + (200,), width=4))
    y = c.gy - 240
    out = [Layer("chip", spr(("chip", c.accent), (130, 130), (65, 65), draw), hold(c.x), hold(y), scale=_scl(_pulse(c, 0.05, 4), 1.6), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=5)]
    for i in range(2):
        u = min(0.88, c.u0 + 0.08 + 0.12 * i)
        out.append(Layer(f"ring{i}", ring, hold(c.x), hold(y), scale=lin(periodic(u, 0.24, lambda p: 0.8 + 1.4 * p)), alpha=lin(periodic(u, 0.24, lambda p: 0.7 * (1 - p))), z=4))
    return out


def signal(c: Ctx) -> list[Layer]:
    node = spr(("node", c.accent), (110, 90), (55, 90), lambda d, k: (
        _rrect(d, k, (6, 4, 104, 66), 10, fill=(40, 70, 90), outline=c.accent, width=5), _rrect(d, k, (22, 18, 88, 52), 4, fill=c.accent),
        _rrect(d, k, (30, 70, 80, 86), 4, fill=GREY, outline=INK, width=3)))
    pkt = spr(("packet", c.accent2), (26, 26), (13, 13), lambda d, k: _rrect(d, k, (2, 2, 24, 24), 5, fill=c.accent2, outline=INK, width=3))
    xa, xb, y = c.x - 250, c.x + 250, c.gy - 100
    pin = _in(c)
    out = [Layer("src", node, hold(xa), hold(c.gy), scale=_scl(pin["scale"], 1.6), alpha=pin["alpha"], z=5),
           Layer("dst", node, hold(xb), hold(c.gy), scale=_scl(pin["scale"], 1.6), alpha=pin["alpha"], z=5)]
    for i in range(4):
        u = min(0.85, c.u0 + 0.06 + 0.03 * i)
        out.append(Layer(f"pkt{i}", pkt, lin(periodic(u, 0.26, lambda p: xa + (xb - xa) * p, 12)), lin(periodic(u, 0.26, lambda p: y - 70 * math.sin(math.pi * p) - 22 * i, 12)),
                         scale=hold(1.6), alpha=lin(periodic(u, 0.26, _rain_alpha, 12)), z=6))
    return out


def book(c: Ctx) -> list[Layer]:
    def page(left: bool):
        def draw(d, k):
            _rrect(d, k, (2, 2, 98, 118), 6, fill=WHITE, outline=INK, width=4)
            for yy in (24, 44, 64, 84):
                _line(d, k, (16, yy), (84, yy), GREY, 5)
        return spr(("page", left), (100, 120), (100 if left else 0, 120), draw)
    u1 = _end(c.u0, 0.3)
    y = c.gy - 40
    return [Layer("page_l", page(True), hold(c.x - 2), hold(y), scale=hold(1.5), rot=Track(((0.0, -55.0), (c.u0, -55.0), (u1, 8.0))), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=5),
            Layer("page_r", page(False), hold(c.x + 2), hold(y), scale=hold(1.5), rot=Track(((0.0, 55.0), (c.u0, 55.0), (u1, -8.0))), alpha=Track(fade(c.u0, c.u0 + 0.04)), z=5)]


def bulb(c: Ctx) -> list[Layer]:
    body = spr(("bulb",), (140, 190), (70, 95), lambda d, k: (
        _circle(d, k, (70, 70), 56, fill=YELLOW, outline=INK, width=6), _rrect(d, k, (46, 118, 94, 150), 6, fill=GREY, outline=INK, width=5),
        _rrect(d, k, (54, 150, 86, 172), 6, fill=GREY, outline=INK, width=5), _line(d, k, (56, 80), (70, 56), INK, 5), _line(d, k, (70, 56), (84, 80), INK, 5)))
    rays = spr(("bulb_rays", c.accent2), (260, 260), (130, 130), lambda d, k: [
        _line(d, k, (130 + 78 * math.cos(a), 130 + 78 * math.sin(a)), (130 + 108 * math.cos(a), 130 + 108 * math.sin(a)), c.accent2, 8)
        for a in [i * math.pi / 4 for i in range(8)]])
    y = c.gy - 190
    return [Layer("rays", rays, hold(c.x), hold(y - 5), rot=Track(((0.0, 0.0), (1.0, 40.0)), ease=False), scale=_pulse(c, 0.07, 3), alpha=Track(fade(c.u0 + 0.1, c.u0 + 0.16)), z=4),
            Layer("bulb", body, hold(c.x), hold(y), scale=_pulse(c, 0.05, 3), alpha=Track(fade(c.u0, c.u0 + 0.05)), z=5)]


# ------------------------------------------------------------------ registry
@dataclass(frozen=True)
class ObjectInfo:
    build: object
    wide: bool = False             # uses the whole stage (walks / flies / orbits / floods across it)
    ground: bool = True            # stands on the ground line (False: drawn in the sky)
    motion: str = ""               # what the content-aware movement is (for reports and tests)


OBJECTS: dict[str, ObjectInfo] = {
    "moon": ObjectInfo(moon, ground=False, motion="drifts across the night sky"),
    "star": ObjectInfo(star, ground=False, motion="twinkles"),
    "bed": ObjectInfo(bed, motion="a sleeper's Zs float up"),
    "brain": ObjectInfo(brain, ground=False, motion="pulses, ideas spark"),
    "clock": ObjectInfo(clock, ground=False, motion="hands turn"),
    "heart": ObjectInfo(heart, ground=False, motion="beats"),
    "coin": ObjectInfo(coin, motion="circulates (with a partner) / falls into a pile"),
    "bank": ObjectInfo(bank, motion="rate arrow bobs"),
    "basket": ObjectInfo(basket, motion="goods drop in"),
    "tag": ObjectInfo(tag, ground=False, motion="price steps up or down"),
    "bars_up": ObjectInfo(bars_up, motion="bars grow one after another"),
    "animal": ObjectInfo(animal, wide=True, motion="walks, legs swing"),
    "bird": ObjectInfo(bird, wide=True, ground=False, motion="flies, wings flap"),
    "fish": ObjectInfo(fish, wide=True, motion="swims, tail wags"),
    "tree": ObjectInfo(tree, motion="grows, then sways"),
    "sprout": ObjectInfo(sprout, motion="sprouts, then blooms"),
    "sun": ObjectInfo(sun, ground=False, motion="rays turn"),
    "drop": ObjectInfo(drop, motion="drops fall"),
    "cloud": ObjectInfo(cloud, ground=False, motion="drifts and rains"),
    "planet": ObjectInfo(planet, wide=True, ground=False, motion="planets orbit the sun"),
    "earth": ObjectInfo(lambda c: planet(Ctx(**{**c.__dict__, "variant": "earth"})), wide=True, ground=False, motion="the Earth orbits the sun"),
    "rocket": ObjectInfo(rocket, wide=True, ground=False, motion="flies up"),
    "building": ObjectInfo(building, wide=True, motion="the city rises"),
    "flood": ObjectInfo(flood, wide=True, motion="water rises"),
    "chip": ObjectInfo(chip, ground=False, motion="pulses, rings spread"),
    "signal": ObjectInfo(signal, motion="data packets travel"),
    "book": ObjectInfo(book, motion="opens"),
    "bulb": ObjectInfo(bulb, ground=False, motion="lights up"),
}
