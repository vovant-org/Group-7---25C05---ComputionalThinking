"""Generation screen: the seven steps with their real state, then the Studio.

Two honest phases, both through `make_video`:
  1. planning (render=False): Router, claims, scenes, budget, narration, timeline. The steps turn green only
     from the stage logs of that run.
  2. rendering (render=True): FFmpeg progress comes from the render callback; the last step turns green only
     when the finished MP4 was measured and its criteria computed.
The narration audio of phase 1 is cached in the work folder, so phase 2 does not speak it again.
"""
from __future__ import annotations

import streamlit as st

from core.models import OutputFormat
from modules.video.make_video import make_video
from modules.video.voice import make_engine
from modules.voice_library.library import VoiceLibrary
from ui import components as C
from ui import state as S
from ui import studio_logic as L


def _back_button(label: str = "← Back to the editor") -> None:
    st.button(label, on_click=S.go, args=("new",))


def render(lib: VoiceLibrary) -> None:
    job = st.session_state.get("job")
    if not job:                                              # opened by hand, nothing to generate
        S.go("new")
        st.rerun()
    if job["state"] == "done":                               # a rerun after the video was finished
        S.open_project(job["name"])
        st.rerun()
    job["state"] = "running"
    st.markdown(C.hero("Creating your video", f"{job['idea']}"), unsafe_allow_html=True)
    badges = " ".join([C.badge(job["fmt"].title(), "accent"), C.badge(f"{job['duration']} s", "muted"),
                       C.badge(f"{job['voice'].name} · {job['voice'].language}", "muted"),
                       C.badge("Silent" if job["engine"] == "silent" else job["engine"], "muted")])
    st.markdown(badges, unsafe_allow_html=True)
    tracker = st.empty()
    note = st.empty()
    tracker.markdown(C.progress_tracker(L.stage_cards(None, started=True)), unsafe_allow_html=True)

    out = S.VIDEOS_DIR / f"{job['name']}.mp4"
    S.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    work = out.parent / (out.stem + "_work")
    try:
        engine = make_engine(job["engine"], job["voice"], job["speed"], job["online"], job["voice"].planning_wpm(job["speed"]))
    except Exception as exc:                                 # missing package, online use not confirmed, ...
        tracker.markdown(C.progress_tracker(L.stage_cards(None, error=f"Voice engine: {exc}")), unsafe_allow_html=True)
        st.markdown(C.error_box("The narration engine is not ready", str(exc)), unsafe_allow_html=True)
        _back_button()
        return

    common = dict(engine=engine, voice=job["voice"], speed=job["speed"], reference_text=job["reference"],
                  t_target=job["duration"], budget=job["budget"], output_format=OutputFormat(job["fmt"]),
                  burn_subtitles=job["burn"], visual_engine=job["topic_engine"], work_dir=work)

    # ---- phase 1: plan, narrate, assemble
    note.caption("Planning the story and measuring the narration…")
    plan = make_video(job["request"], job["claims"], out, render=False, **common)
    steps = L.stage_cards(plan.pipeline, error="" if plan.ok else plan.error)
    tracker.markdown(C.progress_tracker(steps), unsafe_allow_html=True)
    if not plan.ok:
        note.empty()
        st.markdown(C.error_box("The video could not be planned", plan.error), unsafe_allow_html=True)
        for line in plan.log:
            st.caption("adjustment: " + line)
        _back_button()
        return

    # ---- phase 2: render with FFmpeg
    bar = st.progress(0.0, text="Rendering…")

    def on_progress(frac: float, msg: str) -> None:
        frac = min(1.0, max(0.0, frac))
        bar.progress(frac, text=f"Rendering {msg}")
        tracker.markdown(C.progress_tracker(L.stage_cards(plan.pipeline, render_frac=frac)), unsafe_allow_html=True)

    note.caption("Drawing every frame and joining picture, voice and subtitles…")
    res = make_video(job["request"], job["claims"], out, render=True, progress=on_progress, **common)
    bar.empty()
    note.empty()
    if not res.ok:
        tracker.markdown(C.progress_tracker(L.stage_cards(res.pipeline, error=res.error)), unsafe_allow_html=True)
        st.markdown(C.error_box("The video could not be rendered", res.error), unsafe_allow_html=True)
        _back_button()
        return

    tracker.markdown(C.progress_tracker(L.stage_cards(res.pipeline, report=res.report)), unsafe_allow_html=True)
    L.write_sidecar(res.video_path, {"title": job["idea"], "request": job["request"], "voice_id": job["voice"].voice_id,
                                     "voice_name": job["voice"].name, "language": job["language"], "speed": job["speed"],
                                     "engine": job["engine"], "subtitles_burned": job["burn"],
                                     "format_choice": job["fmt"], "budget": job["budget"],
                                     "content": "demo claim pack" if job["source"] == "pack" else "reference text"})
    job["state"] = "done"
    S.open_project(job["name"])
    st.rerun()
