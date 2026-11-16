"""Deterministic text -> structure rules for the Infographic Composer (report 5.4, option I1/I2).

A claim sentence is cut into contiguous chunks (cause -> effect, side A | side B, steps, loop nodes).
Because every chunk is a contiguous run of the claim's own words, the on-screen text always comes
from the claim (criterion S15). `label_supported` is the automatic check for that.
No LLM is used here: same input, same chunks.
"""
from __future__ import annotations

import itertools
import re
from typing import Optional, Sequence

_STRIP = ".,;:!?\"'()[]“”‘’…—–-"
MIN_WORDS = 3

COMPARE_CONN = frozenset({"whereas", "while", "but", "unlike", "versus", "than", "nhưng", "còn"})
# cause -> effect: linking words and common causal verbs (a cut is made BEFORE the word)
CAUSE_CONN = frozenset({"so", "because", "which", "since", "makes", "make", "leads", "causes", "pushes",
                        "raises", "cools", "helps", "delays", "blocks", "creates", "means",
                        "vì", "nên", "khiến", "làm", "giúp", "gây"})
STEP_CONN = frozenset({"then", "finally", "sau", "cuối"})   # "first"/"next" are too often plain adverbs
LOOP_CONN = CAUSE_CONN | frozenset({"and", "or"})
_PREPS = frozenset({"during", "in", "on", "at", "to", "of", "with", "by", "for", "from", "into", "through",
                    "about", "under", "over", "between", "than"})
_DANGLING = _PREPS | frozenset({"and", "or", "the", "a", "an", "that", "is", "are", "as", "và", "của", "là"})
_LEAD = frozenset({"and", "or", "but", "so", "then", "finally", "first", "next"})

_FIGURE = re.compile(r"(?<![\w.,])[$€£]?\d[\d,]*(?:\.\d+)?\s?(?:%|percent\b)?")


def norm(token: str) -> str:
    return token.strip(_STRIP).lower()


def label_supported(label: str, claim_text: str) -> bool:
    """True when the label's words appear as one contiguous run in the claim (ignoring case and
    surrounding punctuation). This is the automatic S15 check."""
    lw = [norm(t) for t in label.split() if norm(t)]
    cw = [norm(t) for t in claim_text.split() if norm(t)]
    if not lw:
        return False
    return any(cw[i:i + len(lw)] == lw for i in range(len(cw) - len(lw) + 1))


def clean_chunk(part: str) -> str:
    part = part.strip().rstrip(",;:").strip()
    if part.endswith(".") and not part.endswith(".."):
        part = part[:-1]
    ws = part.split()
    if len(ws) > MIN_WORDS and norm(ws[0]) in _LEAD:      # "and finally keep ..." -> "keep ..."
        ws = ws[1:]
    part = " ".join(ws)
    return part[:1].upper() + part[1:] if part else part


def _candidates(ws: Sequence[str], connectors: frozenset[str], min_words: int) -> tuple[list[int], list[int]]:
    """(connector cut positions, punctuation cut positions); a position i starts the next part."""
    n = len(ws)
    conn = []
    for i in range(min_words, n - min_words + 1):
        if norm(ws[i]) not in connectors:
            continue
        if norm(ws[i]) in ("which", "whom") and norm(ws[i - 1]) in _PREPS and i - 1 >= min_words:
            conn.append(i - 1)                      # keep "during which" together: cut before the preposition
        elif norm(ws[i - 1]) not in _DANGLING:
            conn.append(i)
    punct = [i for i in range(min_words, n - min_words + 1) if ws[i - 1].endswith((",", ";", ":"))]
    return conn, punct


def natural_cuts(text: str, connectors: frozenset[str] = frozenset(), min_words: int = MIN_WORDS) -> int:
    conn, punct = _candidates(text.split(), connectors, min_words)
    return len(set(conn) | set(punct))


def split_chunks(text: str, k: int, connectors: frozenset[str] = frozenset(),
                 min_words: int = MIN_WORDS, prefer: str = "punct") -> list[str]:
    """Cut `text` into up to k contiguous parts at natural boundaries.

    prefer="connector": cut before linking words first (cause -> effect, A | B), commas second.
    prefer="punct":     cut after commas first (lists, steps), linking words second.
    If neither exists near the ideal position the cut falls at the ideal word, moved left while the
    left part would end on a dangling word such as "and" or "the"."""
    ws = text.split()
    n = len(ws)
    k = max(1, min(k, n // min_words)) if n else 1
    if k == 1:
        return [clean_chunk(text)]
    conn, punct = _candidates(ws, connectors, min_words)
    order = (conn, punct) if prefer == "connector" else (punct, conn)
    cuts: list[int] = []
    for j in range(1, k):
        ideal = round(n * j / k)
        lo = (cuts[-1] if cuts else 0) + min_words
        hi = n - (k - j) * min_words
        tol = n if prefer == "connector" else max(4, 0.45 * n / k)     # a linking word beats balance
        cut = None
        for pool in order:
            ok = [c for c in pool if lo <= c <= hi and abs(c - ideal) <= tol]
            if ok:
                cut = min(ok, key=lambda c: abs(c - ideal))
                break
        if cut is None:
            cut = min(max(ideal, lo), hi)
            while cut > lo and norm(ws[cut - 1]) in _DANGLING:
                cut -= 1
        cuts.append(cut)
    bounds = [0] + cuts + [n]
    return [clean_chunk(" ".join(ws[a:b])) for a, b in zip(bounds, bounds[1:])]


def split_natural(text: str, k_max: int, connectors: frozenset[str] = frozenset(),
                  min_words: int = MIN_WORDS) -> list[str]:
    """Cut `text` into as many parts as possible (at most k_max) using ONLY natural boundaries
    (after a comma/semicolon/colon, or before a linking word). Never cuts in the middle of a phrase:
    if there are not enough boundaries it returns fewer parts (possibly just the whole text)."""
    ws = text.split()
    n = len(ws)
    conn, punct = _candidates(ws, connectors, min_words)
    cands = sorted(set(conn) | set(punct))
    for m in range(min(k_max - 1, len(cands)), 0, -1):
        best, best_cost = None, None
        for combo in itertools.combinations(cands, m):
            bounds = (0,) + combo + (n,)
            sizes = [b - a for a, b in zip(bounds, bounds[1:])]
            if min(sizes) < min_words:
                continue
            cost = sum((x - n / (m + 1)) ** 2 for x in sizes)
            if best_cost is None or cost < best_cost:
                best, best_cost = bounds, cost
        if best:
            return [clean_chunk(" ".join(ws[a:b])) for a, b in zip(best, best[1:])]
    return [clean_chunk(text)]


def split_in_two(text: str) -> list[str]:
    """K3 of the report: split an overflowing label into two reveal steps."""
    return split_chunks(text, 2, LOOP_CONN | COMPARE_CONN, prefer="connector")


def shorten_to_words(text: str, n_words: int) -> str:
    """K2 (last resort): keep the first n words and add an ellipsis. Still a prefix of the claim."""
    ws = text.split()
    return text if len(ws) <= n_words else " ".join(ws[:max(1, n_words)]).rstrip(",;:") + "…"


def extract_figures(text: str) -> list[str]:
    """Numbers that carry a unit (%, percent, currency): the only ones we trust as plottable data."""
    out = []
    for m in _FIGURE.finditer(text):
        tok = m.group(0).strip()
        if re.search(r"[%$€£]|percent", tok):
            out.append(tok)
    return out


def main_number(text: str) -> Optional[str]:
    figs = extract_figures(text)
    if figs:
        return figs[0]
    for m in _FIGURE.finditer(text):               # plain number that is not a year
        tok = m.group(0).strip()
        if not re.fullmatch(r"(19|20)\d\d", tok):
            return tok
    return None


def figure_value(fig: str) -> float:
    return float(re.sub(r"[^0-9.]", "", fig.replace(",", "")) or 0)
