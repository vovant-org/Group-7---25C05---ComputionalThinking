"""Voice-over synchronisation: WHEN does the narrator say each word? (report 5.9.8 option H1, per word)

The real audio duration of a scene is known (TTS or measured). Inside it each word gets a share of the time
proportional to its length, plus a pause after punctuation. This is the same idea as the subtitle timing
(H1: proportional to characters); H2 (TTS timestamps) would be exact but needs provider support.
`word_times` is monotonic and ends at audio_s, so an object tied to word i appears when word i is spoken.
"""
from __future__ import annotations

PAUSE_SOFT = 1.0      # extra weight after , ; :
PAUSE_HARD = 2.0      # extra weight after . ? !
LATEST = 0.92         # latest appearance, as a fraction of the scene
LEAD_S = 0.20         # objects appear this long BEFORE the word (the eye needs a moment)


def word_times(narration: str, audio_s: float) -> list[tuple[str, float, float]]:
    """[(word, start_s, end_s)] for every whitespace-separated word, inside [0, audio_s]."""
    words = narration.split()
    if not words:
        return []
    weights = []
    for w in words:
        core = w.strip(".,;:!?…\"'()[]")
        wt = 1.0 + 0.45 * len(core)
        if w[-1:] in ",;:":
            wt += PAUSE_SOFT
        elif w[-1:] in ".?!…":
            wt += PAUSE_HARD
        weights.append(wt)
    total = sum(weights)
    out, acc = [], 0.0
    for w, wt in zip(words, weights):
        out.append((w, audio_s * acc / total, audio_s * (acc + wt) / total))
        acc += wt
    return out


def mention_time(times: list[tuple[str, float, float]], word_index: int | None) -> float | None:
    """Start time of a word, or None when the object is not tied to a word."""
    if word_index is None or not 0 <= word_index < len(times):
        return None
    return times[word_index][1]


def appear_time(t_mention: float | None, duration_s: float, slot: int) -> float:
    """When an object becomes visible. Mentioned objects: just before the word. Others (filler): spread over
    the first third of the scene. Always inside [0.05, 0.92] x duration (a later object would not be on screen long enough to be seen)."""
    t = t_mention - LEAD_S if t_mention is not None else duration_s * (0.10 + 0.12 * slot)
    return min(max(t, 0.05 * duration_s), LATEST * duration_s)
