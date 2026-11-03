"""Voice Segmenter benchmark (S19). Usage: python -m evaluation.voice_benchmark [--n 300] [--seed 11]

The TTS is SIMULATED (modules/providers/mock_tts.py): true speaking rate differs from the
planning wpm, with noise and a pause after each sentence. The numbers show how the algorithms
cope with estimation error; they are NOT measurements of a real voice.
Calibration modes: none = nominal 165 wpm, no pause term (the report's formula);
wpm = true wpm known; wpm+pause = true wpm and true pause known (what to-do items 12/14 would give).
"""
from __future__ import annotations

import argparse
import csv
import random

from core.config import OUTPUT_DIR, VOICE_WPM
from modules.providers.mock_tts import MockTTS
from modules.voice_segmenter.segmenter import (
    ALGORITHMS, VoiceParams, expected_voice_count, in_band, repair_after_tts, segment_voices,
)

TRUE_PAUSE = 0.3
SHORT_S = 5.0          # a non-last voice shorter than this sounds choppy
CALIBRATIONS = ("none", "wpm", "wpm+pause")


def make_script(rng: random.Random, idx: int, t_target: int) -> list[str]:
    """Random narration: ~W_target words, sentence lengths ~ N(19, 7) clipped to 5..40 words."""
    target_words = VOICE_WPM * t_target / 60.0
    sents, total, i = [], 0, 0
    while total < target_words:
        n = int(min(40, max(5, round(rng.gauss(19, 7)))))
        sents.append(" ".join([f"t{idx}x{i}"] + ["w"] * (n - 1)) + ".")
        total, i = total + n, i + 1
    return sents


def params_for(cal: str, true_wpm: float, max_sentences: int = 2) -> VoiceParams:
    if cal == "none":
        return VoiceParams(max_sentences=max_sentences)
    if cal == "wpm":
        return VoiceParams(wpm=true_wpm, max_sentences=max_sentences)
    return VoiceParams(wpm=true_wpm, pause_s=TRUE_PAUSE, max_sentences=max_sentences)


def evaluate(n_scripts: int, seed: int, algos=None, max_sentences: int = 2, cals=CALIBRATIONS):
    rng = random.Random(seed)
    rows = []
    for idx in range(n_scripts):
        t = rng.choice([60, 90, 120])
        script = make_script(rng, idx, t)
        true_wpm = rng.uniform(145, 185)
        tts = MockTTS(true_wpm, pause_s=TRUE_PAUSE, seed=seed)
        for cal in cals:
            p = params_for(cal, true_wpm, max_sentences)
            for algo in (algos or ALGORITHMS):
                seg = segment_voices(script, algo, p)
                est_ok = sum(in_band(u.est_s, p, i == len(seg.units) - 1) for i, u in enumerate(seg.units))
                for repair in (False, True):
                    if repair:
                        res = repair_after_tts(seg.units, tts, p)
                        units, durs, calls = res.units, res.durations, res.synth_calls
                    else:
                        units, durs, calls = seg.units, [tts(u.sentences) for u in seg.units], len(seg.units)
                    last, (lo, hi) = len(units) - 1, expected_voice_count(t)
                    rows.append({
                        "script": idx, "t_target": t, "algorithm": algo, "calibration": cal,
                        "max_sentences": max_sentences, "repair": int(repair), "voices": len(units),
                        "est_voices": len(seg.units), "est_in_band": est_ok,
                        "actual_in_band": sum(in_band(d, p, i == last) for i, d in enumerate(durs)),
                        "actual_within_tol": sum(in_band(d, p, i == last, p.tol) for i, d in enumerate(durs)),
                        "short_voices": sum(d < SHORT_S for i, d in enumerate(durs) if i != last),
                        "count_ok": int(lo <= len(units) <= hi), "synth_calls": calls,
                        "needs_shorten": len(seg.needs_shorten),
                    })
    return rows


def _line(label, r):
    v, ev = sum(x["voices"] for x in r), sum(x["est_voices"] for x in r)
    pct = lambda k, d: f"{100 * sum(x[k] for x in r) / d:.1f}%"
    return (f"| {label} | {pct('est_in_band', ev)} | {pct('actual_in_band', v)} | {pct('actual_within_tol', v)} "
            f"| {pct('count_ok', len(r))} | {sum(x['voices'] for x in r) / len(r):.1f} "
            f"| {sum(x['short_voices'] for x in r) / len(r):.2f} "
            f"| {sum(x['synth_calls'] for x in r) / len(r):.1f} |")


HEAD = ("| {first} | Planned in-band | Actual in-band (S19) | Within ±1 s | Voice count in 4(f) range "
        "| Voices / script | Voices < 5 s / script | TTS calls / script |\n|---|---|---|---|---|---|---|---|")


def summarize(rows):
    out = ["**A. Algorithm x calibration (no post-TTS repair)**\n", HEAD.format(first="Algorithm / calibration")]
    for algo in ALGORITHMS:
        for cal in CALIBRATIONS:
            r = [x for x in rows if x["algorithm"] == algo and x["calibration"] == cal and x["repair"] == 0]
            out.append(_line(f"{algo} / {cal}", r))
    out += ["", "**B. Post-TTS repair (report 5.7), F4_dp_share**\n", HEAD.format(first="Calibration / repair")]
    for cal in CALIBRATIONS:
        for rep in (0, 1):
            r = [x for x in rows if x["algorithm"] == "F4_dp_share" and x["calibration"] == cal and x["repair"] == rep]
            out.append(_line(f"{cal} / {'repair' if rep else 'no repair'}", r))
    return "\n".join(out)


def sensitivity(n_scripts: int, seed: int):
    out = ["**C. Max sentences per voice, F4_dp_share, wpm+pause calibrated, no repair**\n",
           HEAD.format(first="Max sentences")]
    for k in (1, 2, 3):
        rows = evaluate(n_scripts, seed, ["F4_dp_share"], k, ("wpm+pause",))
        out.append(_line(str(k), [x for x in rows if x["repair"] == 0]))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rows = evaluate(a.n, a.seed)
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / "voice_benchmark.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"scripts={a.n} seed={a.seed} (SIMULATED TTS, pause={TRUE_PAUSE}s) -> outputs/voice_benchmark.csv\n")
    print(summarize(rows))
    print("\n" + sensitivity(a.n, a.seed))
