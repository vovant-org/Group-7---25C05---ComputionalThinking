"""Infographic Composer (report 5.4, 5.9.9): one scene -> a drawn frame split into reveal steps.

Every piece of text and every number is drawn by code (Pillow) from the claim, never by an image
model (report 1.2.4, option J2 of 5.9.9: Pillow instead of SVG -> headless browser, because it needs
no browser and no extra system library; the price is that we wrap and measure text ourselves).

Layouts: cause_chain, compare_2col, steps, loop, big_number, trend_chart (report 5.2 / M14).
  * trend_chart needs at least two figures WITH a unit (%, $, percent) in the claim: we never plot
    numbers that are not in the verified claim. Without them the scene falls back to cause_chain.
  * big_number needs a number in the claim, otherwise it falls back to cause_chain.
Text that does not fit is handled in the order of the report: K1 shrink the font down to
`min_font`, K3 split the label into two reveal steps (one more box), K2 shorten with an ellipsis.

Each ELEMENT is one reveal step (a card, its arrow, its number badge). The renderer shows elements one
by one in step with the narration (REVEAL) or all at once (STATIC, PAN).

ASSUMPTIONS (to-do item 13 of the report, not measured): min_font = 26 px at 720p; the palette and
sizes are our own choice. Icons are not generated (no image provider): numbered badges and arrows
are drawn instead.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from core.models import Label, Scene
from modules.video import labels as L
from modules.video.fonts import get_font

KNOWN_LAYOUTS = ("cause_chain", "compare_2col", "steps", "loop", "big_number", "trend_chart")
MAX_CHUNKS = {"cause_chain": 3, "compare_2col": 2, "steps": 4, "loop": 3}

_ACCENTS = [(46, 125, 210), (38, 166, 120), (224, 138, 30), (176, 72, 162), (214, 69, 69), (0, 150, 170)]


@dataclass(frozen=True)
class Style:
    size: tuple[int, int] = (1280, 720)
    margin: int = 60
    header_h: int = 100
    sub_h: int = 120                       # bottom band kept free for subtitles
    min_font: int = 26                     # ASSUMPTION: minimum label height at 720p
    max_font: int = 40
    bg_top: tuple = (247, 248, 252)
    bg_bottom: tuple = (226, 233, 246)
    ink: tuple = (28, 34, 48)
    white: tuple = (255, 255, 255)

    @property
    def area(self) -> tuple[int, int, int, int]:
        w, h = self.size
        return (self.margin, self.header_h + 12, w - self.margin, h - self.sub_h - 18)

    def accent(self, facet: str, shift: int = 0) -> tuple:
        return _ACCENTS[(sum(ord(c) for c in facet) + shift) % len(_ACCENTS)]


@dataclass
class Element:
    """One reveal step: a cropped RGBA piece of the frame and where it goes."""
    x: int
    y: int
    image: Image.Image                      # RGBA
    words: int                              # narration words it stands for (reveal timing)
    text: str
    rgb: np.ndarray = field(init=False, repr=False)       # float32 HxWx3
    alpha: np.ndarray = field(init=False, repr=False)     # float32 HxWx1

    def __post_init__(self):
        arr = np.asarray(self.image, dtype=np.float32)
        self.rgb, self.alpha = arr[:, :, :3], arr[:, :, 3:4] / 255.0


@dataclass
class ComposedScene:
    scene_id: int
    layout: str                             # layout actually drawn
    requested_layout: Optional[str]
    base: Image.Image                       # RGB: background, header, progress bar
    elements: list[Element]
    labels: list[Label]
    min_font_used: int
    claim_text: str = ""
    warnings: list[str] = field(default_factory=list)
    overflow: bool = False                  # True when text still did not fit after K1 -> K3 -> K2
    has_art: bool = False                   # True when an AI picture of the claim is on screen (layout ai_visual)
    base_arr: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        self.base_arr = np.asarray(self.base, dtype=np.uint8).copy()


# ------------------------------------------------------------------ text fitting (K1)
def wrap(text: str, font, max_w: float) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        trial = w if not cur else f"{cur} {w}"
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(text: str, box_w: float, box_h: float, start: int, min_size: int, bold: bool = False,
             gap: float = 1.28) -> tuple[list[str], int, bool]:
    """K1: largest font in [min_size, start] whose wrapped text fits the box. Returns (lines, size, fits)."""
    size = start
    while True:
        font = get_font(size, bold)
        lines = wrap(text, font, box_w)
        widest = max((font.getlength(x) for x in lines), default=0)
        if len(lines) * size * gap <= box_h and widest <= box_w:
            return lines, size, True
        if size <= min_size:
            return lines, size, False
        size -= 2


def _draw_lines(draw, lines, size, box, bold=False, color=(28, 34, 48), align="left", gap=1.28):
    x0, y0, x1, y1 = box
    font = get_font(size, bold)
    total = len(lines) * size * gap
    y = y0 + (y1 - y0 - total) / 2
    for line in lines:
        w = font.getlength(line)
        x = x0 if align == "left" else (x0 + x1 - w) / 2
        draw.text((x, y + size * (gap - 1) / 2), line, font=font, fill=color)
        y += size * gap


def _text_box(draw, text, box, st: Style, start=None, bold=False, color=None, align="left", pad=22):
    x0, y0, x1, y1 = box
    inner = (x0 + pad, y0 + pad // 2, x1 - pad, y1 - pad // 2)
    lines, size, ok = fit_text(text, inner[2] - inner[0], inner[3] - inner[1], start or st.max_font,
                               st.min_font, bold)
    _draw_lines(draw, lines, size, inner, bold, color or st.ink, align)
    return size, ok


# ------------------------------------------------------------------ drawing helpers
def _layer(st: Style) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", st.size, (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def _card(d, box, st: Style, outline, fill=None, radius=22):
    x0, y0, x1, y1 = box
    d.rounded_rectangle((x0 + 5, y0 + 7, x1 + 5, y1 + 7), radius, fill=(20, 30, 60, 40))
    d.rounded_rectangle(box, radius, fill=fill or st.white + (255,), outline=outline + (255,), width=4)


def _badge(d, cx, cy, r, n, color, st: Style, font_px=30):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (255,))
    font = get_font(font_px, True)
    s = str(n)
    d.text((cx - font.getlength(s) / 2, cy - font_px * 0.62), s, font=font, fill=st.white + (255,))


def _arrow(d, x0, y0, x1, y1, color, width=10, head=26):
    ang = math.atan2(y1 - y0, x1 - x0)
    bx, by = x1 - head * math.cos(ang), y1 - head * math.sin(ang)
    d.line((x0, y0, bx, by), fill=color + (255,), width=width)
    px, py = -math.sin(ang), math.cos(ang)
    d.polygon([(x1, y1), (bx + px * head * 0.62, by + py * head * 0.62),
               (bx - px * head * 0.62, by - py * head * 0.62)], fill=color + (255,))


def _crop(layer: Image.Image, words: int, text: str) -> Optional[Element]:
    box = layer.getbbox()
    if box is None:
        return None
    return Element(box[0], box[1], layer.crop(box), words, text)


@dataclass
class _Built:
    elements: list[Element]
    overflow: list[int]                     # chunk indices that did not fit at min_font
    min_font: int


def _words(text: str) -> int:
    return max(1, len(text.split()))


# ------------------------------------------------------------------ layouts
def _single_card(chunks, st: Style, accent, **_) -> _Built:
    x0, y0, x1, y1 = st.area
    img, d = _layer(st)
    box = (x0 + 60, y0 + 70, x1 - 60, y1 - 70)
    _card(d, box, st, accent)
    size, ok = _text_box(d, chunks[0], box, st, start=44, align="center", pad=40)
    el = _crop(img, _words(chunks[0]), chunks[0])
    return _Built([el], [] if ok else [0], size)


def _cause_chain(chunks, st: Style, accent, **_) -> _Built:
    if len(chunks) == 1:
        return _single_card(chunks, st, accent)
    x0, y0, x1, y1 = st.area
    k = len(chunks)
    gap = 120 if k == 2 else 90
    w = (x1 - x0 - (k - 1) * gap) // k
    h, top = 300, y0 + (y1 - y0 - 300) // 2
    els, bad, minf = [], [], st.max_font
    for i, text in enumerate(chunks):
        img, d = _layer(st)
        bx = x0 + i * (w + gap)
        box = (bx, top, bx + w, top + h)
        _card(d, box, st, accent)
        if i > 0:
            _arrow(d, bx - gap + 14, top + h // 2, bx - 10, top + h // 2, accent)
        _badge(d, bx + 6, top + 6, 24, i + 1, accent, st)
        size, ok = _text_box(d, text, box, st)
        minf = min(minf, size)
        if not ok:
            bad.append(i)
        els.append(_crop(img, _words(text), text))
    return _Built(els, bad, minf)


def _compare_2col(chunks, st: Style, accent, **_) -> _Built:
    if len(chunks) == 1:
        return _single_card(chunks, st, accent)
    x0, y0, x1, y1 = st.area
    gap = 80
    w = (x1 - x0 - gap) // 2
    top, h = y0 + 10, (y1 - y0) - 20
    els, bad, minf = [], [], st.max_font
    for i, text in enumerate(chunks[:2]):
        img, d = _layer(st)
        bx = x0 + i * (w + gap)
        col = accent if i == 0 else (214, 120, 40)
        box = (bx, top, bx + w, top + h)
        _card(d, box, st, col)
        d.rounded_rectangle((bx, top, bx + w, top + 62), 22, fill=col + (255,))
        d.rectangle((bx, top + 40, bx + w, top + 62), fill=col + (255,))
        d.text((bx + w // 2 - 12, top + 10), "AB"[i], font=get_font(36, True), fill=st.white + (255,))
        if i == 1:
            cx, cy = bx - gap // 2, top + h // 2
            d.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), fill=st.ink + (255,))
            f = get_font(28, True)
            d.text((cx - f.getlength("VS") / 2, cy - 18), "VS", font=f, fill=st.white + (255,))
        size, ok = _text_box(d, text, (bx, top + 70, bx + w, top + h), st, align="center", pad=34)
        minf = min(minf, size)
        if not ok:
            bad.append(i)
        els.append(_crop(img, _words(text), text))
    return _Built(els, bad, minf)


def _steps(chunks, st: Style, accent, **_) -> _Built:
    if len(chunks) == 1:
        return _single_card(chunks, st, accent)
    x0, y0, x1, y1 = st.area
    k = len(chunks)
    gap = 14
    row_h = min(104, (y1 - y0 - (k - 1) * gap) // k)
    top = y0 + ((y1 - y0) - (k * row_h + (k - 1) * gap)) // 2
    els, bad, minf = [], [], st.max_font
    for i, text in enumerate(chunks):
        img, d = _layer(st)
        y = top + i * (row_h + gap)
        box = (x0 + 90, y, x1, y + row_h)
        _card(d, box, st, accent, radius=18)
        _badge(d, x0 + 38, y + row_h // 2, 34, i + 1, accent, st, 34)
        size, ok = _text_box(d, text, box, st, start=36, pad=30)
        minf = min(minf, size)
        if not ok:
            bad.append(i)
        els.append(_crop(img, _words(text), text))
    return _Built(els, bad, minf)


def _loop(chunks, st: Style, accent, **_) -> _Built:
    if len(chunks) < 3:
        return _cause_chain(chunks, st, accent)
    x0, y0, x1, y1 = st.area
    w, h = 470, 150
    boxes = [(x0 + (x1 - x0 - w) // 2, y0, 0, y0 + h),
             (x1 - w - 10, y1 - h - 10, 0, y1 - 10),
             (x0 + 10, y1 - h - 10, 0, y1 - 10)]
    boxes = [(b[0], b[1], b[0] + w, b[3]) for b in boxes]
    centers = [((b[0] + b[2]) // 2, (b[1] + b[3]) // 2) for b in boxes]
    arrows = [((boxes[0][2] - 40, boxes[0][3] + 6), (boxes[1][0] + w // 2 + 60, boxes[1][1] - 8)),
              ((boxes[1][0] - 8, centers[1][1]), (boxes[2][2] + 8, centers[2][1])),
              ((boxes[2][0] + w // 2 - 60, boxes[2][1] - 8), (boxes[0][0] + 40, boxes[0][3] + 6))]
    els, bad, minf = [], [], st.max_font
    for i, text in enumerate(chunks[:3]):
        img, d = _layer(st)
        _card(d, boxes[i], st, accent)
        _badge(d, boxes[i][0] + 6, boxes[i][1] + 6, 22, i + 1, accent, st, 26)
        a, b = arrows[(i - 1) % 3]
        if i > 0:
            _arrow(d, a[0], a[1], b[0], b[1], accent, 9, 24)
        if i == 2:                          # closing arrow back to step 1 appears with the last step
            a2, b2 = arrows[2]
            _arrow(d, a2[0], a2[1], b2[0], b2[1], accent, 9, 24)
        size, ok = _text_box(d, text, boxes[i], st, start=34, pad=26)
        minf = min(minf, size)
        if not ok:
            bad.append(i)
        els.append(_crop(img, _words(text), text))
    return _Built(els, bad, minf)


def _big_number(chunks, st: Style, accent, claim_text="", **_) -> _Built:
    number = L.main_number(claim_text) or "?"
    x0, y0, x1, y1 = st.area
    img, d = _layer(st)
    f_size = 170
    while get_font(f_size, True).getlength(number) > 470 and f_size > 60:
        f_size -= 8
    f = get_font(f_size, True)
    d.text((x0 + 20 + (470 - f.getlength(number)) / 2, y0 + (y1 - y0) / 2 - f_size * 0.62), number, font=f,
           fill=accent + (255,))
    el_num = _crop(img, 1, number)
    img2, d2 = _layer(st)
    box = (x0 + 520, y0 + 50, x1, y1 - 50)
    _card(d2, box, st, accent)
    size, ok = _text_box(d2, chunks[0], box, st, start=38, pad=34)
    return _Built([el_num, _crop(img2, _words(chunks[0]), chunks[0])], [] if ok else [1], size)


def _trend_chart(chunks, st: Style, accent, claim_text="", **_) -> _Built:
    figs = L.extract_figures(claim_text)
    vals = [L.figure_value(f) for f in figs]
    x0, y0, x1, y1 = st.area
    img, d = _layer(st)
    cx0, cy0, cx1, cy1 = x0 + 40, y0 + 20, x1 - 40, y0 + 270
    d.line((cx0, cy1, cx1, cy1), fill=(120, 130, 150, 255), width=3)
    d.line((cx0, cy0, cx0, cy1), fill=(120, 130, 150, 255), width=3)
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    pts = [(cx0 + 60 + i * (cx1 - cx0 - 120) / max(1, len(vals) - 1),
            cy1 - 30 - (v - lo) / span * (cy1 - cy0 - 90)) for i, v in enumerate(vals)]
    d.line(pts, fill=accent + (255,), width=8, joint="curve")
    f = get_font(30, True)
    for (px, py), label in zip(pts, figs):
        d.ellipse((px - 11, py - 11, px + 11, py + 11), fill=accent + (255,), outline=st.white + (255,), width=3)
        d.text((px - f.getlength(label) / 2, py - 48), label, font=f, fill=st.ink + (255,))
    el_chart = _crop(img, max(1, len(figs)), " ".join(figs))
    img2, d2 = _layer(st)
    box = (x0, cy1 + 24, x1, y1)
    _card(d2, box, st, accent)
    size, ok = _text_box(d2, chunks[0], box, st, start=34, pad=30)
    return _Built([el_chart, _crop(img2, _words(chunks[0]), chunks[0])], [] if ok else [1], size)


ART_W = 500


def _ai_visual(chunks, st: Style, accent, art: Optional[Image.Image] = None, **_) -> _Built:
    """AI picture of the claim on the left, the claim itself (text drawn by code) on the right."""
    x0, y0, x1, y1 = st.area
    top, bot = y0 + 10, y1 - 10
    box = (x0, top, x0 + ART_W, bot)
    w, h = box[2] - box[0], box[3] - box[1]
    img, d = _layer(st)
    d.rounded_rectangle((box[0] + 5, box[1] + 7, box[2] + 5, box[3] + 7), 22, fill=(20, 30, 60, 40))
    rgb = art.convert("RGB")
    # Fit the WHOLE picture (never crop its edges); the margin is filled with the picture's own background colour,
    # so an AI picture on a plain background blends into the panel instead of losing the pot / hands / mountain tops.
    bg = rgb.getpixel((min(3, rgb.width - 1), min(3, rgb.height - 1)))
    pic = ImageOps.pad(rgb, (w, h), Image.LANCZOS, color=bg, centering=(0.5, 0.5)).convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), 22, fill=255)
    img.paste(pic, (box[0], box[1]), mask)
    d.rounded_rectangle(box, 22, outline=accent + (255,), width=4)
    el_pic = _crop(img, 1, "")
    img2, d2 = _layer(st)
    tbox = (x0 + ART_W + 40, top, x1, bot)
    _card(d2, tbox, st, accent)
    size, ok = _text_box(d2, chunks[0], tbox, st, start=40, pad=34)
    return _Built([el_pic, _crop(img2, _words(chunks[0]), chunks[0])], [] if ok else [0], size)


_LAYOUT_FN: dict[str, Callable[..., _Built]] = {
    "cause_chain": _cause_chain, "compare_2col": _compare_2col, "steps": _steps, "loop": _loop,
    "big_number": _big_number, "trend_chart": _trend_chart, "ai_visual": _ai_visual}


# ------------------------------------------------------------------ choosing layout and chunks
def resolve_layout(requested: Optional[str], text: str) -> tuple[str, str]:
    """(layout to draw, note). Falls back instead of inventing data (see module docstring)."""
    layout = requested
    if layout is None:                                       # analogy: report 5.2 'big_number or loop'
        layout = "big_number" if L.main_number(text) else "loop"
    if layout not in KNOWN_LAYOUTS:
        return "cause_chain", f"unknown layout {requested!r}, drew cause_chain"
    if layout == "big_number" and not L.main_number(text):
        return "cause_chain", "big_number needs a number in the claim; drew cause_chain"
    if layout == "trend_chart" and len(L.extract_figures(text)) < 2:
        return "cause_chain", "trend_chart needs two figures with a unit in the claim; drew cause_chain"
    return layout, ""


def initial_chunks(layout: str, text: str) -> list[str]:
    n = len(text.split())
    if layout == "cause_chain":
        k = 3 if L.natural_cuts(text, L.CAUSE_CONN) >= 2 and n >= 22 else 2
        return L.split_chunks(text, k, L.CAUSE_CONN, prefer="connector")
    if layout == "compare_2col":
        return L.split_chunks(text, 2, L.COMPARE_CONN, prefer="connector")
    if layout == "steps":
        return L.split_natural(text, 4, L.STEP_CONN, min_words=4)
    if layout == "loop":
        return L.split_natural(text, 3, L.LOOP_CONN, min_words=3)
    return [L.clean_chunk(text)]


# ------------------------------------------------------------------ background and header
def draw_base(st: Style, facet: str, index: int, total: int, accent: tuple) -> Image.Image:
    w, h = st.size
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top, bot = np.array(st.bg_top, np.float32), np.array(st.bg_bottom, np.float32)
    arr = np.broadcast_to(top * (1 - t) + bot * t, (h, w, 3)).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, int(w * (index + 1) / max(1, total)), 8), fill=accent)       # progress bar
    chip = facet.replace("_", " ").upper()
    f = get_font(24, True)
    cw = int(f.getlength(chip)) + 40
    d.rounded_rectangle((st.margin, 34, st.margin + cw, 76), 21, fill=accent)
    d.text((st.margin + 20, 40), chip, font=f, fill=st.white)
    counter = f"{index + 1} / {total}"
    d.text((w - st.margin - get_font(24).getlength(counter), 42), counter, font=get_font(24), fill=(90, 100, 120))
    return img


# ------------------------------------------------------------------ public API
def compose_scene(scene: Scene, claim_text: str, st: Style = Style(), index: int = 0,
                  total: int = 1, art: Optional[Image.Image] = None) -> ComposedScene:
    """Draw the scene. Text comes only from `claim_text`; labels list exactly what was drawn.
    `art`: an AI picture of the claim (modules/ai). With it the scene uses the `ai_visual` layout."""
    if art is not None:
        layout, note = "ai_visual", ""
    else:
        layout, note = resolve_layout(scene.layout, claim_text)
    warnings = [note] if note else []
    accent = st.accent(scene.facet)
    chunks = [L.clean_chunk(claim_text)] if art is not None else initial_chunks(layout, claim_text)
    if layout == "loop" and len(chunks) < 3:                 # a loop needs three natural parts
        layout = "cause_chain"
        chunks = initial_chunks(layout, claim_text)
        warnings.append("loop needs three natural parts in the claim; drew cause_chain")
    fn = _LAYOUT_FN[layout]
    max_k = MAX_CHUNKS.get(layout, 1)

    built = fn(chunks, st, accent, claim_text=claim_text, art=art)
    for _ in range(2):                                      # K3: split an overflowing label (at most 2 retries)
        if not built.overflow or len(chunks) >= max_k or layout in ("big_number", "trend_chart"):
            break
        i = built.overflow[0]
        parts = L.split_in_two(chunks[i])
        if len(parts) < 2:
            break
        chunks = chunks[:i] + parts + chunks[i + 1:]
        warnings.append(f"K3: split an overflowing label into {len(parts)} steps")
        built = fn(chunks, st, accent, claim_text=claim_text, art=art)
    shrink = 0
    while built.overflow and shrink < 8:                    # K2: last resort, shorten (still a prefix of the claim)
        i = built.overflow[0]
        chunks[i] = L.shorten_to_words(chunks[i], max(3, len(chunks[i].split()) - 2))
        shrink += 1
        built = fn(chunks, st, accent, claim_text=claim_text, art=art)
        if shrink == 1:
            warnings.append("K2: shortened a label that did not fit at the minimum font")
    overflow = bool(built.overflow)
    if overflow:
        warnings.append("label still overflows after K1 -> K3 -> K2")

    elements = [e for e in built.elements if e is not None]
    if layout == "big_number":
        shown = [L.main_number(claim_text) or "", chunks[0]]
    elif layout == "trend_chart":
        shown = list(L.extract_figures(claim_text)) + [chunks[0]]
    else:
        shown = list(chunks)
    cid = scene.claim_ids[0] if scene.claim_ids else ""
    return ComposedScene(scene_id=scene.scene_id, layout=layout, requested_layout=scene.layout,
                         base=draw_base(st, scene.facet, index, total, accent), elements=elements,
                         labels=[Label(t, cid) for t in shown if t], min_font_used=built.min_font,
                         claim_text=claim_text, warnings=warnings, overflow=overflow, has_art=art is not None)


def static_frame(cs: ComposedScene) -> np.ndarray:
    """The finished frame (all elements visible) as a uint8 HxWx3 array."""
    out = cs.base_arr.copy()
    for el in cs.elements:
        h, w = el.alpha.shape[:2]
        reg = out[el.y:el.y + h, el.x:el.x + w].astype(np.float32)
        out[el.y:el.y + h, el.x:el.x + w] = (reg * (1 - el.alpha) + el.rgb * el.alpha).astype(np.uint8)
    return out


def check_labels(cs: ComposedScene) -> list[str]:
    """Automatic S15 check: every label comes from the claim; nothing overflows. Returns problems."""
    problems = []
    for lab in cs.labels:
        if not L.label_supported(lab.text.rstrip("…"), cs.claim_text):
            problems.append(f"scene {cs.scene_id}: label {lab.text!r} is not in the claim")
    if cs.overflow:
        problems.append(f"scene {cs.scene_id}: text overflows")
    return problems
