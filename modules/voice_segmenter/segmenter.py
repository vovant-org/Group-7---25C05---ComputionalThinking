"""Voice Segmenter (report 4(f), 5.7, 5.9.6; criterion S19).

Cuts the narration script into voice units: 1-2 consecutive sentences, about 10-12 s each,
a sentence is never split. Three algorithms are kept side by side for the benchmark:

  F1_greedy        sequential greedy, exactly the pseudocode of report 5.7
  F2_dp_deviation  DP minimising sum |duration - 11 s|            (report 5.9.6 "F2")
  F3_dp_band       DP minimising (#voices outside [10, 12] s, then sum |duration - 11 s|)
                   -> optimises the S19 metric itself; the last voice may be shorter.
  F4_dp_share      like F3 but ties are broken towards MORE in-band voices (see counter-example)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from core import config as C


@dataclass(frozen=True)
class VoiceParams:
    wpm: float = C.VOICE_WPM
    v_min: float = C.VOICE_MIN_S
    v_max: float = C.VOICE_MAX_S
    v_target: float = C.VOICE_TARGET_S
    max_sentences: int = C.VOICE_MAX_SENTENCES
    tol: float = C.VOICE_TOL_S
    pause_s: float = 0.0       # pause per sentence added to the estimate (0 = report formula)


@dataclass(frozen=True)
class VoiceUnit:
    sentences: tuple[str, ...]
    words: int
    est_s: float

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


@dataclass
class VoiceSegmentation:
    units: list[VoiceUnit]
    needs_shorten: list[int]      # indices of units longer than v_max + tol (back to the Segmenter)
    algorithm: str


# ------------------------------------------------------------------ sentences
_ABBR = {"mr", "mrs", "ms", "dr", "prof", "vs", "etc", "e.g", "i.e", "st", "no",
         "tp", "pgs", "gs", "ts", "ths"}
_TERMINATOR = re.compile(r"[.!?…]+[\"”’)\]]*\s+")


def split_sentences(text: str) -> list[str]:
    """Deterministic splitter for English and Vietnamese narration.

    A boundary needs terminator + whitespace + an uppercase letter/digit/quote, and the word
    before it must not be a known abbreviation. "3.5%" and "TP.HCM" have no space after the dot,
    so they are never split.
    """
    text = " ".join(text.split())
    out: list[str] = []
    start = 0
    for m in _TERMINATOR.finditer(text):
        nxt = text[m.end():m.end() + 1]
        if not nxt or not (nxt.isupper() or nxt.isdigit() or nxt in "\"“‘("):
            continue
        prev = re.findall(r"[^\W\d_]+(?:\.[^\W\d_]+)*$", text[start:m.start()].lower())
        if m.group().startswith(".") and prev and prev[-1] in _ABBR:
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


# ---------------------------------------------------------------------- units
def make_unit(sentences, wpm: float, pause_s: float = 0.0) -> VoiceUnit:
    """Estimated duration = words / wpm * 60 + pause_s per sentence."""
    words = sum(len(s.split()) for s in sentences)
    return VoiceUnit(tuple(sentences), words, words * 60.0 / wpm + pause_s * len(sentences))


def expected_voice_count(t_target: float, p: VoiceParams = VoiceParams()) -> tuple[int, int]:
    """Report 4(f): from T/12 to T/10, rounded to whole numbers (90 s -> 8..9)."""
    return math.ceil(t_target / p.v_max), math.floor(t_target / p.v_min)


def in_band(d: float, p: VoiceParams, last: bool = False, slack: float = 0.0) -> bool:
    """S19 band check; the last voice may be shorter than v_min."""
    return (d <= p.v_max + slack) if last else (p.v_min - slack <= d <= p.v_max + slack)


def _finish(units: list[VoiceUnit], p: VoiceParams, algo: str) -> VoiceSegmentation:
    bad = [i for i, u in enumerate(units) if u.est_s > p.v_max + p.tol]
    return VoiceSegmentation(units, bad, algo)


# --------------------------------------------------------------- F1 (report)
def segment_greedy(sentences: list[str], p: VoiceParams = VoiceParams(),
                   faithful: bool = False) -> VoiceSegmentation:
    """F1. `faithful=True` is the report's pseudocode verbatim; it can merge a 2-sentence tail
    into a 1-sentence voice and emit a 3-sentence voice (breaks the 1-2 sentence rule).
    The default (`faithful=False`) merges the tail only if the result keeps <= max_sentences."""
    units: list[list[str]] = []
    cur: list[str] = []
    est = lambda ss: make_unit(ss, p.wpm, p.pause_s).est_s
    for snt in sentences:
        if cur and (est(cur + [snt]) > p.v_max or len(cur) == p.max_sentences or est(cur) >= p.v_min):
            units.append(cur)
            cur = []
        cur.append(snt)
    if cur:
        room = (len(units[-1]) < p.max_sentences) if faithful else \
               (bool(units) and len(units[-1]) + len(cur) <= p.max_sentences)
        if est(cur) < p.v_min and units and room:
            units[-1] = units[-1] + cur          # merge a short tail
        else:
            units.append(cur)
    return _finish([make_unit(u, p.wpm, p.pause_s) for u in units], p, "F1_greedy")


# ------------------------------------------------------------------ DP (F2/F3)
def _dp(sentences: list[str], p: VoiceParams, unit_cost: Callable, algo: str,
        width: int = 2) -> VoiceSegmentation:
    """Shortest path over cut points; costs are tuples compared lexicographically."""
    n = len(sentences)
    dp: list = [None] * (n + 1)
    back = [0] * (n + 1)
    dp[0] = (0,) * width
    for i in range(1, n + 1):
        best = None
        for k in range(1, p.max_sentences + 1):     # k ascending: ties go to fewer sentences
            if i - k < 0:
                break
            c = unit_cost(make_unit(sentences[i - k:i], p.wpm, p.pause_s), i == n)
            tot = tuple(round(a + b, 9) for a, b in zip(dp[i - k], c))
            if best is None or tot < best[0]:
                best = (tot, k)
        dp[i], back[i] = best
    cuts, i = [], n
    while i > 0:
        cuts.append((i - back[i], i))
        i -= back[i]
    units = [make_unit(sentences[a:b], p.wpm, p.pause_s) for a, b in reversed(cuts)]
    return _finish(units, p, algo)


def segment_dp_deviation(sentences, p: VoiceParams = VoiceParams()) -> VoiceSegmentation:
    return _dp(sentences, p, lambda u, last: (0, abs(u.est_s - p.v_target)), "F2_dp_deviation")


def segment_dp_band(sentences, p: VoiceParams = VoiceParams()) -> VoiceSegmentation:
    def cost(u: VoiceUnit, last: bool):
        return (0 if in_band(u.est_s, p, last) else 1, abs(u.est_s - p.v_target))
    return _dp(sentences, p, cost, "F3_dp_band")


def segment_dp_share(sentences, p: VoiceParams = VoiceParams()) -> VoiceSegmentation:
    """F4: minimise voices outside the band, then prefer MORE voices (= more in-band voices),
    then deviation. Fixes F3 ties such as [3 s, 11 s, 3 s, 11 s] -> two 14 s voices."""
    def cost(u: VoiceUnit, last: bool):
        return (0 if in_band(u.est_s, p, last) else 1, -1, abs(u.est_s - p.v_target))
    return _dp(sentences, p, cost, "F4_dp_share", width=3)


ALGORITHMS = {
    "F1_greedy": segment_greedy,
    "F2_dp_deviation": segment_dp_deviation,
    "F3_dp_band": segment_dp_band,
    "F4_dp_share": segment_dp_share,
}


def segment_voices(sentences: list[str], algorithm: str = "F3_dp_band",
                   params: VoiceParams = VoiceParams()) -> VoiceSegmentation:
    if not sentences:
        return VoiceSegmentation([], [], algorithm)
    return ALGORITHMS[algorithm](sentences, params)


# ------------------------------------------------------- post-TTS check (5.7)
@dataclass
class RepairResult:
    units: list[VoiceUnit]
    durations: list[float]
    synth_calls: int              # TTS calls spent (unchanged voices are cached, not re-synthesised)
    rounds: int


def repair_after_tts(units: list[VoiceUnit], tts: Callable[[tuple[str, ...]], float],
                     p: VoiceParams = VoiceParams(), max_rounds: int = 2) -> RepairResult:
    """Check REAL durations and re-split / re-merge voices outside [v_min-tol, v_max+tol]."""
    cache: dict[tuple[str, ...], float] = {}
    calls = 0

    def dur(u: VoiceUnit) -> float:
        nonlocal calls
        if u.sentences not in cache:
            cache[u.sentences] = tts(u.sentences)
            calls += 1
        return cache[u.sentences]

    cur, rounds = list(units), 0
    for _ in range(max_rounds):
        durs = [dur(u) for u in cur]
        new, changed, i = [], False, 0
        while i < len(cur):
            u, d, last = cur[i], durs[i], i == len(cur) - 1
            if d > p.v_max + p.tol and len(u.sentences) > 1:           # too long -> split
                new.extend(make_unit((s,), p.wpm, p.pause_s) for s in u.sentences)
                changed = True
            elif (d < p.v_min - p.tol and not last
                  and len(u.sentences) + len(cur[i + 1].sentences) <= p.max_sentences
                  and d + durs[i + 1] <= p.v_max + p.tol):   # too short -> merge (durations include pauses)
                new.append(make_unit(u.sentences + cur[i + 1].sentences, p.wpm, p.pause_s))
                changed, i = True, i + 1
            else:
                new.append(u)
            i += 1
        cur = new
        rounds += 1
        if not changed:
            break
    return RepairResult(cur, [dur(u) for u in cur], calls, rounds)
