"""Subtitles (report 5.9.8, option H1): cues cut from the narration, timed in proportion to length.

H1 spreads the real audio duration of a scene over its cues by character count. It is the simple
option; H2 (timestamps from the TTS) would be more exact and is not used here. The SRT file is also
muxed into the MP4 as a soft subtitle track, and optionally burned into the picture (always
readable, no player support needed).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw

from modules.video import labels as L
from modules.video.composer import Style, fit_text
from modules.video.fonts import get_font
from modules.voice_segmenter.segmenter import split_sentences

MAX_CUE_WORDS = 12


@dataclass(frozen=True)
class Cue:
    text: str
    start_s: float
    end_s: float


def cue_texts(narration: str, max_words: int = MAX_CUE_WORDS) -> list[str]:
    """Sentences, each cut at natural boundaries when longer than `max_words`."""
    out: list[str] = []
    for sentence in split_sentences(narration):
        n = len(sentence.split())
        if n <= max_words:
            out.append(sentence.strip())
        else:
            parts = L.split_chunks(sentence, math.ceil(n / max_words), L.LOOP_CONN | L.COMPARE_CONN | L.STEP_CONN)
            out.extend(p for p in parts if p)
    return out


def make_cues(entries) -> list[Cue]:
    """One list of cues for the whole timeline (H1: proportional to characters)."""
    cues: list[Cue] = []
    for e in entries:
        texts = cue_texts(e.narration)
        if not texts:
            continue
        total_chars = sum(len(t) for t in texts)
        t = e.start_s
        for text in texts:
            d = e.audio_duration_s * len(text) / total_chars
            cues.append(Cue(text, round(t, 3), round(t + d, 3)))
            t += d
    return cues


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: Sequence[Cue]) -> str:
    return "".join(f"{i}\n{srt_time(c.start_s)} --> {srt_time(c.end_s)}\n{c.text}\n\n"
                   for i, c in enumerate(cues, 1))


def cue_band(text: str, st: Style = Style()) -> tuple[np.ndarray, np.ndarray]:
    """Burned-in subtitle: (rgb float32, alpha float32) of the bottom band (sub_h x width)."""
    w, h = st.size[0], st.sub_h
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, h), fill=(10, 14, 26, 170))
    lines, size, _ = fit_text(text, w - 140, h - 24, 34, st.min_font)
    font = get_font(size)
    total = len(lines) * size * 1.25
    y = (h - total) / 2
    for line in lines:
        d.text(((w - font.getlength(line)) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += size * 1.25
    arr = np.asarray(img, dtype=np.float32)
    return arr[:, :, :3], arr[:, :, 3:4] / 255.0
