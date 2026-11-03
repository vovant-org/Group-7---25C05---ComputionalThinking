"""Router (report 5.1). Decides: accept / clarify / reject, resolves the format and
duration, and enforces the hard limits (S14, S12) deterministically.

Versions (report 5.9.1):
  v0_policy_table     A1: only structured fields are read (no free-text understanding)
  v1_hybrid_naive     A4: rules + intent parser (naive duration regex)
  v2_hybrid_windowed  A4: same, but a duration only counts if a video word is nearby
  v3_hardened         A4: request part vs topic part, more units, compound durations,
                      thousands separators, negation (fixes the adversarial cases)
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from core.config import DEFAULT_FORMAT, DEFAULT_T_TARGET, PROFILES
from core.models import OutputFormat, Scene
from modules.budget_optimizer.optimizer import min_cost_with_motion
from modules.router.intent_parser import ParsedIntent, parse_intent, parse_intent_v3, strip_quantities

MAX_INPUT_WORDS = 1500
T_MIN, T_MAX = 60, 120
_NUMERIC_HINT = (r"compar|\bvs\b|versus|chart|trend|price|percent|%|statistic|\bgiá\b"
                 r"|so sánh|biểu đồ|thống kê")


class RouteStatus(str, Enum):
    ACCEPT = "ACCEPT"
    CLARIFY = "CLARIFY"
    REJECT = "REJECT"


@dataclass
class Request:
    topic: str
    reference_text: str = ""
    output_format: Optional[OutputFormat] = None
    t_target: Optional[int] = None
    budget: Optional[int] = None
    c_est: Optional[int] = None        # from the Cost Estimator, when available


@dataclass
class RouteDecision:
    status: RouteStatus
    codes: set[str] = field(default_factory=set)
    fmt: Optional[OutputFormat] = None
    t_target: Optional[int] = None
    intent: str = "new_video"
    word_count: int = 0
    messages: list[str] = field(default_factory=list)


REJECT_CODES = {"INPUT_TOO_LONG", "T_OUT_OF_RANGE", "BUDGET_BELOW_MIN", "COST_OVER_BUDGET"}
CLARIFY_CODES = {"EMPTY_TOPIC", "AMBIGUOUS_FORMAT"}


def count_words(text: str) -> int:
    """Whitespace-separated strings (each Vietnamese syllable counts as one word)."""
    return len(text.split())


def min_scene_cost(fmt: OutputFormat, t_target: int) -> int:
    profile = PROFILES[fmt]
    n = math.ceil(t_target / profile.t_max)
    dummy = [Scene(scene_id=i) for i in range(n)]
    return min_cost_with_motion(dummy, profile)


def _is_numeric_heavy(text: str) -> bool:
    cleaned = strip_quantities(text)
    digits = sum(any(ch.isdigit() for ch in tok) for tok in cleaned.split())
    return digits >= 3 or bool(re.search(_NUMERIC_HINT, cleaned))


def route(req: Request, algorithm: str = "v2_hybrid_windowed") -> RouteDecision:
    text = f"{req.topic}\n{req.reference_text}"
    d = RouteDecision(RouteStatus.ACCEPT, word_count=count_words(text))

    # ---- understand: fill missing fields (never override structured input)
    parsed = ParsedIntent()
    if algorithm == "v1_hybrid_naive":
        parsed = parse_intent(req.topic, window=None)
    elif algorithm == "v2_hybrid_windowed":
        parsed = parse_intent(req.topic, window=2)
    elif algorithm == "v3_hardened":
        parsed = parse_intent_v3(req.topic)
    elif algorithm != "v0_policy_table":
        raise ValueError(algorithm)

    d.intent = parsed.intent
    fmt = req.output_format or parsed.fmt
    t = req.t_target if req.t_target is not None else parsed.t_target
    budget = req.budget if req.budget is not None else parsed.budget

    if fmt is None and parsed.ambiguous_format:
        d.codes.add("AMBIGUOUS_FORMAT")
        d.messages.append("Do you want an infographic video or an animation video?")
    elif fmt is None:
        fmt = DEFAULT_FORMAT
        d.codes.add("FORMAT_DEFAULTED")
        d.messages.append(f"No format given; defaulting to {fmt.value}.")
    if t is None:
        t = DEFAULT_T_TARGET
        d.codes.add("T_DEFAULTED")
        d.messages.append(f"No duration given; defaulting to {t} s.")
    d.fmt, d.t_target = fmt, t

    # ---- hard rules (deterministic, cannot be bypassed by the text)
    if not req.topic.strip():
        d.codes.add("EMPTY_TOPIC")
        d.messages.append("Please describe the topic or question.")
    if d.word_count > MAX_INPUT_WORDS:
        d.codes.add("INPUT_TOO_LONG")
        d.messages.append(f"Input has {d.word_count} words (limit {MAX_INPUT_WORDS}); please shorten it.")
    in_range = T_MIN <= t <= T_MAX
    if not in_range:
        d.codes.add("T_OUT_OF_RANGE")
        nearest = min(max(t, T_MIN), T_MAX)
        d.messages.append(f"Duration {t} s is outside {T_MIN}-{T_MAX} s; nearest valid value is {nearest} s.")
    if fmt is not None and in_range and budget is not None:
        lo = min_scene_cost(fmt, t)
        if budget < lo:
            d.codes.add("BUDGET_BELOW_MIN")
            d.messages.append(f"Budget {budget} < minimum {lo} for {fmt.value}; "
                              "raise it, shorten the video, or choose a cheaper format.")
        elif req.c_est is not None and req.c_est > budget:
            d.codes.add("COST_OVER_BUDGET")
            d.messages.append(f"Estimated cost {req.c_est} > budget {budget}.")
        elif req.c_est is not None:
            d.codes.add("NEEDS_CONFIRMATION")
    if fmt == OutputFormat.ANIMATION and _is_numeric_heavy(req.topic):
        d.codes.add("SUGGEST_NUMERIC_FORMAT")
        d.messages.append("Figure-heavy topic: INFOGRAPHIC or HYBRID shows numbers more clearly.")

    if d.codes & REJECT_CODES:
        d.status = RouteStatus.REJECT
    elif d.codes & CLARIFY_CODES:
        d.status = RouteStatus.CLARIFY
    return d
