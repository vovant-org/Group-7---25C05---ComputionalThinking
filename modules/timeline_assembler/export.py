"""Timeline -> JSON in the three-track shape of the report (Part 4(d)).

    {"tracks": {"video": [...], "audio": [...], "subtitle": [...]}, "fps": 24, "resolution": [1280, 720]}

ASSUMPTIONS (no rendering exists yet): asset ids are placeholders derived from the scene id
("V-03", "A-003"); the audio and subtitle clips last as long as the (simulated or real) narration,
the video clip lasts the whole scene (narration + pad, or t_min if the scene was stretched).
"""
from __future__ import annotations

from core.models import Timeline

DEFAULT_FPS = 24
DEFAULT_RESOLUTION = (1280, 720)


def timeline_to_dict(tl: Timeline, fps: int = DEFAULT_FPS,
                     resolution: tuple[int, int] = DEFAULT_RESOLUTION) -> dict:
    video, audio, subtitle = [], [], []
    for e in tl.entries:
        start = round(e.start_s, 3)
        video.append({"scene_id": e.scene_id, "asset_id": f"V-{e.scene_id:02d}",
                      "render_mode": e.render_mode.value if e.render_mode else None,
                      "transition_in": e.transition_in,
                      "start_s": start, "end_s": round(e.start_s + e.duration_s, 3)})
        narration_end = round(e.start_s + e.audio_duration_s, 3)
        audio.append({"audio_asset_id": f"A-{e.scene_id:03d}", "start_s": start, "end_s": narration_end})
        subtitle.append({"text": e.narration, "start_s": start, "end_s": narration_end})
    return {"tracks": {"video": video, "audio": audio, "subtitle": subtitle},
            "fps": fps, "resolution": list(resolution),
            "total_s": round(tl.total_s, 3), "t_target": tl.t_target,
            "checks": sorted(tl.codes)}
