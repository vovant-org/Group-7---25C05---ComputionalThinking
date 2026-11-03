"""Fit  duration = words * 60 / wpm + pause * sentences  to real measurements.

Usage: python -m evaluation.fit_tts_model [--csv evaluation/data/tts_measurements.csv] [--language en]
Prints the speaking rate, the pause per sentence and the relative noise, plus the lines to
paste into core/config.py and the command to re-run the voice benchmark with measured values.
Needs >= 30 rows with different sentence lengths for a trustworthy fit.
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
from pathlib import Path

from core.config import DATA_DIR


def fit(rows: list[dict]) -> dict:
    w = [float(r["n_words"]) for r in rows]
    s = [float(r["n_sentences"]) for r in rows]
    d = [float(r["duration_s"]) for r in rows]
    sww, sws, sss = sum(x * x for x in w), sum(x * y for x, y in zip(w, s)), sum(y * y for y in s)
    swd, ssd = sum(x * y for x, y in zip(w, d)), sum(x * y for x, y in zip(s, d))
    det = sww * sss - sws * sws
    if len(rows) < 3 or abs(det) < 1e-9:
        raise ValueError("need >= 3 rows with different words/sentences ratios")
    a = (swd * sss - ssd * sws) / det              # seconds per word
    b = (ssd * sww - swd * sws) / det              # pause per sentence (s)
    pred = [a * x + b * y for x, y in zip(w, s)]
    ss_res = sum((di - pi) ** 2 for di, pi in zip(d, pred))
    mean_d = sum(d) / len(d)
    ss_tot = sum((di - mean_d) ** 2 for di in d)
    rel = [di / pi - 1.0 for di, pi in zip(d, pred) if pi > 0]
    return {"n": len(rows), "wpm": 60.0 / a, "pause_s": b, "r2": 1 - ss_res / ss_tot if ss_tot else 1.0,
            "noise_sd": st.pstdev(rel) if len(rel) > 1 else 0.0}


def load(path: Path, language: str | None = None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if language is None or r["language"] == language]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=DATA_DIR / "tts_measurements.csv")
    ap.add_argument("--language", default=None)
    a = ap.parse_args()
    res = fit(load(a.csv, a.language))
    print(f"rows={res['n']}  wpm={res['wpm']:.1f}  pause={res['pause_s']:.2f}s  "
          f"noise_sd={res['noise_sd']:.3f}  R2={res['r2']:.3f}")
    if res["n"] < 30:
        print("WARNING: fewer than 30 rows - collect more before trusting these numbers.")
    print("\nPaste into core/config.py:")
    print(f"VOICE_WPM = {res['wpm']:.1f}   # measured, language={a.language or 'all'}, n={res['n']}")
    print("\nRe-run the voice benchmark with measured values (use the spread of wpm across voices):")
    print(f"py -m evaluation.voice_benchmark --wpm-lo {res['wpm'] * 0.95:.0f} --wpm-hi {res['wpm'] * 1.05:.0f} "
          f"--pause {res['pause_s']:.2f} --noise {res['noise_sd']:.3f}")
