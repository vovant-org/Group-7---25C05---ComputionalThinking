"""REASON step: research a topic when the user has only a question and no material.

The rest of the pipeline is built on REFERENCE TEXT (full sentences of 8-24 words, `modules/video/claims.py`).
Until now that text had to be typed, uploaded or taken from a demo pack. Here a free LLM (the same providers as the
AI reader, `modules/ai/llm.py`: Gemini with a free key, Pollinations without a key) writes it from the question:

    "Vì sao TP.HCM ngập khi mưa lớn?"  ->  14-18 Vietnamese sentences: hook, causes, mechanism, example, summary

The result is shown in the material box so the user can read and correct it BEFORE anything is built; from there
the existing flow (claims -> scenes -> voice -> video) is unchanged.

Project rule "no invented facts": a model's text is not verified, so it is checked and labelled.
  * every sentence must have 8-24 words and be in the language of the question (detect_language);
  * sentences with a digit are dropped (no invented statistics, years or percentages);
  * duplicates are dropped; at least MIN_SENTENCES must survive, else one retry, else an error;
  * the UI marks the material "written by AI, not verified" and the project record keeps `content_origin: ai`.
ASSUMPTION: these checks catch format problems, not wrong facts. The user's review is the real check.
Privacy: the question (and nothing else) is sent to an online service, only after the user's consent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from modules.ai.llm import LLM
from modules.ai.net import AIError
from modules.ai.reader import MAX_WORDS, MIN_WORDS, _complete, _extract_json
from modules.voice_library.language import detect_language

MIN_SENTENCES = 8
ROLES = ("hook", "explain", "example", "summary")
LANG_NAMES = {"en": "English", "vi": "Vietnamese (tiếng Việt, with full tone marks)"}

SYSTEM = """You are the research step of an explainer-video app. The user asks a question; you write the reference
text the video will be built from. Answer with JSON only:
{{"title":"...","sentences":[{{"text":"...","role":"hook|explain|example|summary"}}]}}
Rules:
- Write in {language}, whatever language the instructions are in.
- Give {n_lo} to {n_hi} sentences, in the order a good explainer tells them: 1-2 "hook" sentences that make the
  question concrete, then "explain" sentences (causes, mechanism, consequences; each one new idea), 2-3 "example"
  sentences (an everyday example or an analogy a teenager understands), and 1-2 "summary" sentences.
- Each "text" is ONE complete sentence of {lo_w}-{hi_w} words (aim for about 16). No lists, no headings, no questions
  except possibly the first hook.
- Only well-established, widely accepted knowledge. Never write a digit, a statistic, a year, a percentage, a study,
  a quote or the name of a real person or company. Prefer cause-and-effect explanations.
- If the question rests on a doubtful or exaggerated premise (e.g. "always", "everyone"), say so politely in one
  sentence and explain what is generally true instead. Stay neutral on politics and religion.
- "title": a short title for the video (max 8 words), same language."""


@dataclass
class ResearchResult:
    ok: bool
    text: str = ""                                # reference text to put in the material box
    title: str = ""
    sentences: list[str] = field(default_factory=list)
    language: str = "en"
    provider: str = ""
    rejected: list[str] = field(default_factory=list)
    error: str = ""


def sentence_count(t_target_s: float, wpm: float = 165.0, avg_words: float = 16.0) -> int:
    """Sentences of ~16 words that fill `t_target_s` seconds of narration (90 s -> 15), with room for the checks."""
    return max(MIN_SENTENCES + 2, round(t_target_s * wpm / 60.0 / avg_words))


def _check(item, language: str, seen: set) -> tuple[str, str]:
    """(clean sentence, "") or ("", why it was dropped)."""
    text = " ".join(str(item.get("text", "") if isinstance(item, dict) else item).split()).strip(" -•*")
    n = len(text.split())
    if not MIN_WORDS <= n <= MAX_WORDS:
        return "", f"{text[:50]!r}: {n} words (need {MIN_WORDS}-{MAX_WORDS})"
    if re.search(r"\d", text):
        return "", f"{text[:50]!r}: contains a number that cannot be checked"
    if detect_language(text) != language:
        return "", f"{text[:50]!r}: not in {LANG_NAMES.get(language, language).split(' (')[0]}"
    if text.lower() in seen:
        return "", f"{text[:50]!r}: duplicate"
    if text[-1] not in ".!?…":
        text += "."
    return text, ""


def _ask(llm: LLM, question: str, instructions: str, language: str, n: int) -> tuple[str, list[tuple[str, str]], list[str]]:
    system = SYSTEM.format(language=LANG_NAMES.get(language, language), n_lo=n, n_hi=n + 3, lo_w=12, hi_w=MAX_WORDS - 2)
    user = f"QUESTION:\n{question.strip()}\n" + (f"\nEXTRA INSTRUCTIONS FROM THE USER:\n{instructions.strip()}\n" if instructions.strip() else "")
    data = _extract_json(_complete(llm, system, user))
    items = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("no 'sentences' list in the answer")
    kept, rejected, seen = [], [], set()
    for item in items:
        text, why = _check(item, language, seen)
        if why:
            rejected.append(why)
            continue
        seen.add(text.lower())
        role = item.get("role") if isinstance(item, dict) and item.get("role") in ROLES else "explain"
        kept.append((text, role))
    title = " ".join(str(data.get("title", "")).split())[:80]
    return title, kept, rejected


def to_text(kept: list[tuple[str, str]]) -> str:
    """One paragraph per role change, so the material box reads like a short article."""
    paras, last = [], None
    for text, role in kept:
        if role != last:
            paras.append([])
            last = role
        paras[-1].append(text)
    return "\n\n".join(" ".join(p) for p in paras)


def research_topic(question: str, llm: Optional[LLM], *, instructions: str = "", language: Optional[str] = None,
                   t_target_s: float = 90.0) -> ResearchResult:
    """Reference text for `question`. Never raises: a failure comes back as ok=False with a readable error."""
    question = " ".join((question or "").split())
    language = language or detect_language(question) or "en"
    if not question:
        return ResearchResult(False, language=language, error="Type your question first.")
    if llm is None:
        return ResearchResult(False, language=language, error="Choose an AI provider to research the topic.")
    n = sentence_count(t_target_s)
    best: Optional[tuple] = None
    try:
        for attempt in range(2):                          # one retry when too few sentences pass the checks
            title, kept, rejected = _ask(llm, question, instructions, language, n + 3 * attempt)
            if best is None or len(kept) > len(best[1]):
                best = (title, kept, rejected)
            if len(kept) >= MIN_SENTENCES:
                break
    except (AIError, ValueError, KeyError, TypeError) as exc:
        if best is None:
            return ResearchResult(False, language=language, provider=llm.name, error=f"The AI could not answer: {exc}")
    title, kept, rejected = best
    from modules.video.claims import claims_from_text          # the extractor the pipeline will use on this text
    usable = {c.text for c in claims_from_text(to_text(kept))}
    rejected += [f"{t[:50]!r}: the sentence splitter would not keep it" for t, _ in kept if t not in usable]
    kept = [(t, r) for t, r in kept if t in usable]
    if len(kept) < MIN_SENTENCES:
        return ResearchResult(False, language=language, provider=llm.name, rejected=rejected,
                              error=f"Only {len(kept)} usable sentence(s) after the checks (need {MIN_SENTENCES}). Try again "
                                    "or rephrase the question.")
    return ResearchResult(True, to_text(kept), title, [t for t, _ in kept], language, llm.name, rejected)
