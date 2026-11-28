"""AI director for the jointed stick figure (ANIMATION, step b): an LLM chooses WHICH gesture the figure makes WHEN.

The Motion Planner gives one pose per scene (wave / point / think / shrug). The director reads the narration of every
scene and answers, per scene, a short list of gestures, each tied to a WORD of the narration:

    {"scenes": [{"scene": 3, "beats": [{"from_word": 0, "action": "point"}, {"from_word": 9, "action": "idea"}]}]}

`from_word` is the index of the word (0-based, whitespace split: the same words as `visual_engine.sync.word_times`), so the
gesture starts when the narrator says that word. The figure still walks in first (stickman.beats_from_directions).

Safety rules (the model only picks from a menu; it never draws or moves anything itself):
  * only the actions in ALLOWED (walk / run are not offered: the walk-in is fixed);
  * from_word must be inside the narration; beats are sorted, consecutive repeats merged, at most MAX_BEATS per scene;
  * anything invalid is dropped with a reason; a scene without a valid answer keeps the default choreography;
  * `direct_scenes` never raises: a provider error gives no directions and a note, and the video is made as before.
Privacy: the narration text is sent to an online LLM, so callers must have the user's consent (like the AI reader).
ASSUMPTION (not measured): the prompt wording and MAX_BEATS = 5; whether viewers prefer these gestures is untested.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence

from modules.ai.llm import LLM
from modules.ai.net import AIError
from modules.ai.reader import _complete, _extract_json
from modules.video.stickman import ACTIONS, MOVING

MAX_BEATS = 5
ACTION_HELP = {
    "talk": "explaining with hand gestures (the default between key moments)",
    "wave": "greeting or opening (hook scene only)",
    "point": "pointing at the object or chart on screen",
    "think": "a question or something to wonder about",
    "idea": "an insight, a 'got it', a conclusion",
    "shrug": "doubt, 'it depends', a limitation",
    "surprised": "something unexpected or surprising",
    "nod": "agreement, confirming a point",
    "cheer": "success, a happy ending (summary scene)",
    "jump": "big excitement (use rarely)",
    "idle": "a calm pause",
}
ALLOWED = tuple(a for a in ACTION_HELP if a in ACTIONS and a not in MOVING)

SYSTEM = """You are the director of a 2D stick-figure explainer video. For each scene you get the narration with every
word numbered ("0:Sleep 1:helps 2:the ..."). Choose the gestures the figure makes while the narrator speaks.
Answer with JSON only:
{{"scenes":[{{"scene":0,"beats":[{{"from_word":0,"action":"point"}}]}}]}}
Rules:
- "action" must be one of: {menu}
- "from_word" is the number of the word at which the gesture starts. Give 2 to {max_beats} beats per scene, in order,
  the first one with from_word 0. Beats must be at least 4 words apart.
- Match the gesture to the meaning of the words: think for a question, idea for an insight or conclusion, shrug for doubt,
  surprised for something unexpected, nod to confirm, point when the sentence refers to something shown, talk otherwise.
- Never use the same action twice in a row. Use jump and cheer rarely.
- A scene with role "hook" starts with wave. A scene with role "summary" ends with cheer or nod.
- Answer for EVERY scene id you are given, with the same "scene" number."""


@dataclass
class DirectResult:
    directions: dict = field(default_factory=dict)     # scene_id -> [(action, from_word)]
    info: dict = field(default_factory=dict)           # JSON-safe summary for the report


def _items(scenes: Sequence) -> list:
    n, out = len(scenes), []
    for i, s in enumerate(scenes):
        role = "hook" if i == 0 else "summary" if i == n - 1 else "body"
        words = " ".join(f"{k}:{w}" for k, w in enumerate(s.narration.split()))
        out.append({"scene": s.scene_id, "role": role, "words": words})
    return out


def _check(raw_beats, n_words: int, max_beats: int) -> tuple:
    """([(action, from_word)], [why dropped]) for one scene."""
    good, why = [], []
    if not isinstance(raw_beats, list):
        return [], ["beats is not a list"]
    for b in raw_beats:
        if not isinstance(b, dict):
            why.append("a beat is not an object")
            continue
        action = str(b.get("action", "")).strip().lower()
        try:
            w = int(b.get("from_word"))
        except (TypeError, ValueError):
            why.append(f"{action or '?'}: from_word is not a number")
            continue
        if action not in ALLOWED:
            why.append(f"unknown action {action!r}")
        elif not 0 <= w < n_words:
            why.append(f"{action}: from_word {w} is outside the narration ({n_words} words)")
        else:
            good.append((action, w))
    good.sort(key=lambda x: x[1])
    merged = []
    for action, w in good:                             # a repeat of the previous action adds nothing
        if not merged or merged[-1][0] != action:
            merged.append((action, w))
    return merged[:max_beats], why


def direct_scenes(llm: LLM, scenes: Sequence, max_beats: int = MAX_BEATS) -> DirectResult:
    """Gestures per scene from an LLM. Never raises; scenes without a valid answer are simply absent."""
    info = {"provider": getattr(llm, "name", "llm"), "scenes": len(scenes), "scenes_directed": 0, "rejected": [], "notes": []}
    if not scenes:
        return DirectResult({}, info)
    system = SYSTEM.format(menu=", ".join(f"{a} ({ACTION_HELP[a]})" for a in ALLOWED), max_beats=max_beats)
    user = "SCENES:\n" + json.dumps(_items(scenes), ensure_ascii=False)
    try:
        data = _extract_json(_complete(llm, system, user))
        items = data.get("scenes") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise ValueError("no 'scenes' list in the answer")
    except (AIError, ValueError, KeyError, TypeError) as exc:
        info["notes"].append(f"AI director ({info['provider']}) failed: {exc}; the default choreography is used.")
        return DirectResult({}, info)
    info["provider"] = getattr(llm, "name", info["provider"])      # FallbackLLM learns its provider while answering
    words = {s.scene_id: len(s.narration.split()) for s in scenes}
    out = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            sid = int(item.get("scene"))
        except (TypeError, ValueError):
            continue
        if sid not in words or sid in out:
            continue
        beats, why = _check(item.get("beats"), words[sid], max_beats)
        info["rejected"] += [f"scene {sid}: {w}" for w in why]
        if beats:
            out[sid] = beats
    info["scenes_directed"] = len(out)
    missing = sorted(set(words) - set(out))
    if missing:
        info["notes"].append(f"No valid directions for scene(s) {missing}: they keep the default choreography.")
    return DirectResult(out, info)
