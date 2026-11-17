"""Benchmark of the ANIMATION format (report 5.3 / 5.9.10, criteria S11, S12, S13).

Two parts, both offline (no TTS, no network, no MP4 written):

A. Motion quality, measured on REAL frames drawn by the cut-out renderer. Three variants of the same scenes:
     v0  still      the character is drawn but never moves (frame at one fixed time), the "no animation" baseline
     v1  uniform    keyframes and poses, but every scene has energy 1.0 (no extra life for important scenes)
     v2  planned    the shipped version: Motion Planner energy 1.4 for hook, summary and importance >= 0.75
   Per scene it measures the motion score = mean absolute pixel change between frames 1/8 of the scene apart
   (0-255 scale, area above the subtitle band), whether the subtitle band stays untouched, and the draw time.
   S11 (every scene really moves) is counted as motion score > MOVES_MIN.

B. Duration loop on the animation format: the same sweep as evaluation/video_benchmark.py, but for animation
   requests, with the loop OFF ("before") and ON ("after"). The voice is SIMULATED (SilentEngine at a chosen
   speed); this measures the loop, not a real voice.

    python -m evaluation.animation_benchmark      writes outputs/animation_motion.csv and outputs/animation_loop.csv
"""
from __future__ import annotations

import csv
import dataclasses
import statistics
import sys
import time
from pathlib import Path

import numpy as np

from core.config import OUTPUT_DIR
from modules.pipeline.pipeline import run_pipeline
from modules.pipeline.sample_claims import get_sample_claims
from modules.router.router import Request
from modules.video import animation
from modules.video.animation import compose_animation_scene
from modules.video.composer import Style
from modules.video.make_video import UNAVAILABLE_MODES, make_video
from modules.video.motion_planner import HIGH_IMPORTANCE, plan_motion
from modules.video.voice import SilentEngine

PACKS = ["sleep", "inflation"]
ST = Style()
SCENE_S = 7.0                       # length used to draw the frames
SAMPLES = 9                         # 9 frames = 8 steps across the scene
MOVES_MIN = 0.05                    # motion score above this counts as "moves" (S11)
VARIANTS = ["v0 still", "v1 uniform energy", "v2 planned (shipped)"]

TARGETS = [60, 90, 120]
TRUE_WPM = [120, 135, 150, 165, 180, 195, 210]


# ------------------------------------------------------------------ part A: motion
def _uniform_energy(scene, index, total):
    return dataclasses.replace(plan_motion(scene, index, total), energy=1.0)


def _scenes(pack: str):
    res = run_pipeline(Request(f"Make a 90-second animated video about {pack}", budget=400),
                       get_sample_claims(pack), unavailable_modes=UNAVAILABLE_MODES)
    assert res.ok, res.messages
    return res.scenes


def _frames(cs, variant: str):
    r = cs.make_renderer(SCENE_S, SCENE_S, 0, ST)
    if variant == "v0 still":
        still = r.frame(SCENE_S / 2)
        return [still] * SAMPLES
    return [r.frame(SCENE_S * i / (SAMPLES - 1)) for i in range(SAMPLES)]


def measure(cs, variant: str) -> dict:
    top = ST.size[1] - ST.sub_h
    t0 = time.perf_counter()
    frames = _frames(cs, variant)
    draw_s = (time.perf_counter() - t0) / SAMPLES
    f32 = [f[:top].astype(np.float32) for f in frames]
    score = float(np.mean([np.abs(b - a).mean() for a, b in zip(f32, f32[1:])]))
    band = np.asarray(cs.base)[top:]
    clean = all(np.array_equal(f[top:], band) for f in frames)
    return {"motion": score, "band_clean": clean, "draw_s": draw_s}


def part_a() -> list[dict]:
    rows = []
    original = animation.plan_motion
    for pack in PACKS:
        scenes = _scenes(pack)
        total = len(scenes)
        for variant in VARIANTS:
            animation.plan_motion = _uniform_energy if variant == "v1 uniform energy" else original
            try:
                for i, sc in enumerate(scenes):
                    cs = compose_animation_scene(sc, sc.narration, ST, i, total)
                    m = measure(cs, variant)
                    rows.append({"pack": pack, "variant": variant, "scene": i, "importance": sc.importance,
                                 "important": int(sc.importance >= HIGH_IMPORTANCE or i in (0, total - 1)),
                                 "motion": round(m["motion"], 4), "moves": int(m["motion"] > MOVES_MIN),
                                 "band_clean": int(m["band_clean"]), "draw_ms": round(m["draw_s"] * 1000, 1)})
            finally:
                animation.plan_motion = original
    return rows


def summarize_a(rows: list[dict]) -> None:
    print("A. Motion quality on real frames (both packs, all scenes)")
    print(f"   {'variant':24}{'S11 moving':>12}{'band clean':>12}{'motion all':>12}{'motion key':>12}{'motion rest':>13}{'ms/frame':>10}")
    for v in VARIANTS:
        sub = [r for r in rows if r["variant"] == v]
        key = [r["motion"] for r in sub if r["important"]]
        rest = [r["motion"] for r in sub if not r["important"]]
        print(f"   {v:24}{sum(r['moves'] for r in sub):>5}/{len(sub):<6}{sum(r['band_clean'] for r in sub):>5}/{len(sub):<6}"
              f"{statistics.mean(r['motion'] for r in sub):>12.3f}{statistics.mean(key):>12.3f}"
              f"{statistics.mean(rest):>13.3f}{statistics.mean(r['draw_ms'] for r in sub):>10.1f}")
    print("   (motion = mean abs pixel change between frames 1/8 scene apart, 0-255; key = hook, summary, importance >= 0.75)")


# ------------------------------------------------------------------ part B: duration loop
def run_loop(pack: str, target: int, wpm: float, adjustments: int):
    text = f"Make an animated video of {target} seconds about {pack}"
    return make_video(text, get_sample_claims(pack), Path("unused.mp4"), engine=SilentEngine(wpm=wpm),
                      render=False, max_adjustments=adjustments)


def part_b() -> list[dict]:
    rows = []
    for pack in PACKS:
        for target in TARGETS:
            for wpm in TRUE_WPM:
                for adj in (0, 2):
                    r = run_loop(pack, target, wpm, adj)
                    rep = r.report
                    rows.append({"pack": pack, "target_s": target, "true_wpm": wpm, "adjustments_allowed": adj,
                                 "ok": int(r.ok), "total_s": rep.get("total_s", ""), "deviation": rep.get("deviation", ""),
                                 "steps_used": len(r.log)})
    return rows


def summarize_b(rows: list[dict]) -> None:
    print("B. Duration loop on the animation format (simulated voice; planner assumes 165 wpm)")
    for adj, label in ((0, "before (no loop)"), (2, "after (N0-N4 loop)")):
        sub = [r for r in rows if r["adjustments_allowed"] == adj]
        print(f"   {label:22}{sum(r['ok'] for r in sub)}/{len(sub)} runs pass S12 and S13")
    for wpm in TRUE_WPM:
        b = [r for r in rows if r["true_wpm"] == wpm and r["adjustments_allowed"] == 0]
        a = [r for r in rows if r["true_wpm"] == wpm and r["adjustments_allowed"] == 2]
        print(f"     {wpm:3d} wpm: {sum(r['ok'] for r in b):2d}/{len(b)} -> {sum(r['ok'] for r in a):2d}/{len(a)}")


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main(out_dir: Path = OUTPUT_DIR) -> int:
    t0 = time.time()
    a = part_a()
    _write(out_dir / "animation_motion.csv", a)
    summarize_a(a)
    b = part_b()
    _write(out_dir / "animation_loop.csv", b)
    summarize_b(b)
    print(f"done in {time.time() - t0:.0f} s -> {out_dir / 'animation_motion.csv'}, {out_dir / 'animation_loop.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
