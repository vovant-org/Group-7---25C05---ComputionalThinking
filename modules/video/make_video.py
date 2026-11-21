"""Make an INFOGRAPHIC or ANIMATION video end to end.

    python -m modules.video.make_video "Make a 90-second infographic video about sleep" --pack sleep
    python -m modules.video.make_video "Make a 90-second animated video about sleep" --pack sleep
    python -m modules.video.make_video "Make a 90-second infographic video" --reference notes.txt --voice-id en-aria

Flow (report Level-1 flow, REQUEST ... RESPOND):
  1. run_pipeline: Router -> claims -> scenes -> Budget Optimizer -> Voice Segmenter -> Timeline, with a
     `VoiceRecorder` as the TTS, so the timeline is built from REAL audio durations.
  2. If the timeline misses S12/S13 the duration loop runs (report M13 and the calibration-loop pattern):
       N0 calibrate: measure the real speaking rate of the first pass and re-plan the script length;
       then at most 2 adjustments: N4 pauses + N3 speed (within +-10 %) chosen together as the cheapest pair
       that satisfies every constraint, N1 re-plan for a higher rate when the script is too short, N2 drop
       claims that cannot fit. (N2 removes a scene instead of rewriting its narration.)
  3. INFOGRAPHIC: the Infographic Composer draws every scene; labels are checked against the claims (S15).
     ANIMATION: the Motion Planner chooses pose and prop of every scene and `animation.py` builds its
     cut-out layers (render mode LAYERED); the checks are the subtitle band and real movement (S11).
  4. FFmpeg render: visual track + voice-over track + subtitles.
  5. The finished MP4 is measured again (S12, S13) and a JSON report is written next to it.

INFOGRAPHIC and ANIMATION are built. HYBRID stops with a clear message. The AI image-to-video mode
CLIP is not available (no provider is connected), so the Budget Optimizer plans ANIMATION with LAYERED only.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Optional, Sequence

from core.config import OUTPUT_DIR, PROFILES, VOICE_WPM
from core.models import MOTION_MODES, OutputFormat, RenderMode
from modules.pipeline.pipeline import PipelineResult, PipelineStatus, run_pipeline
from modules.router.router import Request
from modules.video.animation import AnimatedScene, check_animation, compose_animation_scene
from modules.video.composer import ComposedScene, Style, check_labels, compose_scene
from modules.video.render import DEFAULT_QUALITY, QUALITY_PROFILES, RenderError, probe_duration, render_video
from modules.video.voice import (SilentEngine, SpeechEngine, VoiceError, VoiceRecorder, make_engine)
from modules.voice_library.library import VoiceProfile

TOLERANCE = 0.05          # S13
MAX_TEMPO = 1.10          # N3: never speed the voice up by more than 10 %
MIN_TEMPO = 0.90          # N3: ... nor slow it down by more than 10 %
MAX_PAD_S = 0.8           # N4: never add more than this pause per scene
MAX_ADJUSTMENTS = 2
UNAVAILABLE_MODES = frozenset({RenderMode.CLIP})   # no image-to-video provider is connected (report 5.9.10, L1)
CALIBRATE_IF = 0.08       # re-plan when the measured speaking rate is more than 8 % off the planned one


@dataclass
class VideoResult:
    ok: bool
    video_path: Optional[Path]
    pipeline: PipelineResult
    report: dict = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    error: str = ""


def _fail(res: PipelineResult, log: list[str], error: str) -> VideoResult:
    return VideoResult(False, None, res, {"error": error, "adjustments": log}, log, error)


def _stop_message(res: PipelineResult) -> str:
    detail = " ".join(res.messages) if res.messages else res.status.value
    where = res.stopped_at.value if res.stopped_at else "pipeline"
    return f"stopped at {where}: {detail}"


def _suggestion(res: PipelineResult) -> str:
    """A concrete way out when the timeline could not reach the target."""
    tl = res.timeline
    if res.status != PipelineStatus.TIMELINE_CHECKS_FAILED or tl is None or not tl.entries:
        return ""
    if tl.total_s < tl.t_target * (1 - TOLERANCE):
        lo = PROFILES[res.decision.fmt].t_total_min
        fits = max(lo, int(round(tl.total_s / 5.0)) * 5)
        return (f" Suggestion: the claims give only about {tl.total_s:.0f} s of narration "
                f"({len(res.selection.claims)} claims). Add more reference text, or ask for {fits} s.")
    return f" Suggestion: the narration lasts {tl.total_s:.0f} s; ask for {min(120, int(round(tl.total_s / 5.0)) * 5)} s or shorten the text."


def _adjust(res: PipelineResult, state: dict, claims: list, log: list[str]) -> bool:
    """One adjustment step (N4 pauses, N3 speed, N2 drop a claim). Returns False when nothing is left.

    N4 and N3 are chosen TOGETHER as a small constraint search: the cheapest (speed, pause) pair for
    which every scene lasts at most t_max and the total is within 4 % of the target (the same formula as
    the Timeline Assembler: scene = max(audio / speed + pause, t_min)). "Cheapest" = smallest change of
    speed and pause. If no pair exists, N2 drops a claim."""
    tl = res.timeline
    prof = PROFILES[res.decision.fmt]
    target = tl.t_target
    raw = [e.audio_duration_s * state["tempo"] for e in tl.entries]          # audio at speed x1.0
    best = None
    for ti in range(int(round(MIN_TEMPO * 100)), int(round(MAX_TEMPO * 100)) + 1):
        tempo = ti / 100
        for pi in range(0, int(round(MAX_PAD_S * 100)) + 1, 5):
            pad = pi / 100
            dur = [max(r / tempo + pad, prof.t_min) for r in raw]
            total = sum(dur)
            if max(dur) > prof.t_max + 1e-9 or not prof.t_total_min <= total <= prof.t_total_max:
                continue
            if abs(total - target) / target > 0.04:
                continue
            cost = abs(tempo - 1.0) / 0.10 + pad / MAX_PAD_S
            if best is None or cost < best[0] - 1e-9:
                best = (cost, tempo, pad, total)
    if best is not None:
        _, tempo, pad, total = best
        if abs(tempo - state["tempo"]) > 1e-9 or abs(pad - state["pad"]) > 1e-9:
            parts = []
            if abs(tempo - state["tempo"]) > 1e-9:
                parts.append(f"N3 speed x{state['tempo']:.2f} -> x{tempo:.2f}")
            if abs(pad - state["pad"]) > 1e-9:
                parts.append(f"N4 pause {state['pad']:.2f} -> {pad:.2f} s per scene")
            log.append(f"{' + '.join(parts)} (now {tl.total_s:.1f} s, expected {total:.1f} s for a {target:.0f} s target)")
            state["tempo"], state["pad"] = tempo, pad
            return True
    # no (speed, pause) pair works: shorten by dropping a claim (N2), or give up when it is too short
    sel = list(res.selection.claims)
    if len(sel) <= 6:
        log.append("N2: only 6 claims left; cannot drop more")
        return False
    too_long_even_fast = [i for i, r in enumerate(raw) if r / MAX_TEMPO > prof.t_max + 1e-9]
    if too_long_even_fast:                      # scenes that no speed can fit: exclude their claims for good
        ids = {next(sc for sc in res.scenes if sc.scene_id == tl.entries[i].scene_id).claim_ids[0]
               for i in too_long_even_fast}
        left = [c for c in claims if c.claim_id not in ids]
        if len(left) < 6:
            log.append("N2: dropping the claims that are too long for this voice would leave fewer than 6 claims")
            return False
        log.append(f"N2: {len(ids)} scene(s) too long even at x{MAX_TEMPO:.2f} -> dropped claim(s) " + ", ".join(sorted(ids)))
        claims[:] = left                        # the other claims stay, so the planner can fill the time
        return True
    if tl.total_s < target * 0.96 and state.get("replans", 0) < 2:         # too short and no (speed, pause) pair fixes it
        new_wpm = res.planning_wpm * target / tl.total_s * 1.02
        log.append(f"N1: the script is too short ({tl.total_s:.1f} s for a {target:.0f} s target) "
                   f"-> re-planned for {new_wpm:.0f} wpm to add content")
        state["plan_wpm"], state["replans"] = new_wpm, state.get("replans", 0) + 1
        return True
    if sum(max(r / MAX_TEMPO, prof.t_min) for r in raw) > target * 1.04:        # whole video too long
        victim = min(sel, key=lambda c: c.importance)
        why = f"total {tl.total_s:.1f} s is too long even at x{MAX_TEMPO:.2f}"
    else:                                                    # too short even with maximal slow-down and pauses
        log.append("N4/N3: pauses and speed are at their limits; the video stays too short")
        return False
    log.append(f"N2: {why} -> dropped claim {victim.claim_id} (importance {victim.importance})")
    claims[:] = [c for c in sel if c.claim_id != victim.claim_id]
    return True


def make_video(request_text: str, claims: Sequence, out_path: Path, *, engine: SpeechEngine,
               voice: Optional[VoiceProfile] = None, speed: float = 1.0, reference_text: str = "",
               t_target: Optional[int] = None, budget: Optional[int] = None,
               output_format: Optional[OutputFormat] = None, fps: int = 24, burn_subtitles: bool = True,
               soft_subtitles: bool = True, render: bool = True, work_dir: Optional[Path] = None,
               style: Style = Style(), progress: Optional[Callable[[float, str], None]] = None,
               max_adjustments: int = MAX_ADJUSTMENTS, visual_engine: bool = True,
               quality: str = DEFAULT_QUALITY) -> VideoResult:
    out_path = Path(out_path)
    if work_dir is None:                                  # dry run: scratch space only, nothing left behind
        work_dir = out_path.parent / (out_path.stem + "_work") if render else Path(tempfile.mkdtemp(prefix="sfs_"))
    work_dir = Path(work_dir)
    recorder = VoiceRecorder(engine, work_dir / "audio")
    log: list[str] = []
    pool = list(claims)
    state = {"pad": 0.0, "tempo": 1.0}
    request = Request(topic=request_text, reference_text=reference_text, output_format=output_format,
                      t_target=t_target, budget=budget)

    calibrated, adjustments = False, 0
    if voice is None:                                   # needed to re-plan with a measured rate
        from modules.voice_library.language import detect_language
        from modules.voice_library.library import builtin_library
        voice = builtin_library().default(detect_language(" ".join(c.text for c in pool)) or "en")
    for _ in range(max_adjustments + 2):
        recorder.tempo = state["tempo"]
        try:
            res = run_pipeline(request, pool, tts=recorder, pad_s=state["pad"], voice=voice, voice_speed=speed,
                               unavailable_modes=UNAVAILABLE_MODES)
        except (VoiceError, RuntimeError) as exc:                   # engine failure, FFmpeg missing, offline ...
            return _fail(PipelineResult(request=request), log, f"voice engine failed: {exc}")
        if res.ok or res.status != PipelineStatus.TIMELINE_CHECKS_FAILED:
            break
        if not calibrated and max_adjustments > 0:                  # calibration loop: estimate vs measured
            calibrated = True
            seconds = sum(e.audio_duration_s for e in res.timeline.entries) * recorder.tempo
            measured = sum(len(e.narration.split()) for e in res.timeline.entries) * 60.0 / seconds
            if abs(measured / res.planning_wpm - 1.0) > CALIBRATE_IF:
                log.append(f"N0: measured speaking rate {measured:.0f} wpm vs planned {res.planning_wpm:.0f} wpm "
                           f"-> script length re-planned")
                voice = replace(voice, measured_wpm=measured / speed)
                continue
        if adjustments >= max_adjustments or not _adjust(res, state, pool, log):
            break
        adjustments += 1
        if state.get("plan_wpm"):                                   # N1: plan for the corrected rate
            voice = replace(voice, measured_wpm=state["plan_wpm"] / speed)
    if not res.ok:
        return _fail(res, log, _stop_message(res) + _suggestion(res) + (" | " + "; ".join(log) if log else ""))

    fmt = res.decision.fmt
    total_scenes = len(res.scenes)
    if fmt == OutputFormat.INFOGRAPHIC:
        composed: dict = {s.scene_id: compose_scene(s, s.narration, style, i, total_scenes)
                          for i, s in enumerate(res.scenes)}
        problems = [p for cs in composed.values() for p in check_labels(cs)]
    elif fmt == OutputFormat.ANIMATION:
        if visual_engine:                           # Topic-aware Visual Engine: objects and motion follow the content
            from modules.visual_engine import analyse_topic, compose_topic_scenes
            profile = analyse_topic(request_text, [c.text for c in res.selection.claims])
            composed = compose_topic_scenes(res.scenes, profile, style)
        else:                                       # generic stick figure + six props
            composed = {s.scene_id: compose_animation_scene(s, s.narration, style, i, total_scenes)
                        for i, s in enumerate(res.scenes)}
        problems = [p for cs in composed.values() for p in check_animation(cs, style)]
    else:
        return _fail(res, log, f"only INFOGRAPHIC and ANIMATION are built; the request resolved to {fmt.value}")

    render_info: dict = {}
    measured_s: Optional[float] = None
    if render:
        try:
            render_info = render_video(res.timeline, composed, recorder, out_path, style, fps, burn_subtitles,
                                       soft_subtitles, progress, quality)
            measured_s = probe_duration(out_path)
        except (RenderError, VoiceError, RuntimeError) as exc:
            return _fail(res, log, f"render failed: {exc}")

    report = build_report(res, composed, problems, engine, state, log, style, fps, measured_s, render_info,
                          out_path if render else None)
    if fmt == OutputFormat.ANIMATION and visual_engine:
        from modules.visual_engine.quality import run_quality
        q = run_quality(composed, res.timeline, style, t_target=res.timeline.t_target, video=out_path if render else None,
                        measured_s=measured_s, silent_engine=isinstance(engine, SilentEngine))
        report["visual_engine"] = {
            "domain": profile.domain, "audience": profile.audience, "concepts": list(profile.concepts[:8]),
            "relations": sorted({r.verb for r in profile.relations}), "trend": profile.trend,
            "scenes": [{"scene": e.scene_id, "objects": list(composed[e.scene_id].objects),
                        "sync": composed[e.scene_id].sync_log} for e in res.timeline.entries],
            "quality": q.as_dict()}
        if not q.ok:
            report["notes"] = report.get("notes", []) + ["Visual quality: " + "; ".join(q.problems[:4])]
    if render:
        report["quality"] = render_info.get("quality", quality)
        report["resolution"] = render_info.get("size", report["resolution"])    # the size of the file, not of the drawing
        out_path.with_suffix(".report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                                        encoding="utf-8")
    return VideoResult(True, out_path if render else None, res, report, log)


def build_report(res: PipelineResult, composed: dict, problems: list[str],
                 engine: SpeechEngine, state: dict, log: list[str], style: Style, fps: int,
                 measured_s: Optional[float], render_info: dict, path: Optional[Path]) -> dict:
    tl, target = res.timeline, res.timeline.t_target
    total = measured_s if measured_s is not None else tl.total_s
    dev = abs(total - target) / target
    fmt = res.decision.fmt
    animation = fmt == OutputFormat.ANIMATION
    modes = [e.render_mode.value for e in tl.entries]
    allowed = {m.value for m in PROFILES[fmt].allowed_modes}
    min_font = min((cs.min_font_used for cs in composed.values()), default=0)
    silent = isinstance(engine, SilentEngine)

    def chk(ok: bool, detail: str) -> dict:
        return {"pass": bool(ok), "detail": detail}

    if animation:                                   # every scene has motion (min_motion_ratio 1.0) and nothing is a still
        motion = sum(m in {x.value for x in MOTION_MODES} for m in modes) / max(1, len(modes))
        s11 = chk(set(modes) <= allowed and motion >= PROFILES[fmt].min_motion_ratio - 1e-9 and not problems,
                  f"motion ratio {motion:.0%}; modes " + ", ".join(sorted(set(modes))) + "; no AI clips (CLIP unavailable)")
        s15 = chk(not problems, "not applicable: no text is drawn inside animation scenes (subtitles come from the narration)"
                  if not problems else "; ".join(problems))
    else:
        s11 = chk(set(modes) <= allowed and "CLIP" not in modes, "no AI clips; modes " + ", ".join(sorted(set(modes))))
        s15 = chk(not problems and min_font >= style.min_font,
                  f"every label comes from its claim; smallest font {min_font}px (limit {style.min_font}px, assumed)"
                  if not problems else "; ".join(problems))
    criteria = {
        "S11": s11,
        "S12": chk(60 <= total <= 120, f"{total:.2f} s " + ("(measured on the MP4)" if measured_s else "(from the timeline)")),
        "S13": chk(dev <= TOLERANCE + 1e-9, f"{dev:.1%} off the {target:.0f} s target"),
        "S15": s15,
    }
    return {
        "video": str(path) if path else None, "request": res.request.topic, "format": fmt.value,
        "t_target": target, "total_s": round(total, 3), "deviation": round(dev, 4), "fps": fps,
        "resolution": list(style.size), "scenes": len(tl.entries), "frames": render_info.get("frames"),
        "subtitle_cues": render_info.get("cues"), "voice_engine": engine.name,
        "voice_is_silent": silent, "voice_speed_factor": round(state["tempo"], 4), "pause_per_scene_s": round(state["pad"], 3),
        "claims": [{"claim_id": c.claim_id, "text": c.text} for c in res.selection.claims],
        "adjustments": log, "criteria": criteria,
        "notes": (["The audio track is SILENT (SilentEngine): durations follow a words-per-minute rule."] if silent else [])
                 + (["CLIP (AI image-to-video) is not available: no provider is connected, so every scene is LAYERED "
                     "cut-out animation drawn by code."] if animation else [])
                 + [w for cs in composed.values() for w in cs.warnings],
        "timeline": [{"scene": e.scene_id, "start_s": round(e.start_s, 3), "duration_s": round(e.duration_s, 3),
                      "mode": e.render_mode.value, "layout": composed[e.scene_id].layout,
                      "labels": [l.text for l in composed[e.scene_id].labels], "narration": e.narration,
                      **({"pose": composed[e.scene_id].plan.pose, "prop": composed[e.scene_id].plan.prop,
                          "energy": composed[e.scene_id].plan.energy} if animation else {})}
                     for e in tl.entries],
    }


# ------------------------------------------------------------------ command line
def main(argv: Optional[Sequence[str]] = None) -> int:
    from modules.pipeline.sample_claims import get_sample_claims, pack_language, topic_keys
    from modules.video.claims import claims_from_text
    from modules.voice_library.library import load_library

    ap = argparse.ArgumentParser(description="Make an INFOGRAPHIC or ANIMATION video (MP4 with voice-over and subtitles).")
    ap.add_argument("request", help='e.g. "Make a 90-second infographic video about sleep"')
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--pack", choices=topic_keys(), help="hand-written claim pack of the demo")
    src.add_argument("--reference", type=Path, help="text file: claims are extracted from it")
    ap.add_argument("--out", type=Path, default=None, help="output .mp4 (default outputs/videos/<name>.mp4)")
    ap.add_argument("--voice-id", default=None, help="voice of the voice library (default: first voice of the language)")
    ap.add_argument("--speed", type=float, default=1.0, help="speaking speed 0.75-1.25")
    ap.add_argument("--voice-engine", choices=["auto", "silent", "system", "edge"], default="auto",
                    help="auto = system voice if pyttsx3 is installed, else silent (never online)")
    ap.add_argument("--allow-online", action="store_true", help="confirm that --voice-engine edge sends the text online")
    ap.add_argument("--no-burn", action="store_true", help="do not burn subtitles into the picture")
    ap.add_argument("--no-soft-subs", action="store_true", help="do not add the soft subtitle track")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--quality", choices=list(QUALITY_PROFILES), default=DEFAULT_QUALITY,
                    help="output quality: draft 480p / standard 720p (default) / high 1080p")
    ap.add_argument("--dry-run", action="store_true", help="plan, compose and check everything but write no video")
    ap.add_argument("--no-visual-engine", action="store_true", help="ANIMATION: use the generic stick-figure animation")
    a = ap.parse_args(argv)

    reference = a.reference.read_text(encoding="utf-8") if a.reference else ""
    if a.pack:
        claims, lang = get_sample_claims(a.pack), pack_language(a.pack)
    elif reference:
        claims = claims_from_text(reference)
        from modules.voice_library.language import detect_language
        lang = detect_language(reference) or "en"
    else:
        ap.error("give --pack or --reference")
    lib = load_library()
    voice = lib.get(a.voice_id) if a.voice_id else lib.default(lang)
    planning_wpm = voice.planning_wpm(a.speed)
    try:
        engine = make_engine(a.voice_engine, voice, a.speed, a.allow_online, planning_wpm)
    except Exception as exc:
        print(f"voice engine error: {exc}", file=sys.stderr)
        return 2
    name = (a.pack or (a.reference.stem if a.reference else "video"))
    out = a.out or OUTPUT_DIR / "videos" / f"{name}.mp4"
    print(f"voice: {voice.name} x{a.speed:g}  engine: {engine.name}", flush=True)

    last = {"pct": -1}

    def show(frac: float, msg: str) -> None:
        pct = int(frac * 100)
        if sys.stdout.isatty():
            print(f"\r  rendering {pct:3d}%  {msg:<18}", end="", flush=True)
        elif pct // 25 != last["pct"] // 25:                  # redirected output: one line per 25 %
            print(f"  rendering {pct}%", flush=True)
        last["pct"] = pct

    r = make_video(a.request, claims, out, engine=engine, voice=voice, speed=a.speed, reference_text=reference,
                   fps=a.fps, burn_subtitles=not a.no_burn, soft_subtitles=not a.no_soft_subs,
                   render=not a.dry_run, progress=show, visual_engine=not a.no_visual_engine, quality=a.quality)
    print()
    for line in r.log:
        print("  adjust:", line)
    if not r.ok:
        print(f"FAILED: {r.error}", file=sys.stderr)
        return 1
    for k, v in r.report["criteria"].items():
        print(f"  {k}: {'PASS' if v['pass'] else 'FAIL'}  {v['detail']}")
    print(f"scenes {r.report['scenes']}, {r.report['total_s']} s" + (f"  ->  {r.video_path}" if r.video_path else "  (dry run)"))
    for note in r.report["notes"][:3]:
        print("  note:", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
