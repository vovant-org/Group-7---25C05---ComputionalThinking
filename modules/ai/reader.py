"""Read the user's input with an LLM and turn it into scenes: claim + a picture description of THAT claim.

Two input cases, two trust levels (the project rule is "no invented facts"):
  * REFERENCE TEXT given: every claim must be traceable to it. A claim is kept only when at least 85 % of its
    words occur in the reference text (so the model may trim a sentence but not add facts or numbers).
    Claims that fail are dropped and listed in `rejected`.
  * TOPIC ONLY: the model writes general claims itself. They are NOT verified: `grounded` is False, claims
    that contain digits are rejected (we do not let a model invent statistics), and the UI should say so.
If the model fails, returns bad JSON, or too few claims survive, `read_input` falls back to the extractive
baseline (modules/video/claims.py) and still gives every claim a locally built picture description.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from modules.ai.llm import LLM
from modules.ai.net import AIError
from modules.scene_segmenter.segmenter import Claim

MIN_CLAIMS = 6
MIN_WORDS, MAX_WORDS = 8, 24
GROUND_RATIO = 0.85
_WORD = re.compile(r"[^\W_]+", re.UNICODE)
_STOP = frozenset("the a an of to in on at and or but is are was were be it its this that with for as by from "
                  "which than then so can may will during over into your you we they their".split())

SYSTEM = """You prepare scenes for an explainer video. Read the user's input and answer with JSON only:
{{"scenes":[{{"claim":"...","facet":"...","importance":0.0,"pattern":"...","visual":"..."}}]}}
Rules:
- Give between {n_lo} and {n_hi} scenes (never fewer than {n_lo}) in the order the video should tell them.
- "claim": ONE sentence of {long_w}-{max_w} words (aim for about 18), in the same language as the input. Short
  sentences are not enough: the narration of all claims together must fill the whole video.
{claim_rule}
- "facet": one or two lowercase words naming the theme (e.g. science, health, daily life, economy).
- "importance": number from 0 to 1.
- "pattern": one of cause_effect, comparison, step_by_step, trend, analogy.
- "visual": an ENGLISH description (max 30 words) of ONE simple picture that shows exactly what the claim says:
  the main objects, what they do, and the setting. No text, letters, numbers, logos or real people's names.
  Keep it family-friendly and symbolic: prefer objects, icons and simple scenes (moon, brain, clock, plant, cup) and
  avoid people lying down, bodies or skin, because image services reject such prompts."""

_RULE_REF = ('- The claim MUST be a sentence of the reference text, copied or only trimmed. Never add a fact, a number '
             'or a word that is not in the reference text.')
_RULE_TOPIC = ('- There is no reference text: write well-established general facts only. Never write a digit or a '
               'statistic. Never invent names, studies or dates.')


@dataclass
class ReadResult:
    claims: list[Claim]
    visuals: dict[str, str]                 # claim_id -> English picture description
    used_ai: bool
    grounded: bool                          # True: every claim comes from the user's reference text
    reader: str                             # provider name or "extractive"
    notes: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)


def _tokens(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text)]


def grounding(claim: str, reference: str) -> float:
    """Share of the claim's words that occur in the reference text (1.0 = fully contained)."""
    ref = set(_tokens(reference))
    toks = _tokens(claim)
    return sum(t in ref for t in toks) / len(toks) if toks else 0.0


def local_visual(text: str) -> str:
    """Offline picture description: the claim's content words. Used when no LLM wrote a better one."""
    words = [w for w in _tokens(text) if w not in _STOP and not w.isdigit() and len(w) > 2][:8]
    return "a simple family-friendly symbolic icon scene showing " + ", ".join(words) if words else "a simple abstract scene"


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except ValueError:
        a, b = raw.find("{"), raw.rfind("}")
        if a < 0 or b <= a:
            raise
        return json.loads(raw[a:b + 1])


SLEEP = time.sleep
RETRY_WAITS = (4.0, 10.0, 20.0)          # a busy provider ("503 high demand") is usually back within seconds


def _complete(llm: LLM, system: str, user: str) -> str:
    for wait in (*RETRY_WAITS, None):
        try:
            return llm.complete(system, user)
        except AIError as exc:
            if wait is None or not exc.retryable:
                raise
            SLEEP(exc.retry_after or wait)
    raise AIError("unreachable")


_PATTERNS = {"cause_effect", "comparison", "step_by_step", "trend", "analogy"}


def _from_llm(llm: LLM, topic: str, reference: str, n_scenes: int) -> ReadResult:
    system = SYSTEM.format(n_lo=max(MIN_CLAIMS, n_scenes - 1), n_hi=n_scenes + 3, long_w=15, max_w=MAX_WORDS,
                           claim_rule=_RULE_REF if reference.strip() else _RULE_TOPIC)
    user = f"TOPIC / REQUEST:\n{topic.strip()}\n\n" + (f"REFERENCE TEXT:\n{reference.strip()}\n" if reference.strip()
                                                       else "REFERENCE TEXT: (none)\n")
    data = _extract_json(_complete(llm, system, user))
    scenes = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, list):
        raise ValueError("no 'scenes' list in the answer")
    grounded = bool(reference.strip())
    claims, visuals, rejected, seen = [], {}, [], set()
    for item in scenes:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get("claim", "")).split())
        n = len(text.split())
        why = ""
        if not MIN_WORDS <= n <= MAX_WORDS:
            why = f"{n} words (need {MIN_WORDS}-{MAX_WORDS})"
        elif text.lower() in seen:
            why = "duplicate"
        elif grounded and grounding(text, reference) < GROUND_RATIO:
            why = f"not found in the reference text (only {grounding(text, reference):.0%} of its words)"
        elif not grounded and re.search(r"\d", text):
            why = "contains a number but there is no reference text to check it"
        if why:
            rejected.append(f"{text[:60]!r}: {why}")
            continue
        seen.add(text.lower())
        i = len(claims)
        try:
            imp = float(item.get("importance", 0.6))
        except (TypeError, ValueError):
            imp = 0.6
        pattern = item.get("pattern") if item.get("pattern") in _PATTERNS else "cause_effect"
        facet = " ".join(str(item.get("facet") or "general").lower().split())[:24] or "general"
        cid = f"AI{i + 1:02d}"
        claims.append(Claim(claim_id=cid, text=text, facet=facet, importance=round(min(0.99, max(0.05, imp)), 3),
                            explain_pattern=pattern, has_figure=bool(re.search(r"\d", text)), order=i))
        vis = " ".join(str(item.get("visual", "")).split())
        visuals[cid] = vis[:300] if vis else local_visual(text)
    return ReadResult(claims, visuals, True, grounded, llm.name, rejected=rejected)


def claims_for_duration(t_target_s: float, wpm: float = 165.0, avg_words: float = 18.0) -> int:
    """How many claims of about 18 words fill `t_target_s` seconds of narration (90 s -> 14)."""
    return max(MIN_CLAIMS, round(t_target_s * wpm / 60.0 / avg_words))


def read_input(topic: str, reference: str = "", llm: Optional[LLM] = None, n_scenes: int = 14) -> ReadResult:
    """Claims + picture descriptions for the user's input. Never raises: it falls back to the extractive baseline."""
    notes: list[str] = []
    if llm is not None:
        try:
            res = _from_llm(llm, topic, reference, n_scenes)
            if MIN_CLAIMS <= len(res.claims) < int(n_scenes * 0.7):         # too little narration for the duration: ask once more
                again = _from_llm(llm, topic, reference, n_scenes + 4)
                if len(again.claims) > len(res.claims):
                    res = again
            if len(res.claims) >= MIN_CLAIMS:
                if res.rejected:
                    res.notes.append(f"{len(res.rejected)} AI sentence(s) were dropped by the checks.")
                if not res.grounded:
                    res.notes.append("No reference text: the claims were written by the AI and are NOT verified.")
                return res
            notes.append(f"AI reader ({llm.name}): only {len(res.claims)} usable claim(s) after the checks "
                         f"(need {MIN_CLAIMS}); using the extractive baseline.")
            notes.extend(res.rejected[:3])
        except (AIError, ValueError, KeyError, TypeError) as exc:
            notes.append(f"AI reader ({llm.name}) failed: {exc}; using the extractive baseline.")
    if reference.strip():
        from modules.video.claims import claims_from_text
        claims = claims_from_text(reference)
        vis = {c.claim_id: local_visual(c.text) for c in claims}
        return ReadResult(claims, vis, False, True, "extractive", notes)
    return ReadResult([], {}, False, False, "extractive",
                      notes + ["No reference text and no AI reader: nothing to build the claims from."])
