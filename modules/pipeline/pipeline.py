"""Pipeline demo (Lab04 feature): one request in, a checked timeline out.

    Router -> Scene Segmenter -> Budget Optimizer -> Voice Segmenter -> Timeline Assembler

This module only ORCHESTRATES the existing modules; it adds no new algorithm. Each stage either
passes its result on or stops the run with a status that says which stage stopped it and why.

SIMULATED parts (labelled so in the UI and the report):
  * the claims come from `sample_claims.py` (the REASON step is not built yet)
  * narration durations come from `MockTTS` (no real TTS has been measured yet)

VOICE CHOICE (optional): pass a `VoiceProfile` from the voice library (+ a speaking speed). It
  * sets the speaking rate the planner assumes (`voice.planning_wpm(speed)`; the library's
    ASSUMED default until that voice has been measured), for claim selection and voice units;
  * is checked against the narration language: an English voice never reads Vietnamese claims
    (stage VOICE stops with VOICE_LANGUAGE_MISMATCH, before anything is planned).
Without a voice the behaviour is exactly what it was before the voice library existed.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Callable, Optional, Sequence

from core.config import PROFILES, VOICE_WPM
from core.models import FormatProfile, OptimizeResult, Scene, Timeline
from modules.budget_optimizer.optimizer import min_cost_with_motion, optimize
from modules.providers.mock_tts import MockTTS
from modules.router.intent_parser import parse_intent_v3
from modules.router.router import Request, RouteDecision, RouteStatus, route
from modules.scene_segmenter.segmenter import Claim, SegParams, Selection, build_scenes, select_claims
from modules.timeline_assembler.assembler import assemble, scene_audio_durations
from modules.voice_library.language import detect_language
from modules.voice_library.library import LANGUAGES, VoiceProfile
from modules.voice_segmenter.segmenter import (VoiceParams, VoiceSegmentation, in_band,
                                               segment_voices, split_sentences)

# ASSUMPTION: simulated TTS defaults (not a measurement of any real voice).
DEFAULT_TTS_PARAMS = {"true_wpm": VOICE_WPM, "noise_sd": 0.06, "pause_s": 0.3, "seed": 0}
# ASSUMPTION: when no budget is given, allow twice the cheapest feasible plan.
AUTO_BUDGET_FACTOR = 2


class Stage(str, Enum):
    ROUTER = "router"
    SCENES = "scene_segmenter"
    BUDGET = "budget_optimizer"
    VOICE = "voice_segmenter"
    TIMELINE = "timeline_assembler"


STAGE_ORDER = [Stage.ROUTER, Stage.SCENES, Stage.BUDGET, Stage.VOICE, Stage.TIMELINE]


class PipelineStatus(str, Enum):
    OK = "OK"
    ROUTER_REJECTED = "ROUTER_REJECTED"
    ROUTER_CLARIFY = "ROUTER_CLARIFY"
    VOICE_LANGUAGE_MISMATCH = "VOICE_LANGUAGE_MISMATCH"
    SCENES_INVALID = "SCENES_INVALID"
    BUDGET_INFEASIBLE = "BUDGET_INFEASIBLE"
    TIMELINE_CHECKS_FAILED = "TIMELINE_CHECKS_FAILED"


@dataclass
class StageLog:
    stage: Stage
    ok: bool
    summary: str


@dataclass
class PipelineResult:
    request: Request
    status: PipelineStatus = PipelineStatus.OK
    stopped_at: Optional[Stage] = None                 # None when every stage ran
    stages: list[StageLog] = field(default_factory=list)
    decision: Optional[RouteDecision] = None
    selection: Optional[Selection] = None
    scenes: list[Scene] = field(default_factory=list)
    scene_report: dict = field(default_factory=dict)
    budget: Optional[int] = None
    budget_source: str = ""                            # request | text | auto
    optimize: Optional[OptimizeResult] = None
    voice: Optional[VoiceSegmentation] = None
    voice_profile: Optional[VoiceProfile] = None       # the voice the user picked (None = no choice)
    voice_speed: float = 1.0
    planning_wpm: float = VOICE_WPM                    # speaking rate the planner assumed
    voice_in_band_share: Optional[float] = None        # S19 on the ESTIMATED durations
    timeline: Optional[Timeline] = None
    messages: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == PipelineStatus.OK


def voice_band_share(seg: VoiceSegmentation, p: VoiceParams = VoiceParams()) -> float:
    """Share of voice units whose estimated length is inside [v_min, v_max] (S19 definition;
    the last unit may be shorter). 1.0 for an empty segmentation."""
    n = len(seg.units)
    if n == 0:
        return 1.0
    good = sum(in_band(u.est_s, p, last=(i == n - 1)) for i, u in enumerate(seg.units))
    return good / n


def _stop(res: PipelineResult, stage: Stage, status: PipelineStatus, summary: str,
          messages: Sequence[str] = ()) -> PipelineResult:
    res.stages.append(StageLog(stage, False, summary))
    res.status, res.stopped_at = status, stage
    res.messages.extend(messages)
    return res


def _resolve_budget(request: Request, scenes: list[Scene], profile: FormatProfile) -> tuple[int, str]:
    if request.budget is not None:
        return request.budget, "request"
    from_text = parse_intent_v3(request.topic).budget
    if from_text is not None:
        return from_text, "text"
    return AUTO_BUDGET_FACTOR * (min_cost_with_motion(scenes, profile) or 0), "auto"


def run_pipeline(request: Request, claims: Sequence[Claim], *,
                 router_algorithm: str = "v3_hardened",
                 selection_algorithm: str = "D2f_mmr_facet",
                 optimizer_algorithm: str = "v2_dp_motion_state",
                 voice_algorithm: str = "F4_dp_share",
                 tts: Optional[Callable[[tuple[str, ...]], float]] = None,
                 pad_s: float = 0.0,
                 voice: Optional[VoiceProfile] = None,
                 voice_speed: float = 1.0,
                 unavailable_modes: frozenset = frozenset(),
                 on_stage: Optional[Callable[[str, str, str], None]] = None) -> PipelineResult:
    """Run the five stages in order and stop at the first one that fails.

    `voice` / `voice_speed` come from the voice library; ValueError if the speed is out of range.
    `unavailable_modes`: render modes that cannot be produced right now (for example CLIP while no
    image-to-video provider is connected). The Budget Optimizer then plans without them.

    `on_stage(key, state, detail)` is called as the work happens, so a UI can show real progress. `state` is
    "start", "done" or "failed"; `key` is a Stage value, or "claims" (claim selection, inside the scene stage) or
    "narration_audio" (the voice engine measuring each scene's real audio, inside the timeline stage)."""
    emit = on_stage or (lambda *_: None)

    def stop(res_: PipelineResult, stage: Stage, status: PipelineStatus, summary: str, messages: Sequence[str] = ()) -> PipelineResult:
        out = _stop(res_, stage, status, summary, messages)
        emit(stage.value, "failed", " ".join(list(messages)[:2]) or summary)
        return out

    planning_wpm = voice.planning_wpm(voice_speed) if voice is not None else VOICE_WPM
    tts = tts or MockTTS(**{**DEFAULT_TTS_PARAMS, "true_wpm": planning_wpm})
    res = PipelineResult(request=request, voice_profile=voice, voice_speed=voice_speed,
                         planning_wpm=planning_wpm)

    # 1. Router -------------------------------------------------------------
    emit(Stage.ROUTER.value, "start", "")
    d = route(request, router_algorithm)
    res.decision = d
    res.messages.extend(d.messages)
    if d.status == RouteStatus.REJECT:
        return stop(res, Stage.ROUTER, PipelineStatus.ROUTER_REJECTED,
                     f"REJECT {sorted(d.codes)}")
    if d.status == RouteStatus.CLARIFY:
        return stop(res, Stage.ROUTER, PipelineStatus.ROUTER_CLARIFY,
                     f"CLARIFY {sorted(d.codes)}")
    res.stages.append(StageLog(Stage.ROUTER, True,
                               f"ACCEPT: {d.fmt.value}, {d.t_target} s, {d.word_count} input words"))
    emit(Stage.ROUTER.value, "done", f"{d.fmt.value.title()} video, {d.t_target} s target, {d.word_count} input words")
    profile = PROFILES[d.fmt]
    if unavailable_modes:
        profile = replace(profile, allowed_modes=tuple(m for m in profile.allowed_modes
                                                       if m not in unavailable_modes))

    # Voice choice: an English voice must not read Vietnamese narration (or the other way round).
    if voice is not None:
        spoken = detect_language(" ".join(c.text for c in claims))
        if spoken is not None and spoken != voice.language:
            return stop(res, Stage.VOICE, PipelineStatus.VOICE_LANGUAGE_MISMATCH,
                         f"voice {voice.name} speaks {voice.language}, narration is {spoken}",
                         [f"The narration is in {LANGUAGES[spoken]} but the voice {voice.name} speaks "
                          f"{LANGUAGES[voice.language]}. Choose a voice for {LANGUAGES[spoken]} narration, "
                          f"or switch to a claim pack in {LANGUAGES[voice.language]}."])

    # 2. Scene Segmenter ----------------------------------------------------
    params = SegParams(wpm=planning_wpm)
    emit("claims", "start", "")
    res.selection = select_claims(list(claims), d.t_target, selection_algorithm, params)
    emit("claims", "done", f"{len(res.selection.claims)} of {len(claims)} claims selected ({res.selection.algorithm})")
    emit(Stage.SCENES.value, "start", "")
    res.scenes, res.scene_report = build_scenes(res.selection, d.fmt, params, profile.t_min, profile.t_max)
    rep = res.scene_report
    if not rep["scene_count_ok"]:
        return stop(res, Stage.SCENES, PipelineStatus.SCENES_INVALID,
                     f"{rep['n_scenes']} scenes (need 6-30)",
                     ["Not enough usable claims to build 6-30 scenes; add claims or change the duration."])
    res.stages.append(StageLog(Stage.SCENES, True,
                               f"{rep['n_scenes']} scenes, {len(res.selection.claims)}/{len(claims)} claims "
                               f"({res.selection.algorithm}), estimated {rep['total_s']} s"))
    emit(Stage.SCENES.value, "done", f"{rep['n_scenes']} scenes, about {rep['total_s']} s before narration is measured")

    # 3. Budget Optimizer ---------------------------------------------------
    emit(Stage.BUDGET.value, "start", "")
    res.budget, res.budget_source = _resolve_budget(request, res.scenes, profile)
    res.optimize = optimize(res.scenes, res.budget, profile, optimizer_algorithm)
    if not res.optimize.feasible:
        return stop(res, Stage.BUDGET, PipelineStatus.BUDGET_INFEASIBLE,
                     f"INFEASIBLE at budget {res.budget}: {res.optimize.reason}",
                     [m for m in (res.optimize.reason, res.optimize.suggestion) if m])
    o = res.optimize
    res.stages.append(StageLog(Stage.BUDGET, True,
                               f"cost {o.total_cost}/{res.budget} ({res.budget_source} budget), "
                               f"motion {o.motion_ratio:.0%} ({o.algorithm})"))
    emit(Stage.BUDGET.value, "done", f"{o.total_cost} of {res.budget} credits, {o.motion_ratio:.0%} of scenes move")

    # 4. Voice Segmenter ----------------------------------------------------
    emit(Stage.VOICE.value, "start", "")
    sentences = [s for sc in res.scenes for s in split_sentences(sc.narration)]
    voice_params = VoiceParams(wpm=planning_wpm)
    res.voice = segment_voices(sentences, voice_algorithm, voice_params)
    res.voice_in_band_share = voice_band_share(res.voice, voice_params)
    who = "" if voice is None else f"; voice {voice.name} x{voice_speed:g} at {planning_wpm:.0f} wpm" \
        + ("" if voice.wpm_is_measured else " (assumed)")
    res.stages.append(StageLog(Stage.VOICE, True,
                               f"{len(res.voice.units)} voice units, {res.voice_in_band_share:.0%} in "
                               f"10-12 s band (estimated, {res.voice.algorithm}){who}"))
    emit(Stage.VOICE.value, "done", f"{len(res.voice.units)} voice units")

    # 5. Timeline Assembler -------------------------------------------------
    emit("narration_audio", "start", "")
    durations = scene_audio_durations(res.scenes, tts)
    emit("narration_audio", "done", f"{len(res.scenes)} scenes of narration measured")
    emit(Stage.TIMELINE.value, "start", "")
    res.timeline = assemble(res.scenes, durations, profile, d.t_target, pad_s)
    tl = res.timeline
    summary = f"total {tl.total_s:.1f} s vs target {tl.t_target:.0f} s (deviation {tl.deviation:.1%})"
    if not tl.ok:
        return stop(res, Stage.TIMELINE, PipelineStatus.TIMELINE_CHECKS_FAILED,
                     f"{summary}; codes {sorted(tl.codes)}")
    res.stages.append(StageLog(Stage.TIMELINE, True, summary + "; S12/S13 hold"))
    emit(Stage.TIMELINE.value, "done", f"{tl.total_s:.1f} s timeline, {tl.deviation:.1%} from target")
    return res
