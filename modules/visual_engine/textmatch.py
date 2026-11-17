"""Matching keywords in English and Vietnamese text.

Vietnamese diacritics matter ("mưa" = rain, "mua" = buy), so keywords are matched on the lower-cased text WITH
diacritics when the text has any Vietnamese letter. Text typed without diacritics ("giac ngu") is matched on
folded forms (diacritics stripped on both sides), because that is the only information it carries.
A single-word keyword matches a word that STARTS with it ("animal" -> "animals"); a multi-word keyword needs
consecutive words ("giấc ngủ", "central bank").
"""
from __future__ import annotations

import re
import unicodedata

_VI_MARKS = re.compile(r"[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]")


def fold(s: str) -> str:
    """lower-case, no diacritics (đ -> d)."""
    s = unicodedata.normalize("NFC", s).lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def has_vietnamese_marks(text: str) -> bool:
    return bool(_VI_MARKS.search(unicodedata.normalize("NFC", text).lower()))


def tokens(text: str) -> list[str]:
    """Whitespace-separated words of the ORIGINAL text, stripped of punctuation, lower-case (NFC)."""
    out = []
    for w in text.split():
        core = re.sub(r"^[^\w]+|[^\w]+$", "", unicodedata.normalize("NFC", w).lower())
        out.append(core)
    return out


def find_keywords(words: list[str], keywords: list[str], vietnamese: bool) -> int | None:
    """Index of the first word where one of `keywords` starts, or None. `words` must come from `tokens`."""
    ws = words if vietnamese else [fold(w) for w in words]
    best = None
    for kw in keywords:
        k = unicodedata.normalize("NFC", kw.lower()) if vietnamese else fold(kw)
        parts = k.split()
        n = len(parts)
        # prefix matching ("animal" -> "animals") only where it is safe: Vietnamese text, or an English keyword.
        # A Vietnamese keyword with diacritics, folded ("trả" -> "tra"), must match a whole word, else it hits "travel".
        prefix_ok = vietnamese or kw.isascii()
        for i in range(len(ws) - n + 1):
            if all((ws[i + j].startswith(parts[j]) if (j == n - 1 and len(parts[j]) >= 3 and prefix_ok)
                    else ws[i + j] == parts[j]) for j in range(n)):
                best = i if best is None else min(best, i)
                break
    return best
