"""Pure logic behind the screens (no Streamlit import, so it is unit-tested).

It composes the request from the form, validates the form, estimates the cost with the REAL pipeline
(Router, Scene Segmenter, Budget Optimizer), maps the real stage logs to the seven user-facing
steps, lists finished videos on disk, and shapes the storyboard and the timeline tracks from the JSON
report written by `make_video`. Nothing here invents a result: when the backend did not confirm
something, it is reported as pending, failed or unavailable.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from core.models import OutputFormat
from modules.pipeline.pipeline import PipelineResult, PipelineStatus, Stage, run_pipeline
from modules.pipeline.sample_claims import get_sample_claims, pack_language
from modules.pipeline.ui_helpers import layout_label
from modules.router.router import Request
from modules.video.claims import claims_from_text
from modules.voice_library.language import detect_language
from modules.voice_library.library import LANGUAGES, VoiceProfile

MAX_INPUT_WORDS = 1500          # Router limit (INPUT_TOO_LONG)
MIN_CLAIMS = 6                  # fewer than 6 scenes cannot be built (S12 scene count)
DURATION_MIN, DURATION_MAX = 60, 120


# ------------------------------------------------------------------ formats and examples
@dataclass(frozen=True)
class FormatInfo:
    key: str                    # OutputFormat value
    title: str
    icon: str
    description: str
    available: bool
    note: str = ""


FORMATS = (
    FormatInfo("INFOGRAPHIC", "Infographic", "📊", "Data-driven visuals. Charts, icons, diagrams and text drawn by code.", True),
    FormatInfo("ANIMATION", "Animation", "🎞️", "Animated storytelling. A cut-out character with motion and scene transitions.",
               True, "AI video clips are not connected, so every scene is cut-out animation drawn by code."),
    FormatInfo("HYBRID", "Hybrid", "✨", "A combination of infographic and animation.", False,
               "The backend does not build this format yet."),
)
FORMAT_BY_KEY = {f.key: f for f in FORMATS}

# (icon, card title, text put in the idea box). None of them has a built-in claim pack: they need reference material.
EXAMPLE_PROMPTS = (
    ("🧠", "Explain Artificial Intelligence", "Explain Artificial Intelligence"),
    ("🌍", "Create a video about Climate Change", "Create a video about Climate Change"),
    ("🌐", "Explain How the Internet Works", "Explain How the Internet Works"),
    ("💻", "Introduce the History of Computer Science", "Introduce the History of Computer Science"),
)

ENGINES = {"silent": "Silent preview (no sound, offline)",
           "system": "System voice (offline, needs pyttsx3)",
           "edge": "Edge neural voice (ONLINE, needs edge-tts)"}


# ------------------------------------------------------------------ request and content
def compose_request(idea: str, fmt_key: str, duration_s: int, language: str, instructions: str = "") -> str:
    """The request text handed to the Router. Format and duration are also passed as explicit fields; the
    text repeats them so the report and the Router read the same thing."""
    idea = " ".join(idea.split())
    extra = " ".join(instructions.split())
    word = {"INFOGRAPHIC": "infographic", "ANIMATION": "animation" if language != "vi" else "hoạt hình",
            "HYBRID": "hybrid"}[fmt_key]
    if language == "vi":
        text = f"Tạo video {word} {int(duration_s)} giây. Chủ đề: {idea}"
    else:
        text = f"Make a {int(duration_s)}-second {word} video. Topic: {idea}"
    if extra:
        text += f". {extra}" if not text.endswith(".") else f" {extra}"
    return text


def resolve_claims(source: str, pack: Optional[str], reference: str) -> tuple[list, Optional[str]]:
    """(claims, language of the content). source: "pack" (hand-written demo claims) or "reference"
    (sentences of 8-24 words from the user's own text)."""
    if source == "pack" and pack:
        return get_sample_claims(pack), pack_language(pack)
    claims = claims_from_text(reference)
    return claims, detect_language(reference) if reference.strip() else None


@dataclass(frozen=True)
class Issue:
    kind: str                   # "error" blocks generation, "warning" does not
    message: str


def validate_config(*, idea: str, fmt_key: str, source: str, pack: Optional[str], reference: str,
                    voice: VoiceProfile, engine: str, allow_online: bool, ffmpeg_ok: bool, edge_ok: bool,
                    system_ok: bool) -> list[Issue]:
    """Everything that would make 'Create Video' fail, found before the run, in plain words."""
    issues: list[Issue] = []
    if not idea.strip():
        issues.append(Issue("error", "Describe the topic or idea of your video."))
    if FORMAT_BY_KEY[fmt_key].available is False:
        issues.append(Issue("error", f"{FORMAT_BY_KEY[fmt_key].title} videos are not built yet. Choose Infographic or Animation."))
    words = len(idea.split()) + len(reference.split())
    if words > MAX_INPUT_WORDS:
        issues.append(Issue("error", f"The text has {words:,} words; the limit is {MAX_INPUT_WORDS:,}. Shorten the reference material."))
    if source == "reference":
        if not reference.strip():
            issues.append(Issue("error", "Add reference material (paste text or upload a .txt/.md file), or switch to a demo claim pack. "
                                         "The research step that finds facts by itself is not built yet."))
        else:
            n = len(claims_from_text(reference))
            if n < MIN_CLAIMS:
                issues.append(Issue("error", f"Found {n} usable sentence(s) in your text; at least {MIN_CLAIMS} are needed "
                                             "(each sentence 8-24 words)."))
            lang = detect_language(reference)
            if lang and lang != voice.language:
                issues.append(Issue("error", f"The text is in {LANGUAGES[lang]} but the voice {voice.name} speaks "
                                             f"{LANGUAGES[voice.language]}. Pick a {LANGUAGES[lang]} voice."))
    elif not pack:
        issues.append(Issue("error", "Choose a demo claim pack."))
    elif pack_language(pack) != voice.language:
        issues.append(Issue("error", f"This claim pack is in {LANGUAGES[pack_language(pack)]}; choose a "
                                     f"{LANGUAGES[pack_language(pack)]} voice or another pack."))
    if not ffmpeg_ok:
        issues.append(Issue("error", "FFmpeg was not found. Run: pip install imageio-ffmpeg"))
    if engine == "edge":
        if not edge_ok:
            issues.append(Issue("error", "The Edge voice needs the edge-tts package: pip install edge-tts"))
        if not allow_online:
            issues.append(Issue("error", "Confirm that the narration text may be sent to an online service, or use another voice engine."))
    if engine == "system" and not system_ok:
        issues.append(Issue("error", "The system voice needs the pyttsx3 package: pip install pyttsx3"))
    if engine == "silent":
        issues.append(Issue("warning", "Silent preview: the video has no sound; timing follows a words-per-minute rule."))
    return issues


def blocking(issues: Sequence[Issue]) -> list[Issue]:
    return [i for i in issues if i.kind == "error"]


# ------------------------------------------------------------------ cost estimate (real Budget Optimizer)
@dataclass
class PlanEstimate:
    status: str                         # ok | over | unknown
    cost: Optional[int] = None
    budget: Optional[int] = None
    budget_source: str = ""
    message: str = ""
    scenes: int = 0
    est_total_s: Optional[float] = None
    details: list[str] = field(default_factory=list)


_SOURCE_WORDS = {"request": "your budget", "text": "from your request", "auto": "automatic: twice the cheapest plan"}


def estimate_plan(request_text: str, claims: Sequence, *, fmt_key: str, duration_s: int, budget: Optional[int],
                  voice: VoiceProfile, speed: float, reference: str = "") -> PlanEstimate:
    """Run the planning stages of the pipeline (no audio, no frames) to learn the cost before generating.

    This is the same Router + Scene Segmenter + Budget Optimizer that the real run uses, with the
    simulated TTS only to size the timeline; the credits per render mode are the team's assumptions."""
    if not claims:
        return PlanEstimate("unknown", message="No claims yet, so nothing can be planned.")
    try:
        from modules.video.make_video import UNAVAILABLE_MODES
    except Exception:                                       # PIL/numpy missing: still estimate
        UNAVAILABLE_MODES = frozenset()
    req = Request(topic=request_text, reference_text=reference, output_format=OutputFormat(fmt_key),
                  t_target=int(duration_s), budget=budget or None)
    try:
        res = run_pipeline(req, list(claims), voice=voice, voice_speed=speed, unavailable_modes=UNAVAILABLE_MODES)
    except ValueError as exc:
        return PlanEstimate("unknown", message=str(exc))
    return estimate_from_result(res)


def estimate_from_result(res: PipelineResult) -> PlanEstimate:
    o = res.optimize
    if res.status == PipelineStatus.BUDGET_INFEASIBLE and o is not None:
        return PlanEstimate("over", budget=res.budget, budget_source=_SOURCE_WORDS.get(res.budget_source, ""),
                            message=" ".join(m for m in (o.reason, o.suggestion) if m) or "The budget is too small for this plan.",
                            scenes=len(res.scenes))
    if o is None or not o.feasible:
        msg = " ".join(res.messages) or (res.stages[-1].summary if res.stages else "The request could not be planned.")
        return PlanEstimate("unknown", message=msg)
    est = res.timeline.total_s if res.timeline is not None else None
    details = []
    if res.status == PipelineStatus.TIMELINE_CHECKS_FAILED:
        details.append("The first timeline estimate misses the length target; the real run adjusts pauses, speed and claims.")
    return PlanEstimate("ok", cost=o.total_cost, budget=res.budget, budget_source=_SOURCE_WORDS.get(res.budget_source, ""),
                        message=f"{len(res.scenes)} scenes · motion {o.motion_ratio:.0%}. Credit costs are assumptions, not measured.",
                        scenes=len(res.scenes), est_total_s=est, details=details)


# ------------------------------------------------------------------ the seven generation steps
STEP_TITLES = ("Understanding Request", "Planning Story", "Organizing Scenes", "Optimizing Budget",
               "Generating Narration", "Assembling Timeline", "Verifying Output")
_WAITING = ("Reads the request and applies the limits.", "Chooses the claims that fit the time.",
            "Turns each claim into a scene.", "Picks a render mode per scene within the budget.",
            "Speaks the narration and measures it.", "Places the scenes on the timeline.",
            "Renders the video and checks it against the criteria.")


def _step(i: int, state: str, detail: str = "") -> dict:
    return {"title": STEP_TITLES[i], "state": state, "detail": detail or _WAITING[i]}


def stage_cards(res: Optional[PipelineResult], *, started: bool = False, render_frac: Optional[float] = None,
                report: Optional[dict] = None, error: str = "") -> list[dict]:
    """The seven steps with their REAL state. 'done' means the backend confirmed it: a stage log with ok=True,
    or (for the last step) a finished MP4 whose criteria were computed. Stages after a failure stay pending."""
    steps = [_step(i, "pending") for i in range(7)]
    if res is None or not res.stages:
        if started:
            steps[0] = _step(0, "run", "Starting…")
        if error:
            steps[0] = _step(0, "fail", error)
        return steps
    logs = {s.stage: s for s in res.stages}

    def mark(i: int, stage: Stage, detail_ok: str) -> None:
        log = logs.get(stage)
        if log is None:
            return
        steps[i] = _step(i, "done", detail_ok) if log.ok else _step(i, "fail", log.summary)

    d = res.decision
    mark(0, Stage.ROUTER, f"{d.fmt.value.title()} video · {d.t_target} s · {d.word_count} input words" if d and d.fmt else "")
    if res.selection is not None:
        steps[1] = _step(1, "done", f"{len(res.selection.claims)} claims selected ({res.selection.algorithm})")
    mark(2, Stage.SCENES, f"{len(res.scenes)} scenes, about {res.scene_report.get('total_s', 0):.0f} s before audio"
         if res.scene_report else "")
    if res.optimize is not None and Stage.BUDGET in logs:
        mark(3, Stage.BUDGET, f"Cost {res.optimize.total_cost} of {res.budget} credits · motion {res.optimize.motion_ratio:.0%}")
    voice_log = logs.get(Stage.VOICE)
    if voice_log is not None and not voice_log.ok:
        steps[4] = _step(4, "fail", voice_log.summary)
    elif res.timeline is not None:                          # durations exist only after the narration was produced
        steps[4] = _step(4, "done", f"Narration ready for {len(res.timeline.entries)} scenes" +
                         (f" · {res.voice_profile.name}" if res.voice_profile else ""))
    tl_log = logs.get(Stage.TIMELINE)
    if tl_log is not None:
        mark(5, Stage.TIMELINE, f"{res.timeline.total_s:.1f} s on the timeline" if res.timeline else "")
    # last step: needs a rendered video
    if report is not None:
        crit = report.get("criteria", {})
        bad = [k for k, v in crit.items() if not v.get("pass")]
        steps[6] = (_step(6, "fail", "Checks failed: " + ", ".join(bad)) if bad else
                    _step(6, "done", f"{len(crit)} checks passed on the finished MP4"))
    elif render_frac is not None and res.ok:
        steps[6] = _step(6, "run", f"Rendering the video… {render_frac:.0%}")
    if error and not any(s["state"] == "fail" for s in steps):
        k = next((i for i, s in enumerate(steps) if s["state"] in ("pending", "run")), 6)
        steps[k] = _step(k, "fail", error)
    return steps


# ------------------------------------------------------------------ SRT and tracks
_SRT_T = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def _srt_seconds(s: str) -> float:
    h, m, sec, ms = _SRT_T.match(s.strip()).groups()
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_srt(text: str) -> list[dict]:
    cues = []
    for block in re.split(r"\n\s*\n", text.strip().replace("\r\n", "\n")):
        lines = [l for l in block.split("\n") if l.strip()]
        timing = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if timing is None:
            continue
        a, b = (x.strip() for x in lines[timing].split("-->"))
        try:
            cues.append({"start": _srt_seconds(a), "end": _srt_seconds(b), "text": " ".join(lines[timing + 1:])})
        except (AttributeError, ValueError):
            continue
    return cues


def tracks_from_report(report: dict, cues: Optional[Sequence[dict]] = None) -> dict:
    """Video, audio and subtitle clips from the report's timeline (the Timeline Assembler output).

    Audio: with a silent engine the lane is hatched (no sound exists). With a voice, a scene's narration
    runs from the scene start to its last subtitle cue when the .srt is known, else the whole scene."""
    video, audio, subtitles = [], [], []
    silent = bool(report.get("voice_is_silent"))
    for t in report.get("timeline", []):
        s, e = float(t["start_s"]), float(t["start_s"]) + float(t["duration_s"])
        video.append({"start": s, "end": e, "label": f"Scene {t['scene']} · {t['mode']}", "short": str(t["scene"]),
                      "mode": t["mode"]})
        in_scene = [c for c in (cues or []) if s - 1e-6 <= c["start"] < e - 1e-6]
        a_end = min(e, max((c["end"] for c in in_scene), default=e))
        audio.append({"start": s, "end": a_end, "label": f"Scene {t['scene']} voice-over" + (" (silent)" if silent else ""),
                      "short": "" if silent else str(t["scene"]), "silent": silent})
    if cues:
        subtitles = [{"start": c["start"], "end": c["end"], "label": c["text"], "short": ""} for c in cues]
    else:
        subtitles = [{"start": float(t["start_s"]), "end": float(t["start_s"]) + float(t["duration_s"]),
                      "label": t["narration"], "short": ""} for t in report.get("timeline", [])]
    return {"video": video, "audio": audio, "subtitles": subtitles}


# ------------------------------------------------------------------ storyboard
def headline(text: str, max_words: int = 7) -> str:
    """Short scene title: the first clause of the narration, cut at max_words (with … when cut)."""
    first = re.split(r"[,:;.]", " ".join(text.split()), maxsplit=1)[0]
    words = first.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def scene_cards(report: dict) -> list[dict]:
    """One dict per scene for the storyboard and the properties panel, from the JSON report."""
    claim_of = {c["text"]: c["claim_id"] for c in report.get("claims", [])}
    animation = report.get("format") == "ANIMATION"
    out = []
    for t in report.get("timeline", []):
        labels = list(t.get("labels") or [])
        if animation:
            visual = f"Cut-out character: pose {t.get('pose', '-')}, prop {t.get('prop', '-')}"
        elif labels:
            visual = "Labels: " + " | ".join(labels)
        else:
            visual = "Infographic layout"
        claim = claim_of.get(t["narration"])
        out.append({"number": t["scene"], "title": labels[0] if labels else headline(t["narration"], 5),
                    "narration": t["narration"], "visual": visual, "layout": layout_label(t["layout"]),
                    "layout_key": t["layout"], "duration_s": float(t["duration_s"]), "start_s": float(t["start_s"]),
                    "mode": t["mode"], "claims": [claim] if claim else [],
                    "claim_texts": [t["narration"]] if claim else []})
    return out


def scene_table(cards: Sequence[dict]) -> list[dict]:
    return [{"scene": c["number"], "title": c["title"], "start_s": round(c["start_s"], 1), "length_s": round(c["duration_s"], 1),
             "mode": c["mode"], "layout": c["layout"], "narration": c["narration"], "evidence": ", ".join(c["claims"])}
            for c in cards]


def check_rows(report: dict) -> list[dict]:
    """Success criteria of the finished MP4 as (id, passed, detail)."""
    return [{"id": k, "passed": bool(v["pass"]), "detail": v["detail"]} for k, v in report.get("criteria", {}).items()]


# ------------------------------------------------------------------ projects on disk
@dataclass
class Project:
    name: str                   # file stem, unique
    video_path: Path
    report_path: Path
    srt_path: Optional[Path]
    title: str
    fmt: str
    total_s: float
    scenes: int
    modified: float
    meta: dict = field(default_factory=dict)


def _sidecar(video: Path) -> Path:
    return video.with_suffix(".studio.json")


def write_sidecar(video: Path, meta: dict) -> None:
    """UI settings that the report does not hold (voice name, speed, subtitles, idea)."""
    _sidecar(video).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_sidecar(video: Path) -> dict:
    try:
        return json.loads(_sidecar(video).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load_report(path: Path) -> Optional[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and "timeline" in data and "total_s" in data else None


def list_projects(videos_dir: Path) -> list[Project]:
    """Finished videos: an .mp4 with a readable .report.json next to it (the video path inside the report is
    ignored: it may be from another computer). Newest first."""
    videos_dir = Path(videos_dir)
    out = []
    if not videos_dir.is_dir():
        return out
    for rp in videos_dir.glob("*.report.json"):
        video = rp.with_name(rp.name[: -len(".report.json")] + ".mp4")
        report = load_report(rp)
        if report is None or not video.exists():
            continue
        meta = read_sidecar(video)
        srt = video.with_suffix(".srt")
        out.append(Project(name=video.stem, video_path=video, report_path=rp, srt_path=srt if srt.exists() else None,
                           title=meta.get("title") or report.get("request") or video.stem,
                           fmt=str(report.get("format", "")), total_s=float(report["total_s"]),
                           scenes=int(report.get("scenes", len(report["timeline"]))),
                           modified=max(video.stat().st_mtime, rp.stat().st_mtime), meta=meta))
    out.sort(key=lambda p: p.modified, reverse=True)
    return out


def project_name(idea: str, fmt_key: str, settings: str) -> str:
    """File stem for a new video: readable slug + a short hash of every setting (same settings = same file)."""
    slug = re.sub(r"[^a-z0-9]+", "-", idea.lower().encode("ascii", "ignore").decode()).strip("-")[:28] or "video"
    return f"{slug}-{fmt_key.lower()[:4]}-{hashlib.sha1(settings.encode('utf-8')).hexdigest()[:6]}"
