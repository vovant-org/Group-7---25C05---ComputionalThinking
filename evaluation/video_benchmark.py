"""Benchmark of the duration-adjustment loop of the video maker (report M13: N4 -> N3 -> N2, plus calibration N0 and re-plan N1).

For every combination of speaking speed, claim pack and target duration it plans the video with the
loop switched OFF (max_adjustments = 0, "before") and ON (2, "after") and counts how many runs reach
a timeline that passes S12 (60-120 s) and S13 (within 5 % of the target).

IMPORTANT: the voice is SIMULATED (SilentEngine speaks at a chosen rate). The planner always assumes
165 wpm, so a "true" rate away from 165 models a real voice that is slower or faster than expected.
This measures the loop, not any real TTS. No video is rendered.

    python -m evaluation.video_benchmark       writes outputs/video_benchmark.csv
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

from core.config import OUTPUT_DIR
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.make_video import make_video
from modules.video.voice import SilentEngine

PACKS = ["sleep", "inflation", "sleep_vi", "inflation_vi"]
TARGETS = [60, 90, 120]
TRUE_WPM = [120, 135, 150, 165, 180, 195, 210]
TOPIC = {"sleep": "sleep", "inflation": "inflation", "sleep_vi": "giấc ngủ", "inflation_vi": "lạm phát"}


def run(pack: str, target: int, wpm: float, adjustments: int):
    word = "Tạo video infographic" if pack.endswith("_vi") else "Make an infographic video"
    text = (f"{word} {target} giây về {TOPIC[pack]}" if pack.endswith("_vi")
            else f"{word} of {target} seconds about {TOPIC[pack]}")
    return make_video(text, get_sample_claims(pack), Path("unused.mp4"), engine=SilentEngine(wpm=wpm),
                      render=False, max_adjustments=adjustments)


def main(out: Path = OUTPUT_DIR / "video_benchmark.csv") -> int:
    rows = []
    t0 = time.time()
    for pack in PACKS:
        for target in TARGETS:
            for wpm in TRUE_WPM:
                for adj in (0, 2):
                    r = run(pack, target, wpm, adj)
                    rep = r.report
                    rows.append({"pack": pack, "target_s": target, "true_wpm": wpm, "adjustments_allowed": adj,
                                 "ok": int(r.ok), "total_s": rep.get("total_s", ""), "deviation": rep.get("deviation", ""),
                                 "steps_used": len(r.log), "methods": "".join(sorted({l[:2] for l in r.log}))})
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} runs in {time.time() - t0:.0f} s -> {out}")
    for adj, label in ((0, "before (no loop)"), (2, "after (N0-N4 loop)")):
        sub = [r for r in rows if r["adjustments_allowed"] == adj]
        print(f"  {label:24} {sum(r['ok'] for r in sub)}/{len(sub)} runs pass S12 and S13")
    print("  by true speed (planner assumes 165 wpm):")
    for wpm in TRUE_WPM:
        b = [r for r in rows if r["true_wpm"] == wpm and r["adjustments_allowed"] == 0]
        a = [r for r in rows if r["true_wpm"] == wpm and r["adjustments_allowed"] == 2]
        print(f"    {wpm:3d} wpm: {sum(r['ok'] for r in b):2d}/{len(b)} -> {sum(r['ok'] for r in a):2d}/{len(a)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
