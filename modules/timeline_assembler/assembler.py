"""Timeline Assembler, step 1 (report 5.5, 5.9.11; criteria S12, S13).

Places the scenes one after another using the AUDIO duration (the Segmenter's reading time is
only an estimate) and checks the hard rules. This version is a pure function: no FFmpeg, no
files, so it is deterministic and easy to test. The adjustment loop N4 -> N3 -> N2 and the MP4
render (FFmpeg) are separate, later steps that consume the Timeline produced here.

  d_scene = max(d_audio + pad, t_min)                       (pseudocode in report 5.5)

Codes in Timeline.codes (empty = all good):
  NO_SCENES            nothing to place
  SCENE_TOO_LONG       a scene is longer than t_max      (the Segmenter must split/shorten it)
  TOTAL_OUT_OF_RANGE   total outside [t_total_min, t_total_max]   (S12)
  DEVIATION_OVER_5PCT  |total - T_target| / T_target > 5%         (S13)
"""
from __future__ import annotations

from typing import Callable, Mapping, Sequence

from core.models import FormatProfile, Scene, Timeline, TimelineEntry
from modules.voice_segmenter.segmenter import split_sentences

DEVIATION_MAX = 0.05     # S13
_EPS = 1e-9              # float tolerance on the boundaries (60 s, 120 s, 5%)


def scene_audio_durations(scenes: Sequence[Scene],
                          tts: Callable[[tuple[str, ...]], float]) -> dict[int, float]:
    """Narration duration of every scene, by calling a TTS function (MockTTS or a real one).

    OPEN QUESTION (discuss with the Voice & Subtitle owner): the Voice Segmenter cuts the whole
    script into 10-12 s voice units, which need not align with scene borders. Here each scene is
    voiced on its own, exactly as in report 5.5 (`audio[sc.id]`)."""
    return {s.scene_id: tts(tuple(split_sentences(s.narration))) for s in scenes}


def assemble(scenes: Sequence[Scene], audio_durations: Mapping[int, float],
             profile: FormatProfile, t_target: float, pad_s: float = 0.0) -> Timeline:
    """Build the timeline. Does not modify `scenes`.

    pad_s is the silence added after each narration. ASSUMPTION: 0.0 until the real TTS pause is
    measured; N4 (add/remove pauses) will later tune it, within bounds, to fix the total."""
    if t_target <= 0:
        raise ValueError(f"t_target must be positive, got {t_target}")
    if pad_s < 0:
        raise ValueError(f"pad_s must be >= 0, got {pad_s}")

    tl = Timeline(t_target=float(t_target))
    if not scenes:
        tl.codes.add("NO_SCENES")
        tl.deviation = 1.0
        return tl

    t = 0.0
    for s in scenes:
        if s.scene_id not in audio_durations:
            raise ValueError(f"no audio duration for scene {s.scene_id}")
        d_audio = float(audio_durations[s.scene_id])
        if d_audio <= 0:
            raise ValueError(f"audio duration of scene {s.scene_id} must be > 0, got {d_audio}")

        d_scene = d_audio + pad_s
        if d_scene < profile.t_min - _EPS:
            d_scene = profile.t_min
            tl.stretched.append(s.scene_id)
        if d_scene > profile.t_max + _EPS:
            tl.too_long.append(s.scene_id)

        tl.entries.append(TimelineEntry(
            scene_id=s.scene_id, start_s=round(t, 6), duration_s=round(d_scene, 6),
            audio_duration_s=d_audio, pad_s=pad_s, render_mode=s.render_mode,
            transition_in=s.transition_in, claim_ids=list(s.claim_ids), narration=s.narration))
        t += d_scene

    tl.total_s = round(t, 6)
    tl.deviation = abs(tl.total_s - t_target) / t_target
    if tl.too_long:
        tl.codes.add("SCENE_TOO_LONG")
    if not (profile.t_total_min - _EPS <= tl.total_s <= profile.t_total_max + _EPS):
        tl.codes.add("TOTAL_OUT_OF_RANGE")
    if tl.deviation > DEVIATION_MAX + _EPS:
        tl.codes.add("DEVIATION_OVER_5PCT")
    return tl