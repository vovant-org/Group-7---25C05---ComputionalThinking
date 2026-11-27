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


# Vietnamese typed WITHOUT tone marks ("tai sao gia ca tang") has no special letter to see. These are very common
# Vietnamese function words written in plain ASCII that are not (or are rare) English words. ASSUMPTION: our own list.
_VI_ASCII_WORDS = frozenset(
    "tai sao nhu nao gi cua khong duoc nhung nguoi viec trong ngoai voi cho cac mot hai ba nhieu rat lam "
    "khi thi va hay hoac neu vi nen ma minh ban chung toi ho nay kia dau day roi chua cung van dang se da "
    "giac ngu gia ca tang giam lam phat thanh pho ngap mua tien hoc sinh tre em suc khoe".split())
VI_ASCII_SHARE = 0.4         # unmarked text is Vietnamese when >= 40% of its words are on that list


def _clean(token: str) -> str:
    return "".join(ch for ch in token.lower() if ch.isalpha())


def detect_language(text: str) -> Optional[str]:
    """'vi' or 'en'; None when the text has no alphabetic word to judge."""
    tokens = [t for t in text.split() if any(ch.isalpha() for ch in t)]
    if not tokens:
        return None
    share = sum(_has_vietnamese_letter(t) for t in tokens) / len(tokens)
    if share >= VI_TOKEN_SHARE:
        return "vi"
    if len(tokens) >= 3 and sum(_clean(t) in _VI_ASCII_WORDS for t in tokens) / len(tokens) >= VI_ASCII_SHARE:
        return "vi"
    return "en"
