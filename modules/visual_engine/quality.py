"""Step 5 - quality checks of the finished picture, on real frames and on the real timeline.

  empty scenes      the objects of a scene cover at least MIN_COVERAGE of the picture area (a presenter alone is
                    not an illustration of the narration)
  repeated visuals  no scene repeats the object set of the previous scene; most scenes of a video differ
  subtitles         every word of the narration is in a cue, cues are ordered, inside their scene, readable length
  audio             the MP4 has an audible audio track (skipped for the silent engine, with a note)
  duration          S12 / S13 on the real timeline (and on the MP4 when it exists)
  sync              each object appears close to the moment its word is spoken

ASSUMPTIONS (thresholds are our own, not measured): MIN_COVERAGE 0.4 %, DISTINCT_MIN 60 %, SYNC_TOL_S 0.5 s,
cue length 0.5-8 s, audible = max volume above -50 dB.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Optional, Sequence

import numpy as np

from modules.video.animation import AnimatedScene, LayerRenderer
from modules.video.composer import Style
from modules.video.subtitles import make_cues
from modules.video.voice import find_ffmpeg
from modules.visual_engine.engine import TopicScene

MIN_COVERAGE = 0.004
DISTINCT_MIN = 0.60
SYNC_TOL_S = 0.5
CUE_MIN_S, CUE_MAX_S = 0.5, 8.0
AUDIBLE_DB = -50.0
ROUND_S = 2e-3                                 # cue times are rounded to 1 ms
FIGURE_PARTS = frozenset({"arm_back", "body", "head", "arm_front", "stickman"})   # stickman: the jointed figure


@dataclass
class QualityReport:
    checks: dict = field(default_factory=dict)       # name -> {"pass": bool, "detail": str}
    problems: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(v["pass"] for v in self.checks.values())

    def add(self, name: str, ok: bool, detail: str, problems: Sequence[str] = ()) -> None:
        self.checks[name] = {"pass": bool(ok), "detail": detail}
        self.problems.extend(problems)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "checks": self.checks, "problems": self.problems, "stats": self.stats}


# ------------------------------------------------------------------ empty scenes
def object_coverage(ts: TopicScene, duration_s: float, audio_s: float, st: Style, at: float = 0.9) -> float:
    """Share of the picture area (between header and subtitle band) that the OBJECTS of the scene change
    compared with the bare backdrop, at `at` x duration. The presenter figure is left out."""
    layers = [l for l in ts.build_layers(duration_s, audio_s, st) if l.name not in FIGURE_PARTS]
    if not layers:
        return 0.0
    scene = AnimatedScene(scene_id=ts.scene_id, plan=ts.plan, base=ts.base, layers=layers)
    frame = LayerRenderer(scene, duration_s, st).frame(duration_s * at).astype(np.int16)
    base = np.asarray(ts.base).astype(np.int16)
    h = st.size[1]
    top, bottom = st.header_h, h - st.sub_h
    changed = np.abs(frame - base).max(axis=2) > 24
    return float(changed[top:bottom].mean())


def check_empty_scenes(scenes: Mapping[int, TopicScene], entries, st: Style, report: QualityReport) -> None:
    cov, empty = {}, []
    for i, e in enumerate(entries):
        c = object_coverage(scenes[e.scene_id], e.duration_s, e.audio_duration_s, st)
        cov[e.scene_id] = round(c, 4)
        if c < MIN_COVERAGE:
            empty.append(f"scene {e.scene_id}: objects cover only {c:.2%} of the picture (needs {MIN_COVERAGE:.1%})")
    report.stats["object_coverage"] = cov
    report.add("empty_scenes", not empty, f"{len(entries) - len(empty)}/{len(entries)} scenes have visible objects "
               f"(min coverage {min(cov.values(), default=0):.2%})", empty)


# ------------------------------------------------------------------ repeated visuals
def check_repeats(scenes: Sequence[TopicScene], report: QualityReport) -> None:
    sigs = [ts.signature for ts in scenes]
    consecutive = [f"scenes {scenes[i - 1].scene_id} and {scenes[i].scene_id} show the same objects {sigs[i]}"
                   for i in range(1, len(sigs)) if sigs[i] == sigs[i - 1]]
    distinct = len(set(sigs)) / max(1, len(sigs))
    report.stats["distinct_visuals"] = round(distinct, 3)
    report.add("repeated_visuals", not consecutive and distinct >= DISTINCT_MIN,
               f"{len(set(sigs))} different object sets in {len(sigs)} scenes ({distinct:.0%}); "
               f"{len(consecutive)} repeats of the previous scene", consecutive)


# ------------------------------------------------------------------ subtitles
def check_subtitles(entries, report: QualityReport) -> None:
    cues = make_cues(entries)
    problems = []
    for a, b in zip(cues, cues[1:]):
        if b.start_s < a.end_s - 1e-6:
            problems.append(f"cues overlap at {b.start_s:.2f}s")
    for c in cues:
        if not CUE_MIN_S <= c.end_s - c.start_s <= CUE_MAX_S:
            problems.append(f"cue '{c.text[:24]}' lasts {c.end_s - c.start_s:.2f}s (limit {CUE_MIN_S}-{CUE_MAX_S}s)")
    for e in entries:
        mine = [c for c in cues if e.start_s - ROUND_S <= c.start_s < e.start_s + e.duration_s - ROUND_S]
        words_in = sum(len(c.text.split()) for c in mine)
        if words_in != len(e.narration.split()):
            problems.append(f"scene {e.scene_id}: subtitles carry {words_in} of {len(e.narration.split())} narration words")
        if any(c.end_s > e.start_s + e.duration_s + ROUND_S for c in mine):
            problems.append(f"scene {e.scene_id}: a cue runs past the end of its scene")
    report.stats["cues"] = len(cues)
    report.add("subtitles", not problems, f"{len(cues)} cues cover all narration words, ordered, inside their scenes"
               if not problems else f"{len(problems)} subtitle problem(s)", problems)


# ------------------------------------------------------------------ audio
def audio_levels(path: Path) -> Optional[tuple[float, float]]:
    """(mean_volume, max_volume) in dB from FFmpeg's volumedetect, or None when it cannot be read."""
    try:
        proc = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                              capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    mean = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)", proc.stderr)
    peak = re.search(r"max_volume:\s*(-?[\d.]+|-inf)", proc.stderr)
    if not mean or not peak:
        return None
    f = lambda s: float("-inf") if s == "-inf" else float(s)
    return f(mean.group(1)), f(peak.group(1))


def check_audio(video: Optional[Path], silent_engine: bool, report: QualityReport) -> None:
    if video is None or not Path(video).exists():
        report.add("audio", True, "skipped: no video file was written (dry run)")
        return
    lv = audio_levels(Path(video))
    if lv is None:
        report.add("audio", False, "the audio track could not be read", ["audio track unreadable"])
        return
    mean, peak = lv
    report.stats["audio_db"] = {"mean": mean, "max": peak}
    if silent_engine:
        report.add("audio", True, f"silent engine: the track is silent on purpose (max {peak} dB); not checked for speech")
    else:
        report.add("audio", peak > AUDIBLE_DB, f"mean {mean} dB, max {peak} dB (audible above {AUDIBLE_DB:.0f} dB)",
                   [] if peak > AUDIBLE_DB else ["the audio track is silent"])


# ------------------------------------------------------------------ duration, sync
def check_duration(total_s: float, target_s: float, report: QualityReport, tolerance: float = 0.05) -> None:
    dev = abs(total_s - target_s) / target_s
    ok = 60 <= total_s <= 120 and dev <= tolerance + 1e-9
    report.add("duration", ok, f"{total_s:.2f} s for a {target_s:.0f} s target ({dev:.1%} off, limit {tolerance:.0%}); 60-120 s: "
               f"{'yes' if 60 <= total_s <= 120 else 'NO'}", [] if ok else [f"duration {total_s:.1f}s misses the target"])


def check_sync(scenes: Sequence[TopicScene], report: QualityReport) -> None:
    errs, bad = [], []
    for ts in scenes:
        for s in ts.sync_log:
            if s["mention_s"] is None:
                continue
            e = abs(s["appear_s"] - s["mention_s"])
            errs.append(e)
            if e > SYNC_TOL_S:
                bad.append(f"scene {ts.scene_id}: {s['object']} appears {e:.2f}s from the word '{s['word']}'")
    report.stats["sync_max_s"] = round(max(errs, default=0.0), 3)
    report.add("sync", not bad, f"{len(errs)} mentioned objects, largest gap between word and appearance "
               f"{max(errs, default=0.0):.2f} s (limit {SYNC_TOL_S} s)", bad)


def run_quality(scenes: Mapping[int, TopicScene], timeline, st: Style, *, t_target: float, video: Optional[Path] = None,
                measured_s: Optional[float] = None, silent_engine: bool = False) -> QualityReport:
    rep = QualityReport()
    ordered = [scenes[e.scene_id] for e in timeline.entries]
    check_empty_scenes(scenes, timeline.entries, st, rep)       # also fills each scene's sync log (build_layers)
    check_repeats(ordered, rep)
    check_sync(ordered, rep)
    check_subtitles(timeline.entries, rep)
    check_audio(video, silent_engine, rep)
    check_duration(measured_s if measured_s is not None else timeline.total_s, t_target, rep)
    return rep
