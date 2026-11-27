"""The only module of the UI layer that calls the backend.

  estimate_plan(...)  runs the real pipeline (Router, claims, Scene Segmenter, Budget Optimizer, Voice
                      Segmenter, Timeline Assembler) on a planning pass with the project's simulated TTS timing,
                      so the cost and budget status can be shown BEFORE anything is rendered. No video, no audio.
  generate(...)       calls `modules.video.make_video.make_video`, exactly as the original "Make video" page did.

Neither function changes backend behaviour: same defaults, same modules, same arguments. HYBRID is not built in
the backend (make_video stops with a clear message), so the UI does not offer it as selectable.
"""
from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.models import OutputFormat
from modules.pipeline.pipeline import run_pipeline
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, pack_language, topic_keys
from modules.providers import edge_tts_provider as tts_engine
from modules.router.router import Request
from modules.video.claims import claims_from_text
from modules.video.make_video import UNAVAILABLE_MODES, make_video
from modules.video.render import DEFAULT_QUALITY, QUALITY_PROFILES
from modules.video.voice import FFmpegMissing, find_ffmpeg, make_engine
from modules.voice_library.language import detect_language
from modules.voice_library.library import (SPEED_MAX, SPEED_MIN, VoiceLibrary, VoiceLibraryError, builtin_library,
                                           load_library)
from ui import storage
from ui.adapters import facts_from_pipeline, short_title

ENGINES = {"silent": "Silent", "system": "System voice", "edge": "Edge neural voice"}
ENGINE_HELP = {"silent": "No sound. Timing follows a words-per-minute rule. Works offline.",
               "system": "Your operating system's voice (needs pyttsx3). Works offline.",
               "edge": "Natural neural voices (needs edge-tts). ONLINE: the narration text is sent to a Microsoft service."}
SUBTITLE_MODES = {"burn": "On the video", "track": "Separate track", "off": "Off"}
SUBTITLE_HELP = {"burn": "Burned into the picture and also saved as a track.",
                 "track": "Not drawn on the picture; a subtitle track in the file that players can switch on.",
                 "off": "Not in the video. The .srt file is still saved next to it."}
QUALITY_LABELS = {k: f"{q.label} · {q.size[1]}p" for k, q in QUALITY_PROFILES.items()}
QUALITY_HELP = {q.label: q.note for q in QUALITY_PROFILES.values()}
BUILT_FORMATS = (OutputFormat.INFOGRAPHIC, OutputFormat.ANIMATION)     # HYBRID: not built in the backend


# ----------------------------------------------------------------------------------- environment
def load_voices() -> tuple[VoiceLibrary, Optional[str]]:
    """Voice library, plus the error text when data/voice_library.json is broken (never silently ignored)."""
    try:
        return load_library(), None
    except VoiceLibraryError as exc:
        return builtin_library(), str(exc)


def ffmpeg_ok() -> bool:
    try:
        find_ffmpeg()
        return True
    except FFmpegMissing:
        return False


def system_voice_installed() -> bool:
    return importlib.util.find_spec("pyttsx3") is not None


def edge_installed() -> bool:
    return tts_engine.is_available()


def default_engine() -> str:
    """The voice engine preselected: the offline system voice when installed, otherwise silent. Never online."""
    return "system" if system_voice_installed() else "silent"


def engine_label(kind: str) -> str:
    return ENGINES.get(kind, kind)


# ------------------------------------------------------------------------------------------ content
def demo_templates() -> list[dict]:
    """The hand-written claim packs of the project (they stand in for the REASON step)."""
    out = []
    for key in topic_keys():
        lang = pack_language(key)
        out.append({"key": key, "label": TOPIC_LABELS.get(key, key), "language": lang, "claims": len(get_sample_claims(key))})
    return out


def build_claims(source: str, pack: Optional[str], reference: str) -> list:
    """Claims for the pipeline: a demo pack, or sentences extracted from the user's own text."""
    if source == "demo":
        return get_sample_claims(pack) if pack else []
    return claims_from_text(reference)


def claims_language(claims: list) -> Optional[str]:
    return detect_language(" ".join(c.text for c in claims)) if claims else None


def request_text(topic: str, instructions: str) -> str:
    """The text the Router reads: the topic, then the optional instructions (the Router looks for format,
    duration and budget hints in it; the visual engine uses it to recognise the subject)."""
    topic, instructions = " ".join(topic.split()), " ".join(instructions.split())
    return topic + (". " + instructions if instructions else "")


# ------------------------------------------------------------------------------------------- preview
def preview_available(voice, speed: float, pitch_hz: int = 0) -> bool:
    """True only when the existing preview functionality can play this voice (bundled sample or edge-tts)."""
    try:
        return tts_engine.can_preview(voice, speed, pitch_hz=pitch_hz)
    except Exception:
        return False


def preview_audio(voice, speed: float, pitch_hz: int = 0) -> tuple[Optional[bytes], str]:
    """(audio bytes, "") or (None, reason). Uses only the fixed public sample sentence, never user text."""
    try:
        return tts_engine.get_preview(voice, speed, pitch_hz=pitch_hz).read_bytes(), ""
    except tts_engine.TTSUnavailable as exc:
        return None, str(exc)
    except Exception as exc:                                    # a preview must never take the page down
        return None, f"Preview failed: {exc}"


def cast_voice(lib: VoiceLibrary, language: str, topic: str, texts: list, instructions: str = ""):
    """Voice, speed and pitch proposed for this topic (modules/voice_library/casting.py). Offline and instant."""
    from modules.voice_library.casting import cast_voice as _cast
    return _cast(lib, language, topic, list(texts), instructions)


def research(question: str, instructions: str, kind: str, t_target: float, language: Optional[str] = None):
    """REASON step (modules/reason): reference text written by a free online LLM. Never raises."""
    from modules.ai.llm import make_llm
    from modules.reason import ResearchResult, research_topic
    try:
        llm = make_llm(kind)
    except Exception as exc:                                    # no Gemini key, unknown provider, ...
        return ResearchResult(False, language=language or "en", error=str(exc))
    return research_topic(question, llm, instructions=instructions, language=language, t_target_s=t_target)


# ------------------------------------------------------------------------------------------ estimate
def estimate_plan(topic: str, instructions: str, reference: str, source: str, pack: Optional[str], fmt_value: str,
                  t_target: int, budget: Optional[int], voice_id: str, speed: float) -> dict:
    """Planning pass of the real pipeline -> facts dict (see ui.adapters.facts_from_pipeline).

    Raises nothing for bad user input: the Router and the other stages report it in the result."""
    lib, _ = load_voices()
    voice = lib.get(voice_id)
    claims = build_claims(source, pack, reference)
    req = Request(topic=request_text(topic, instructions), reference_text=reference if source == "text" else "",
                  output_format=OutputFormat(fmt_value), t_target=int(t_target), budget=int(budget) if budget else None)
    pr = run_pipeline(req, claims, voice=voice, voice_speed=float(speed), unavailable_modes=UNAVAILABLE_MODES)
    return facts_from_pipeline(pr, len(claims))


# ---------------------------------------------------------------------------------------- generation
@dataclass
class GenParams:
    topic: str
    instructions: str
    reference: str
    source: str                      # "demo" | "text"
    pack: Optional[str]
    fmt: str                         # OutputFormat value
    t_target: int
    budget: Optional[int]            # None = automatic
    voice_id: str
    speed: float
    engine_kind: str                 # silent | system | edge
    allow_online: bool
    subtitles: str                   # burn | track | off
    topic_aware: bool
    language: str
    quality: str = DEFAULT_QUALITY         # draft | standard | high (output size and bitrate; see modules/video/render.py)
    ai_read: str = "off"                   # off | pollinations | gemini: an LLM reads the input and writes claims + picture prompts
    ai_image: str = "off"                  # off | pollinations | folder: an AI picture of each claim (INFOGRAPHIC only)
    ai_online: bool = False                # the user confirmed that text is sent to an online AI service
    ai_folder: str = ""                    # folder of hand-made pictures for ai_image == "folder"
    pitch_hz: int = 0                      # voice pitch offset (Edge voices only), proposed by voice casting
    voice_mood: str = ""                   # mood chosen by voice casting ("" = the user picked the voice)
    content_origin: str = "user"           # "ai": the reference text was written by the REASON step (not verified)


@dataclass
class Outcome:
    ok: bool
    project_id: Optional[str] = None
    error: str = ""
    facts: dict = field(default_factory=dict)
    report: dict = field(default_factory=dict)
    adjustments: list = field(default_factory=list)
    engine_name: str = ""
    silent: Optional[bool] = None
    seconds: float = 0.0


def _record(p: GenParams, pid: str, voice, engine_name: str, res, facts: dict, n_claims: int) -> dict:
    pr = res.pipeline
    audio = {e.scene_id: e.audio_duration_s for e in pr.timeline.entries} if pr.timeline else {}
    return {
        "schema": 1, "id": pid, "title": short_title(request_text(p.topic, ""), 90), "created": time.time(),
        "request_text": request_text(p.topic, p.instructions), "instructions": p.instructions,
        "content_source": p.source, "pack": p.pack, "language": p.language,
        **({"content_origin": p.content_origin} if p.content_origin != "user" else {}),
        "voice": {"id": voice.voice_id, "name": voice.name, "speed": f"×{p.speed:g}", "engine": engine_label(p.engine_kind),
                  "engine_id": engine_name,
                  **({"pitch": f"{p.pitch_hz:+d} Hz"} if p.pitch_hz else {}), **({"mood": p.voice_mood} if p.voice_mood else {})},
        "requested": {"format": p.fmt, "t_target": p.t_target, "budget": p.budget},
        "options": {"subtitles": p.subtitles, "topic_aware": p.topic_aware, "quality": p.quality,
                    **({"ai_read": p.ai_read, "ai_image": p.ai_image} if (p.ai_read, p.ai_image) != ("off", "off") else {})},
        "pipeline": facts,
        "claims": [{"claim_id": c.claim_id, "text": c.text, "facet": c.facet, "importance": c.importance}
                   for c in (pr.selection.claims if pr.selection else [])],
        "scenes": [{"scene": s.scene_id, "claim_ids": list(s.claim_ids), "facet": s.facet, "explain_pattern": s.explain_pattern,
                    "mode": s.render_mode.value if s.render_mode else None, "cost": s.cost_credit, "importance": s.importance,
                    "audio_s": audio.get(s.scene_id)} for s in pr.scenes],
        "claims_available": n_claims,
    }


def generate(p: GenParams, progress: Optional[Callable[[float, str], None]] = None,
             on_stage: Optional[Callable[[str, str, str], None]] = None) -> Outcome:
    """Build the video with the existing `make_video` (the same call the original page made)."""
    t0 = time.time()
    lib, _ = load_voices()
    voice = lib.get(p.voice_id)
    try:
        engine = make_engine(p.engine_kind, voice, p.speed, p.allow_online, voice.planning_wpm(p.speed), pitch_hz=p.pitch_hz)
    except Exception as exc:                                   # missing package, online not confirmed, ...
        return Outcome(False, error=f"Voice engine: {exc}")
    claims = build_claims(p.source, p.pack, p.reference)
    text = request_text(p.topic, p.instructions)
    ai = None
    if (p.ai_read, p.ai_image) != ("off", "off"):
        from modules.ai.net import AIError
        from modules.ai.reader import claims_for_duration
        from modules.ai.setup import prepare_ai
        if on_stage:
            on_stage("ai_read", "start", "The AI is reading your input and writing claims…" if p.ai_read != "off" else "Preparing the AI pictures…")
        try:
            ai = prepare_ai(text, p.reference if p.source == "text" else "", claims, read_kind=p.ai_read,
                            image_kind=p.ai_image,
                            folder=Path(p.ai_folder) if p.ai_folder else None, allow_online=p.ai_online,
                            n_scenes=claims_for_duration(p.t_target), cache_dir=storage.videos_dir().parent / "ai_cache")
        except AIError as exc:
            return Outcome(False, error=f"AI: {exc}")
        if ai.claims:
            claims = ai.claims
    if not claims:
        return Outcome(False, error="No usable sentence (8–24 words) was found in the reference material."
                       + (" " + " ".join(ai.notes) if ai and ai.notes else ""))
    pid = storage.project_key(text, p.reference, p.source, p.pack, p.fmt, p.t_target, p.budget, p.voice_id, p.speed,
                              engine.name, p.subtitles, p.topic_aware,
                              *(() if p.quality == DEFAULT_QUALITY else (p.quality,)),      # default keeps the ids of older videos
                              *(() if ai is None else (p.ai_read, p.ai_image, " ".join(c.text for c in claims))))
    out = storage.videos_dir() / f"{pid}.mp4"
    res = make_video(text, claims, out, engine=engine, voice=voice, speed=p.speed,
                     reference_text=p.reference if p.source == "text" else "", t_target=p.t_target, budget=p.budget,
                     output_format=OutputFormat(p.fmt), burn_subtitles=p.subtitles == "burn",
                     soft_subtitles=p.subtitles != "off", visual_engine=p.topic_aware, progress=progress, quality=p.quality,
                     art=ai.art if ai else None, visuals=ai.visuals if ai else None,
                     ai_notes=ai.notes if ai else (), on_stage=on_stage)
    facts = facts_from_pipeline(res.pipeline, len(claims))
    silent = bool(res.report.get("voice_is_silent")) if res.ok else None
    if not res.ok:
        return Outcome(False, error=res.error, facts=facts, adjustments=list(res.log), engine_name=engine.name,
                       silent=None, seconds=time.time() - t0)
    storage.save_record(pid, _record(p, pid, voice, engine.name, res, facts, len(claims)))
    return Outcome(True, project_id=pid, facts=facts, report=res.report, adjustments=list(res.log), engine_name=engine.name,
                   silent=silent, seconds=time.time() - t0)


__all__ = ["ENGINES", "SUBTITLE_MODES", "BUILT_FORMATS", "GenParams", "Outcome", "estimate_plan", "generate", "load_voices",
           "ffmpeg_ok", "SPEED_MIN", "SPEED_MAX", "Path"]
