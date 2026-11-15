"""Tiny deterministic language detector for narration text: English or Vietnamese.

Used only to catch a wrong pairing (an English voice asked to read Vietnamese claims, or the
other way round) before anything is synthesised. It is a heuristic, not a language model:
Vietnamese is recognised by its letters (đ, ă, â, ê, ô, ơ, ư) and tone marks, which plain
English text almost never contains.
"""
from __future__ import annotations

import unicodedata
from typing import Optional

# Combining marks of Vietnamese: grave, acute, circumflex, tilde, breve, hook above, horn, dot below.
_VI_MARKS = frozenset("̛̣̀́̂̃̆̉")
VI_TOKEN_SHARE = 0.25        # a text is Vietnamese when >= 25% of its words carry such a letter


def _has_vietnamese_letter(token: str) -> bool:
    if "đ" in token or "Đ" in token:
        return True
    return any(ch in _VI_MARKS for ch in unicodedata.normalize("NFD", token))


def detect_language(text: str) -> Optional[str]:
    """'vi' or 'en'; None when the text has no alphabetic word to judge."""
    tokens = [t for t in text.split() if any(ch.isalpha() for ch in t)]
    if not tokens:
        return None
    share = sum(_has_vietnamese_letter(t) for t in tokens) / len(tokens)
    return "vi" if share >= VI_TOKEN_SHARE else "en"
