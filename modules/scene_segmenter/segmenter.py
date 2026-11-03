"""Scene Segmenter: claim selection + scene construction (report 5.2, 5.9.4; criteria S13, S16).

Input  : verified claims (output of REASON) with importance and facet.
Output : the claims that fit the narration word budget W_target = wpm * T_target / 60,
         turned into Scene objects (layout looked up from explain_pattern for infographics).

Selection algorithms (report 5.9.4):
  D1_greedy       highest importance first                       (the report's current method)
  D2_mmr          Maximal Marginal Relevance: importance vs. similarity to what is already chosen
  D2f_mmr_facet   MMR, but first one claim per facet (perspectives), budget permitting
Similarity is lexical (TF-IDF cosine on content words): deterministic, no model, no API.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Optional

from core import config as C
from core.models import OutputFormat, Scene

STOPWORDS = frozenset("""a an the of and or to in on at for with by from as is are was were be been it its this that
these those so but not no can may will would should could do does did has have had than then into out up down over
under about more most some any each every very just also which who whom what when where why how their there they them
you your we our us he she his her i if""".split()) | frozenset(
    "và của là có cho một những các được trong với để cũng thì mà này đó khi".split())

LAYOUT_BY_PATTERN = {                      # report 5.2 lookup table
    "cause_effect": "cause_chain",
    "comparison": "compare_2col",
    "step_by_step": "steps",
    "trend": "trend_chart",
}


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    facet: str
    importance: float                       # in [0, 1], produced upstream (REASON)
    explain_pattern: str = "cause_effect"
    has_figure: bool = False
    order: int = 0                          # position in the source (keeps narration order stable)

    @property
    def words(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class SegParams:
    wpm: float = C.VOICE_WPM
    tol: float = 0.10                       # narration may deviate +-10% from W_target (S13 uses 5% later)
    lam: float = 0.7                        # MMR weight of importance vs. novelty


@dataclass
class Selection:
    claims: list[Claim]                     # in narration (source) order
    words: int
    w_target: float
    algorithm: str


def target_words(t_target: float, wpm: float) -> float:
    return wpm * t_target / 60.0


# ------------------------------------------------------------- similarity
def _stem(w: str) -> str:
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"\w+", text.lower()) if w not in STOPWORDS]


def similarity_matrix(claims: list[Claim]) -> list[list[float]]:
    docs = [Counter(tokenize(c.text)) for c in claims]
    n = len(docs)
    df = Counter(t for d in docs for t in d)
    idf = {t: math.log((1 + n) / (1 + k)) + 1.0 for t, k in df.items()}
    vecs = [{t: f * idf[t] for t, f in d.items()} for d in docs]
    norms = [math.sqrt(sum(v * v for v in vec.values())) or 1.0 for vec in vecs]
    sim = [[0.0] * n for _ in range(n)]
    for i in range(n):
        sim[i][i] = 1.0 if vecs[i] else 0.0
        for j in range(i + 1, n):
            dot = sum(v * vecs[j].get(t, 0.0) for t, v in vecs[i].items())
            sim[i][j] = sim[j][i] = dot / (norms[i] * norms[j])
    return sim


# ---------------------------------------------------------------- selection
def _fill(claims, p: SegParams, w_target: float, pick, algo: str, pre: Optional[Callable] = None) -> Selection:
    """Shared loop: add claims until the budget is reached; never exceed W_target*(1+tol)."""
    w_lo, w_hi = w_target * (1 - p.tol), w_target * (1 + p.tol)
    chosen: list[int] = []
    total = 0
    if pre:
        for i in pre(chosen, total, w_hi):
            chosen.append(i)
            total += claims[i].words
    while total < w_lo:
        cands = [i for i in range(len(claims)) if i not in chosen and total + claims[i].words <= w_hi]
        if not cands:
            break
        i = pick(chosen, cands)
        chosen.append(i)
        total += claims[i].words
    ordered = sorted((claims[i] for i in chosen), key=lambda c: (c.order, c.claim_id))
    return Selection(ordered, total, w_target, algo)


def select_greedy(claims, w_target, p: SegParams = SegParams()) -> Selection:
    key = lambda i: (-claims[i].importance, claims[i].order, claims[i].claim_id)
    return _fill(claims, p, w_target, lambda chosen, cands: min(cands, key=key), "D1_greedy")


def _mmr_picker(claims, sim, p):
    top = max((c.importance for c in claims), default=1.0) or 1.0

    def pick(chosen, cands):
        def score(i):
            red = max((sim[i][j] for j in chosen), default=0.0)
            return (p.lam * claims[i].importance / top - (1 - p.lam) * red,
                    claims[i].importance, -claims[i].order)
        return max(cands, key=score)
    return pick


def select_mmr(claims, w_target, p: SegParams = SegParams()) -> Selection:
    sim = similarity_matrix(claims)
    return _fill(claims, p, w_target, _mmr_picker(claims, sim, p), "D2_mmr")


def select_mmr_facet(claims, w_target, p: SegParams = SegParams()) -> Selection:
    """MMR plus a coverage constraint: one claim per facet first (facets with the most
    important claim first), as long as it fits; then ordinary MMR fills the rest."""
    sim = similarity_matrix(claims)
    pick = _mmr_picker(claims, sim, p)

    def pre(chosen, total, w_hi):
        facets = sorted({c.facet for c in claims},
                        key=lambda f: -max(c.importance for c in claims if c.facet == f))
        out, tot = [], total
        for f in facets:
            cands = [i for i, c in enumerate(claims) if c.facet == f and tot + c.words <= w_hi]
            if cands:
                i = pick(chosen + out, cands)
                out.append(i)
                tot += claims[i].words
        return out
    return _fill(claims, p, w_target, pick, "D2f_mmr_facet", pre)


ALGORITHMS = {"D1_greedy": select_greedy, "D2_mmr": select_mmr, "D2f_mmr_facet": select_mmr_facet}


def select_claims(claims: list[Claim], t_target: float, algorithm: str = "D2f_mmr_facet",
                  params: SegParams = SegParams()) -> Selection:
    return ALGORITHMS[algorithm](claims, target_words(t_target, params.wpm), params)


# ------------------------------------------------------------------- scenes
def layout_for(c: Claim) -> Optional[str]:
    """Infographic layout from explain_pattern (report 5.2); analogy depends on the claim."""
    if c.explain_pattern == "analogy":
        return "big_number" if c.has_figure else "loop"
    return LAYOUT_BY_PATTERN.get(c.explain_pattern)


def build_scenes(selection: Selection, fmt: OutputFormat = OutputFormat.INFOGRAPHIC,
                 p: SegParams = SegParams(), t_min: float = 4.0, t_max: float = 10.0) -> tuple[list[Scene], dict]:
    """One scene per selected claim. Returns the scenes and a report of rule violations
    (scenes longer than t_max need splitting/shortening, shorter than t_min need merging)."""
    scenes, too_long, too_short, t = [], [], [], 0.0
    for i, c in enumerate(selection.claims):
        dur = c.words * 60.0 / p.wpm
        if dur > t_max:
            too_long.append(i)
        elif dur < t_min:
            too_short.append(i)
        scenes.append(Scene(
            scene_id=i, narration=c.text, importance=c.importance, explain_pattern=c.explain_pattern,
            claim_ids=[c.claim_id], facet=c.facet, start_s=round(t, 3), duration_s=round(dur, 3),
            visual_type="infographic" if fmt == OutputFormat.INFOGRAPHIC else "character_scene",
            layout=layout_for(c) if fmt == OutputFormat.INFOGRAPHIC else None))
        t += dur
    n = len(scenes)
    return scenes, {"n_scenes": n, "scene_count_ok": 6 <= n <= 30,
                    "too_long": too_long, "too_short": too_short, "total_s": round(t, 2)}
