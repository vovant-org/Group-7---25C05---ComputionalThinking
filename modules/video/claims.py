"""Baseline REASON replacement: claims from the user's own reference text (no LLM, no web).

ASSUMPTION / LIMITS: this is an EXTRACTIVE heuristic, not the verified REASON step of the report.
It keeps usable sentences (8-24 words: a longer one would not fit one scene of at most 10 s) of the reference text as claims, in order, and guesses importance and
`explain_pattern` from simple cues (position, figures, linking words). Facts are only as good as the
text the user supplies; nothing is checked against sources. Same text, same claims.
"""
from __future__ import annotations

import re

from modules.scene_segmenter.segmenter import Claim
from modules.video import labels as L
from modules.voice_segmenter.segmenter import split_sentences

_COMPARE = re.compile(r"\b(while|whereas|compared with|than|unlike|versus|trong khi|so với)\b", re.I)
_STEPS = re.compile(r"\b(first|then|finally|next|đầu tiên|sau đó|cuối cùng)\b", re.I)
_ANALOGY = re.compile(r"\b(imagine|think of|like a|as if|hãy tưởng tượng|giống như)\b", re.I)
_KEY = re.compile(r"\b(because|so|therefore|key|main|important|causes?|leads? to|vì|nên|quan trọng)\b", re.I)


def claims_from_text(text: str, prefix: str = "TXT", min_words: int = 8, max_words: int = 24) -> list[Claim]:
    seen, sentences = set(), []
    for s in split_sentences(text):
        s = " ".join(s.split())
        n = len(s.split())
        key = s.lower()
        if min_words <= n <= max_words and key not in seen:
            seen.add(key)
            sentences.append(s)
    total = len(sentences)
    claims = []
    for i, s in enumerate(sentences):
        figs = L.extract_figures(s)
        if _ANALOGY.search(s):
            pattern = "analogy"
        elif len(figs) >= 2:
            pattern = "trend"
        elif _COMPARE.search(s):
            pattern = "comparison"
        elif _STEPS.search(s):
            pattern = "step_by_step"
        else:
            pattern = "cause_effect"
        imp = 0.9 - 0.4 * (i / max(1, total - 1)) + (0.08 if figs else 0) + (0.05 if _KEY.search(s) else 0)
        claims.append(Claim(claim_id=f"{prefix}{i + 1:02d}", text=s, facet="general",
                            importance=round(min(0.99, max(0.05, imp)), 3), explain_pattern=pattern,
                            has_figure=bool(figs), order=i))
    return claims
