"""Pure functions that turn backend results into the plain dicts the UI components draw.

Nothing here calls Streamlit or runs the pipeline, and nothing invents data: every value is read from a
`PipelineResult`, a video `report` (the JSON that `modules/video/make_video.py` writes next to the MP4),
the `.srt` file of the video, or the small project record written by `ui/storage.py`.

Where the backend does not store something (for example a title for a scene, or which claim belongs to
a scene of a project that was made before this UI existed) the adapters say so instead of guessing.
"""
from __future__ import annotations

import re
import time
from typing import Any, Optional, Sequence

from modules.pipeline.ui_helpers import CUTOUT_LABELS

MAX_WORDS = 1500          # same limit as the Router (modules/router/router.py: MAX_INPUT_WORDS)

# ------------------------------------------------------------------------------------ progress stages
# The seven user-facing stages and the backend step each one is read from. A stage is shown as done only
# when the backend log of that step says so (see `stage_view`).
STAGES = [
    ("understanding", "Understanding Request", "Reads your request and applies the format, length and input limits (Router)."),
    ("planning", "Planning Story", "Picks the most important claims that fit the target length (claim selection)."),
    ("scenes", "Organizing Scenes", "Turns the selected claims into scenes, each with a layout (Scene Segmenter)."),
    ("budget", "Optimizing Budget", "Chooses how each scene is rendered so the total stays within budget (Budget Optimizer)."),
    ("narration", "Generating Narration", "Splits the script into voice units and measures the real narration length (Voice Segmenter + voice engine)."),
    ("timeline", "Assembling Timeline", "Places scenes, voice and subtitles on one timeline and renders the MP4 (Timeline Assembler + FFmpeg)."),
    ("verify", "Verifying Output", "Measures the finished video against the length and format checks."),
]

# backend stage name (core of modules/pipeline/pipeline.py: Stage) -> UI stage keys it confirms
_LOG_OF = {"router": "understanding", "scene_segmenter": "scenes", "budget_optimizer": "budget",
           "voice_segmenter": "narration", "timeline_assembler": "timeline"}

BLOCKING_STATUSES = {"ROUTER_REJECTED", "ROUTER_CLARIFY", "VOICE_LANGUAGE_MISMATCH", "SCENES_INVALID", "BUDGET_INFEASIBLE"}


def count_words(text: str) -> int:
    """Whitespace-separated words, the Router's own definition (a Vietnamese syllable counts as a word)."""
    return len(text.split())


# --------------------------------------------------------------------------------------- pipeline facts
def facts_from_pipeline(pr: Any, claims_available: Optional[int] = None) -> dict:
    """Plain, JSON-safe summary of a `PipelineResult` (read-only). Used by the stage tracker, the cost
    card and the project record."""
    d, o, tl, vs = pr.decision, pr.optimize, pr.timeline, pr.voice
    sel = pr.selection
    stages = [{"stage": s.stage.value, "ok": bool(s.ok), "summary": s.summary} for s in pr.stages]
    return {
        "stages": stages,
        "messages": list(pr.messages),
        "status": pr.status.value,
        "stopped_at": pr.stopped_at.value if pr.stopped_at else None,
        "format": d.fmt.value if d is not None and d.fmt else None,
        "t_target": d.t_target if d is not None else None,
        "word_count": d.word_count if d is not None else None,
        "router_codes": sorted(d.codes) if d is not None else [],
        "claims_selected": len(sel.claims) if sel is not None else None,
        "claims_available": claims_available,
        "selection_algorithm": sel.algorithm if sel is not None else "",
        "n_scenes": len(pr.scenes) if pr.scenes else None,
        "est_total_s": pr.scene_report.get("total_s") if pr.scene_report else None,
        "budget": pr.budget,
        "budget_source": pr.budget_source,
        "cost": o.total_cost if o is not None and o.feasible else None,
        "motion_ratio": o.motion_ratio if o is not None and o.feasible else None,
        "optimizer": o.algorithm if o is not None else "",
        "optimizer_reason": (o.reason if o is not None and not o.feasible else ""),
        "voice_units": len(vs.units) if vs is not None else None,
        "voice_in_band": pr.voice_in_band_share,
        "planning_wpm": pr.planning_wpm,
        "timeline_built": tl is not None,
        "timeline_total_s": tl.total_s if tl is not None else None,
        "deviation": tl.deviation if tl is not None else None,
        "timeline_codes": sorted(tl.codes) if tl is not None else [],
    }


def _log(facts: dict, backend_stage: str) -> Optional[dict]:
    return next((s for s in facts.get("stages", []) if s["stage"] == backend_stage), None)


def estimate_from_facts(facts: Optional[dict], budget_set_by_user: bool = False) -> dict:
    """Cost-estimation card data, from a planning pass of the real pipeline (Budget Optimizer included)."""
    if not facts:
        return {"status_key": "pending", "status_text": "Waiting for input", "can_start": False, "blocking": False,
                "messages": ["Add a topic and your reference material to see the estimated cost."]}
    status = facts["status"]
    est = {"cost": facts.get("cost"), "budget": facts.get("budget"), "budget_source": facts.get("budget_source") or None,
           "motion": facts.get("motion_ratio"), "n_scenes": facts.get("n_scenes"), "n_claims": facts.get("claims_selected"),
           "est_total_s": facts.get("est_total_s"), "messages": [], "blocking": status in BLOCKING_STATUSES}
    if status == "OK" or status == "TIMELINE_CHECKS_FAILED":
        est.update(status_key="within", status_text="Within budget", can_start=True)
        if status == "TIMELINE_CHECKS_FAILED":
            est["messages"].append("With the simulated narration timing the length check misses its target. "
                                   "The real narration is measured during generation and the length is adjusted then.")
    elif status == "BUDGET_INFEASIBLE" or "BUDGET_BELOW_MIN" in facts.get("router_codes", []):
        est.update(status_key="infeasible", status_text="Budget too low", can_start=False)
        est["messages"] += facts.get("messages", [])
    elif status in ("ROUTER_REJECTED", "ROUTER_CLARIFY", "VOICE_LANGUAGE_MISMATCH", "SCENES_INVALID"):
        est.update(status_key="blocked", status_text="Needs attention", can_start=False)
        est["messages"] += facts.get("messages", [])
    else:
        est.update(status_key="blocked", status_text=status.replace("_", " ").title(), can_start=False)
        est["messages"] += facts.get("messages", [])
    est.setdefault("can_start", False)
    return est


# ------------------------------------------------------------------------------------- stage tracker
def stage_view(facts: Optional[dict], *, video_ok: Optional[bool] = None, criteria: Optional[dict] = None,
               engine_name: str = "", silent: Optional[bool] = None, error: str = "") -> list[dict]:
    """The seven UI stages with a state each: done | warning | failed | pending.

    A stage is `done` only if the backend confirms it:
      * understanding / scenes / budget / narration / timeline: the backend stage log says ok
      * planning: claims were selected AND the scene stage ran
      * narration: also needs the timeline (the voice engine measured the real durations)
      * timeline: also needs the MP4 to be rendered (`video_ok`)
      * verify: the MP4 exists and its checks (S11, S12, S13, S15) were evaluated
    Nothing is `running`: the backend runs as one blocking job and gives no per-stage signal.
    """
    out = [{"key": k, "title": t, "desc": d, "state": "pending", "detail": ""} for k, t, d in STAGES]
    by_key = {s["key"]: s for s in out}
    if not facts:
        if error:
            by_key["understanding"].update(state="failed", detail=error)
        return out
    msgs = facts.get("messages", [])

    def fail(key: str, text: str) -> None:
        by_key[key].update(state="failed", detail=text)

    # 1 Understanding
    lg = _log(facts, "router")
    if lg is not None:
        if lg["ok"]:
            by_key["understanding"].update(state="done", detail=f'{(facts.get("format") or "").title()} video, {facts.get("t_target")} s target, '
                                                               f'{facts.get("word_count")} input words')
        else:
            fail("understanding", " ".join(msgs[:2]) or "The request was not accepted.")
    # 2 Planning (claim selection runs inside the scene stage of the backend)
    sc = _log(facts, "scene_segmenter")
    if facts.get("claims_selected") is not None and sc is not None:
        avail = facts.get("claims_available")
        of = f" of {avail}" if avail else ""
        by_key["planning"].update(state="done" if facts["claims_selected"] > 0 else "failed",
                                  detail=f'{facts["claims_selected"]}{of} claims selected ({facts.get("selection_algorithm")})')
    # 3 Scenes
    if sc is not None:
        if sc["ok"]:
            by_key["scenes"].update(state="done", detail=f'{facts.get("n_scenes")} scenes, about {facts.get("est_total_s")} s before narration is measured')
        else:
            fail("scenes", " ".join(msgs[-1:]) or sc["summary"])
    # 4 Budget
    bd = _log(facts, "budget_optimizer")
    if bd is not None:
        if bd["ok"]:
            by_key["budget"].update(state="done", detail=f'{facts.get("cost")} of {facts.get("budget")} credits · '
                                                         f'{(facts.get("motion_ratio") or 0):.0%} of scenes move')
        else:
            fail("budget", " ".join(m for m in msgs if m) or bd["summary"])
    # 5 Narration
    vg = _log(facts, "voice_segmenter")
    if vg is not None:
        if vg["ok"] and facts.get("timeline_built"):
            note = "silent engine: no sound is produced" if silent else (f"engine {engine_name}" if engine_name else "")
            by_key["narration"].update(state="done", detail=", ".join(x for x in (f'{facts.get("voice_units")} voice units', note) if x))
        elif not vg["ok"]:
            fail("narration", " ".join(msgs[:1]) or vg["summary"])
    elif facts.get("status") == "VOICE_LANGUAGE_MISMATCH":      # the language check stops the run before the Voice Segmenter
        fail("narration", " ".join(msgs[:1]))
    # 6 Timeline (+ render)
    tg = _log(facts, "timeline_assembler")
    if tg is not None:
        if not tg["ok"]:
            fail("timeline", f'Timeline checks failed: {", ".join(facts.get("timeline_codes", [])) or tg["summary"]}')
        elif video_ok is True:
            dev = facts.get("deviation")
            by_key["timeline"].update(state="done", detail=f'{(facts.get("timeline_total_s") or 0):.1f} s timeline'
                                                           + (f", {dev:.1%} from target" if dev is not None else "") + ", MP4 rendered")
        elif video_ok is False:
            fail("timeline", error or "The timeline was built but the video could not be rendered.")
    # 7 Verify
    if video_ok is True and criteria:
        passed = sum(1 for v in criteria.values() if v.get("pass"))
        total = len(criteria)
        by_key["verify"].update(state="done" if passed == total else "warning", detail=f"{passed} of {total} checks passed")
    return out


# ----------------------------------------------------------------------------------- input validation
def validate_inputs(*, topic: str, instructions: str, reference: str, source: str, claims_text: Sequence[str],
                    voice_language: str, ffmpeg_ok: bool, upload_error: str = "", online_ok: bool = True,
                    engine_kind: str = "silent", detected_language=None, ai_reads: bool = False,
                    ai_online_needed: bool = False, ai_online_ok: bool = True) -> list[dict]:
    """Messages shown under the composer: [{level: err|warn|info, title, text}]. Any `err` blocks Create Video."""
    msgs: list[dict] = []

    def add(level: str, title: str, text: str = "") -> None:
        msgs.append({"level": level, "title": title, "text": text})

    if not ffmpeg_ok:
        add("err", "FFmpeg was not found", "Install it, or run  pip install -r requirements-video.txt  (imageio-ffmpeg bundles a copy).")
    if upload_error:
        add("err", "The uploaded file could not be read", upload_error)
    if not topic.strip():
        add("err", "Add a topic or idea", "Describe what the video should explain, for example “Why does inflation happen?”.")
    words = count_words(topic) + count_words(instructions) + count_words(reference)
    if words > MAX_WORDS:
        add("err", f"Too long: {words:,} words (limit {MAX_WORDS:,})", "Shorten the topic or the reference material. Nothing is cut silently.")
    if source == "text":
        if not reference.strip() and ai_reads:
            add("info", "The AI will write the claims from your topic",
                "Without reference text the claims are written by the AI and are NOT verified. Paste your own material for a video "
                "whose every sentence comes from your text.")
        elif not reference.strip():
            add("err", "Add reference material", "StoryFrame builds the story from text you provide. It cannot research a topic by itself yet "
                                                   "(the REASON step is not built). Paste text or upload a .txt / .md file, or pick a demo template.")
        elif not claims_text:
            add("err", "No usable sentences found", "Sentences of 8–24 words become the claims. Use full sentences, not a list of keywords.")
    if claims_text and detected_language and detected_language != voice_language:
        add("err", "The voice does not match the narration language",
            f"The content looks like “{detected_language}” but the selected voice speaks “{voice_language}”. Switch the narration language or the voice.")
    if engine_kind == "edge" and not online_ok:
        add("err", "Confirm the online voice", "The Edge voice sends the narration text to an online service. Tick the confirmation or choose another engine.")
    if ai_online_needed and not ai_online_ok:
        add("err", "Confirm the online AI", "The selected AI option sends your text to an online service. Tick the confirmation or switch it off.")
    if engine_kind == "silent":
        add("info", "Silent video", "The video will have a timed but silent audio track. Choose a system or Edge voice to hear narration.")
    return msgs


def has_blocking(msgs: Sequence[dict]) -> bool:
    return any(m["level"] == "err" for m in msgs)


# ------------------------------------------------------------------------------------------- labels
PATTERN_LABELS = {"cause_effect": "Cause → effect", "comparison": "Comparison", "step_by_step": "Step by step",
                  "trend": "Trend over time", "analogy": "Analogy"}
LAYOUT_NAMES = {"cause_chain": "Cause chain", "compare_2col": "Two-column comparison", "steps": "Steps", "trend_chart": "Trend chart",
                "big_number": "Big number", "loop": "Loop"}
POSE_LABELS = {"wave": "waving", "think": "thinking", "point": "pointing", "walk": "walking", "sleep": "sleeping"}


def layout_name(layout: Optional[str]) -> str:
    if not layout:
        return "Character scene"
    if layout.startswith("cutout:"):
        prop = layout.split(":", 1)[1]
        return f"Cut-out · {CUTOUT_LABELS.get(prop, prop)}"
    return LAYOUT_NAMES.get(layout, layout.replace("_", " ").title())


def pattern_name(pattern: Optional[str]) -> str:
    return PATTERN_LABELS.get(pattern or "", (pattern or "").replace("_", " ").title())


# ---------------------------------------------------------------------------------------- SRT cues
_SRT_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{3})\s*-->\s*(\d+):(\d\d):(\d\d)[,.](\d{3})")


def parse_srt(text: str) -> list[dict]:
    """Cues of an .srt file: [{text, start_s, end_s}]. Malformed blocks are skipped."""
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip()):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        for i, ln in enumerate(lines):
            m = _SRT_TIME.search(ln)
            if m:
                g = [int(x) for x in m.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
                body = " ".join(lines[i + 1:]).strip()
                if body and end > start:
                    cues.append({"text": body, "start_s": start, "end_s": end})
                break
    return cues


# ------------------------------------------------------------------------------ storyboard and tracks
def storyboard_scenes(report: dict, record: Optional[dict] = None) -> list[dict]:
    """One dict per scene for the storyboard, properties panel and timeline.

    `report` is the JSON written by make_video (always present). `record` is the UI's project record (only for
    videos made with this UI): it adds the claim linked to each scene. Without it the claim ids of a scene are
    unknown and `evidence_missing` is set, rather than guessing.
    """
    timeline = report.get("timeline", [])
    first = min((t["scene"] for t in timeline), default=0)
    rec_scenes = {s["scene"]: s for s in (record or {}).get("scenes", [])}
    claim_text = {c["claim_id"]: c.get("text", "") for c in (record or {}).get("claims", [])}
    claim_text.update({c["claim_id"]: c.get("text", "") for c in report.get("claims", [])})
    objects = {s["scene"]: s.get("objects", []) for s in report.get("visual_engine", {}).get("scenes", [])}
    animation = report.get("format") == "ANIMATION"
    out = []
    for t in timeline:
        rs = rec_scenes.get(t["scene"])
        labels = list(t.get("labels", []))
        if animation:
            pose = POSE_LABELS.get(t.get("pose", ""), t.get("pose", ""))
            prop = CUTOUT_LABELS.get(t.get("prop", ""), t.get("prop", ""))
            visual = f"Stick-figure character {('(' + pose + ') ') if pose else ''}with a “{prop}” prop" if prop else "Stick-figure character"
            if objects.get(t["scene"]):
                visual += "; objects: " + ", ".join(objects[t["scene"]])
        else:
            visual = ("On-screen text: " + " | ".join(labels)) if labels else f"{layout_name(t.get('layout'))} drawn by code from the claim"
        claims = [{"claim_id": cid, "text": claim_text.get(cid, "")} for cid in (rs or {}).get("claim_ids", [])]
        out.append({
            "scene": t["scene"], "number": t["scene"] - first + 1,
            "title": pattern_name((rs or {}).get("explain_pattern")) or layout_name(t.get("layout")),
            "narration": t.get("narration", ""), "visual": visual, "layout": layout_name(t.get("layout")), "mode": t.get("mode", "STATIC"),
            "start_s": float(t["start_s"]), "duration_s": float(t["duration_s"]), "labels": labels, "claims": claims,
            "evidence_missing": rs is None, "facet": (rs or {}).get("facet", ""), "cost": (rs or {}).get("cost"),
        })
    return out


def timeline_data(scenes: Sequence[dict], cues: Sequence[dict], record: Optional[dict] = None) -> dict:
    """Video, audio and subtitle tracks from the real timeline.

    video: every scene's start/length from the Timeline Assembler (via the report).
    audio: the narration length of each scene, from the record when the UI saved it; otherwise from the span
           of that scene's subtitle cues (the cues are cut from the same measured audio, see subtitles.make_cues).
    subtitles: the cues of the .srt file the renderer wrote.
    """
    rec_scenes = {s["scene"]: s for s in (record or {}).get("scenes", [])}
    video = [{"scene": s["number"], "start_s": s["start_s"], "end_s": s["start_s"] + s["duration_s"], "mode": s["mode"]} for s in scenes]
    audio = []
    for s in scenes:
        end = s["start_s"] + s["duration_s"]
        a = rec_scenes.get(s["scene"], {}).get("audio_s")
        if a is not None:
            audio.append({"scene": s["number"], "start_s": s["start_s"], "end_s": min(end, s["start_s"] + float(a))})
            continue
        inside = [c for c in cues if s["start_s"] - 1e-3 <= c["start_s"] < end - 1e-3]
        if inside:
            audio.append({"scene": s["number"], "start_s": inside[0]["start_s"], "end_s": min(end, max(c["end_s"] for c in inside))})
    total = max([v["end_s"] for v in video] + [0.0])
    return {"video": video, "audio": audio, "subtitles": list(cues), "total_s": total}


# ---------------------------------------------------------------------------------------- misc text
def humanize_age(ts: float, now: Optional[float] = None) -> str:
    """'just now', '5 min ago', '3 h ago', '2 days ago', or a date for older files."""
    sec = max(0.0, (time.time() if now is None else now) - ts)
    if sec < 60:
        return "just now"
    if sec < 3600:
        return f"{int(sec // 60)} min ago"
    if sec < 86400:
        return f"{int(sec // 3600)} h ago"
    if sec < 7 * 86400:
        d = int(sec // 86400)
        return f"{d} day{'s' if d != 1 else ''} ago"
    return time.strftime("%d %b %Y", time.localtime(ts))


def short_title(text: str, limit: int = 70) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
