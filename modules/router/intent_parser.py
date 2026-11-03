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


# ======================================================================= v3
# Hardened parser (answers the 5 adversarial cases found by the team):
#  (a) more units: "150s", hours;   (b) "1 minute 30 seconds" is ONE duration;
#  (c) thousands separators in credits ("1,000");  (d) negated formats ("not animation");
#  (e) only the REQUEST part (text before the topic marker: about/on/why/về...) decides
#      format and duration; the topic itself can no longer act as a command.
_TOPIC_MARKER = r"\b(?:about|on|regarding|explaining|explain|why|how|what|về|giải thích|vì sao|tại sao)\b"
_NEGATED_FMT = (rf"(?:\b(?:not|no|without|instead of|rather than|except)\s+(?:an?\s+)?(?:{_INFO}|{_ANIM}))"
                rf"|(?:\b(?:không|đừng)\s+(?:phải\s+)?(?:{_INFO}|{_ANIM}))")
_COMPOUND = r"(\d+)\s*(?:minutes?|mins?|phút)\s*(?:and\s*|và\s*)?(\d+)\s*(?:seconds?|secs?|giây)"
_DURATION3 = r"(\d+(?:[.,]\d+)?)\s*-?\s*(seconds?|secs?|giây|minutes?|mins?|phút|hours?|hrs?|giờ)"
_ATTACHED = r"(?<![\d.,])(\d{1,3})(s|h)\b"        # 150s, 2h  (never 1990s: max 3 digits)
_CREDITS3 = r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+|\d+)\s*(?:credits?|tín dụng)"
_TAIL_CUES = {"long", "lasting", "duration", "length", "dài"}


def _to_seconds(value: float, unit: str) -> int:
    if unit.startswith(("hour", "hr", "giờ", "h")):
        return int(round(value * 3600))
    if unit.startswith(("min", "phút")):
        return int(round(value * 60))
    return int(round(value))


def _head_len(low: str) -> int:
    m = re.search(_TOPIC_MARKER, low)
    return m.start() if m and low[:m.start()].strip() else len(low)


def _detect_format(s: str) -> tuple[Optional[OutputFormat], bool]:
    s = re.sub(_NEGATED_FMT, " ", s)
    has_i, has_a = bool(re.search(_INFO, s)), bool(re.search(_ANIM, s))
    if re.search(_HYB, s):
        return OutputFormat.HYBRID, False
    if has_i and has_a:
        return (OutputFormat.HYBRID, False) if re.search(_CUE, s) else (None, True)
    if has_a:
        return OutputFormat.ANIMATION, False
    if has_i:
        return OutputFormat.INFOGRAPHIC, False
    return None, False


def _parse_duration_v3(low: str, head_len: int) -> Optional[int]:
    cands = []
    for m in re.finditer(_COMPOUND, low):
        cands.append((m.start(), m.end(), int(m.group(1)) * 60 + int(m.group(2))))
    for m in re.finditer(_DURATION3, low):
        cands.append((m.start(), m.end(), _to_seconds(float(m.group(1).replace(",", ".")), m.group(2))))
    for m in re.finditer(_ATTACHED, low):
        cands.append((m.start(), m.end(), _to_seconds(float(m.group(1)), m.group(2))))
    cands.sort(key=lambda c: (c[0], -(c[1] - c[0])))
    taken: list[tuple[int, int]] = []
    for start, end, secs in cands:
        if any(start < e and s < end for s, e in taken):
            continue
        taken.append((start, end))
        left, right = _words(low[:start]), _words(low[end:])
        if start < head_len:                                   # request part: needs a video word
            ok = bool(_ANCHORS.intersection(left[-2:] + right[:2]))
        else:                                                  # topic part: needs "... long"
            ok = bool(_TAIL_CUES.intersection(left[-1:] + right[:1]))
        if ok:
            return secs
    return None


def parse_intent_v3(text: str) -> ParsedIntent:
    low = text.lower()
    out = ParsedIntent()
    head = low[:_head_len(low)]
    out.t_target = _parse_duration_v3(low, len(head))
    if (b := re.search(_CREDITS3, low)):
        out.budget = int(re.sub(r"[.,]", "", b.group(1)))

    first_words = " ".join(low.split()[:4])
    if re.search(_SWITCH, first_words) and (tgt := re.search(_SWITCH_TARGET, low)):
        out.intent, out.fmt = "switch_format", _fmt_of(tgt.group(1))
        return out
    fmt, amb = _detect_format(head)
    if fmt is None and not amb:
        fmt, amb = _detect_format(low)
    out.fmt, out.ambiguous_format = fmt, amb
    return out
