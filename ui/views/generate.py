"""Generation workspace: stage tracker + live render progress, then the Video Studio (or a clear failure)."""
from __future__ import annotations

import streamlit as st

from ui import components as C
from ui import runner
from ui import state as S
from ui.adapters import stage_view
from ui.widgets import btn, html, rerun

WAIT_NOTE = ("The planner, narration and timeline steps run first as one job, so their results appear when it finishes. "
             "Frame rendering reports live progress below.")


def _back() -> None:
    st.session_state["gen_state"] = "idle"
    st.session_state["view"] = "create"


def render() -> None:
    ss = st.session_state
    job = ss.get("job")
    html(C.heading("Creating your video", "Each stage turns green only after the backend confirms it."))
    left, right = st.columns([1.35, 1], gap="large")

    if job is not None:                                           # ---- run the real generation, once
        ss["job"] = None                                          # a rerun during the run must not start a second job
        with left:
            tracker = st.empty()
            tracker.markdown(C.progress_tracker(stage_view(None), "Working on it…", WAIT_NOTE, pending_label="Waiting"), unsafe_allow_html=True)
        with right:
            note = st.empty()
            note.markdown(C.alert("info", "Generating", "This usually takes 30–60 s for a 90 s video. Keep this page open."), unsafe_allow_html=True)
            bar = st.progress(0.0, text="Planning and measuring narration…")

        def on_progress(frac: float, msg: str) -> None:
            bar.progress(min(1.0, max(0.0, frac)), text=f"Rendering frames · {msg}")

        outcome = runner.generate(job, progress=on_progress)
        bar.empty()
        tracker.empty()                                           # the working view must not stay next to the result
        note.empty()
        ss["last_outcome"] = outcome
        if outcome.ok:
            ss["gen_state"] = "done"
            ss["project"], ss["sel_scene"] = outcome.project_id, None
            ss["view"] = "studio"
            rerun()
            return
        ss["gen_state"] = "failed"

    outcome = ss.get("last_outcome")
    if outcome is None:                                           # opened with no job: interrupted run or direct visit
        if ss["gen_state"] == "running":
            html(C.alert("warn", "The previous run was interrupted", "Changing a control while a video is being made stops the run. Start it again."))
        else:
            html(C.empty_state("Nothing is being generated", "Set up a project and press Create Video.", "video"))
        ss["gen_state"] = "idle"
        btn("Back to settings", key="gen_back0", on_click=_back)
        return

    with left:                                                    # ---- failure view (success moved on to the studio)
        st.markdown(C.progress_tracker(stage_view(outcome.facts or None, video_ok=False, engine_name=outcome.engine_name,
                                                             error=outcome.error if outcome.facts else ""),
                                       "Generation stopped", "Stages after the one that stopped were not reached."), unsafe_allow_html=True)
    with right:
        html(C.alert("err", "The video could not be created", outcome.error or "Unknown error."))
        for line in outcome.adjustments:
            html(C.alert("info", "Automatic adjustment tried", line))
        btn("Back to settings", key="gen_back", type="primary", on_click=_back)
