"""Generation workspace: stage tracker + live render progress, then the Video Studio (or a clear failure)."""
from __future__ import annotations

import streamlit as st

from ui import components as C
from ui import runner
from ui import state as S
from ui.adapters import LiveStages, stage_view
from ui.widgets import btn, html, rerun

LIVE_NOTE = "Each step shows Waiting, Working or Done as the backend reaches it."


def _back() -> None:
    st.session_state["gen_state"] = "idle"
    st.session_state["view"] = "create"


def render() -> None:
    ss = st.session_state
    job = ss.get("job")
    html(C.heading("Creating your video", "A step turns green only after the backend reports it finished."))
    left, right = st.columns([1.35, 1], gap="large")

    if job is not None:                                           # ---- run the real generation, once
        ss["job"] = None                                          # a rerun during the run must not start a second job
        with left:
            tracker = st.empty()
            live = LiveStages()

            def draw() -> None:
                sub = f"Adjusting: {live.note}" if live.note else LIVE_NOTE
                tracker.markdown(C.progress_tracker(live.view(), "Working on it…", sub, pending_label="Waiting"), unsafe_allow_html=True)
                frac, text = live.progress()
                bar.progress(frac, text=text)
        with right:
            note = st.empty()
            note.markdown(C.alert("info", "Generating", "This usually takes 30–60 s for a 90 s video. Keep this page open."), unsafe_allow_html=True)
            bar = st.progress(0.0, text="Starting…")
        draw()

        def on_stage(key: str, state: str, detail: str = "") -> None:
            live.update(key, state, detail)
            draw()

        last = {"msg": None}

        def on_progress(frac: float, msg: str) -> None:             # frames: redraw only when the scene changes
            live.set_render(min(1.0, max(0.0, frac)), msg)
            if msg != last["msg"]:
                last["msg"] = msg
                draw()
            else:
                frac, text = live.progress()
                bar.progress(frac, text=text)

        outcome = runner.generate(job, progress=on_progress, on_stage=on_stage)
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
