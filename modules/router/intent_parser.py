"""Offline intent parser for the Router (report 5.1 / 5.9.1, option A4).

Deterministic regex stand-in for the "LLM intent classifier": it only FILLS fields
the user did not give as structured input; the hard limits are enforced by the
router rules afterwards. A real LLM can later be plugged in behind `parse_intent`
(same ParsedIntent output) and measured on the same benchmark.

`window` controls false-positive protection for durations: a number+unit such as
"5 minutes" only counts as the video length if a video word appears within
`window` words next to it. window=None -> naive mode (v1), window=2 -> v2.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from core.models import OutputFormat

_INFO = r"info-?graphics?|inforgraphics?|đồ họa thông tin"
_ANIM = r"animat(?:ion|ed|e)|hoạt hình"
_HYB = r"hybrid|kết hợp"
_CUE = r"\b(?:only|rest|mix|mixed|keep|combine|chỉ|còn lại|giữ)\b"
_SWITCH = r"\b(?:convert|switch|chuyển)\b"
_SWITCH_TARGET = rf"\b(?:to|into|sang)\s+(?:an?\s+)?({_INFO}|{_ANIM})"
_DURATION = r"(\d+(?:[.,]\d+)?)\s*-?\s*(seconds?|secs?|giây|minutes?|mins?|phút)"
_CREDITS = r"(\d+)\s*(?:credits?|tín dụng)"
_ANCHORS = {"video", "videos", "clip", "infographic", "infographics", "animation",
            "animated", "animate", "film", "long", "phim", "dài", "hoạt", "hình"}


@dataclass
class ParsedIntent:
    fmt: Optional[OutputFormat] = None
    ambiguous_format: bool = False
    t_target: Optional[int] = None
    budget: Optional[int] = None
    intent: str = "new_video"          # or "switch_format"


def _fmt_of(token: str) -> OutputFormat:
    return OutputFormat.INFOGRAPHIC if re.fullmatch(_INFO, token) else OutputFormat.ANIMATION


def _words(chunk: str) -> list[str]:
    return [w.strip(".,;:!?()\"'").lower() for w in chunk.split()]


def _parse_duration(text: str, window: Optional[int]) -> Optional[int]:
    for m in re.finditer(_DURATION, text):
        if window is not None:
            left = _words(text[:m.start()])[-window:]
            right = _words(text[m.end():])[:window]
            if not _ANCHORS.intersection(left + right):
                continue
        value = float(m.group(1).replace(",", "."))
        unit = m.group(2)
        seconds = value * 60 if unit.startswith(("min", "phút")) else value
        return int(round(seconds))
    return None


def strip_quantities(text: str) -> str:
    """Remove duration/credit expressions (used before counting numbers)."""
    return re.sub(_CREDITS, " ", re.sub(_DURATION, " ", text.lower()))


def parse_intent(text: str, window: Optional[int] = 2) -> ParsedIntent:
    low = text.lower()
    out = ParsedIntent()
    out.t_target = _parse_duration(low, window)
    if (b := re.search(_CREDITS, low)):
        out.budget = int(b.group(1))

    sw, tgt = re.search(_SWITCH, low), re.search(_SWITCH_TARGET, low)
    if sw and tgt:
        out.intent, out.fmt = "switch_format", _fmt_of(tgt.group(1))
        return out

    has_i, has_a = bool(re.search(_INFO, low)), bool(re.search(_ANIM, low))
    if re.search(_HYB, low):
        out.fmt = OutputFormat.HYBRID
    elif has_i and has_a:
        if re.search(_CUE, low):
            out.fmt = OutputFormat.HYBRID
        else:
            out.ambiguous_format = True
    elif has_a:
        out.fmt = OutputFormat.ANIMATION
    elif has_i:
        out.fmt = OutputFormat.INFOGRAPHIC
    return out
