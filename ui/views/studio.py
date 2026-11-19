"""Video Studio: preview, timeline, storyboard and a read-only properties panel for one project.

Everything shown is read from the project's files (see ui/storage.py). There are no editing controls: the
backend cannot edit a scene, so none is drawn.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from ui import components as C
from ui import state as S
from ui import storage
from ui.adapters import stage_view, storyboard_scenes, timeline_data
from ui.widgets import btn, card_button, html, stretch


def _select(number: int) -> None:
    st.session_state["sel_scene"] = number


def _again() -> None:
    S.goto("create")


def render() -> None:
    ss = st.session_state
    proj = storage.load_project(ss["project"]) if ss.get("project") else None
    if proj is None:
        html(C.empty_state("No project open", "Create a video or open one from My Projects.", "video"))
        btn("New Project", key="studio_new", type="primary", on_click=S.goto, args=("create",))
        return
    rep, rec = proj["report"], proj["record"]
    scenes = storyboard_scenes(rep, rec)
    tl = timeline_data(scenes, proj["cues"], rec)
    if ss["sel_scene"] not in [s["number"] for s in scenes]:
        ss["sel_scene"] = scenes[0]["number"] if scenes else None
    selected = next((s for s in scenes if s["number"] == ss["sel_scene"]), None)
    crit = rep.get("criteria", {})
    passed = sum(1 for v in crit.values() if v.get("pass"))
    silent = bool(rep.get("voice_is_silent"))
    title = (rec or {}).get("title") or rep.get("request", proj["id"])

    # ---- header + metrics
    h1, h2 = st.columns([4, 1])
    with h1:
        html(C.heading(title, "Video Studio"))
    with h2:
        btn("Make another", icon="add", key="studio_again", on_click=_again)
    cost = ((rec or {}).get("pipeline") or {}).get("cost")
    budget = ((rec or {}).get("pipeline") or {}).get("budget")
    m = [("Format", str(rep.get("format", "")).title(), f'{rep.get("resolution", ["?", "?"])[0]}×{rep.get("resolution", ["?", "?"])[1]} · {rep.get("fps", "?")} fps', "video"),
         ("Length", f'{rep["total_s"]:.1f} s', f'target {rep["t_target"]:.0f} s · {rep["deviation"]:.1%} off', "clock"),
         ("Scenes", str(rep["scenes"]), f'{rep.get("subtitle_cues", len(proj["cues"]))} subtitle cues', "layout"),
         ("Checks", f"{passed}/{len(crit)} passed" if crit else "—", "length and format checks", "check")]
    if cost is not None:
        m.append(("Plan cost", f"{cost}/{budget}" if budget else str(cost), "assumed credits", "coin"))
    for col, (lab, val, hint, ico) in zip(st.columns(len(m)), m):
        with col:
            html(C.metric_card(lab, val, hint, ico))

    main, side = st.columns([2.1, 1], gap="large")
    with main:
        S_ = "<span class='sf-split'></span>"
        html(S_)
        # ---- main video preview
        html(C.section("Preview"))
        if proj["video_path"] is not None:
            html(C.badges([("Video rendered", "ok"), (str(rep.get("format", "")).title(), "accent"),
                           (f'{rep["total_s"]:.1f} s', "neutral"), ("Silent audio track" if silent else "Narrated", "warn" if silent else "ok")]))
            st.video(str(proj["video_path"]))
        else:
            html(C.badges([("No video file", "warn"), (str(rep.get("format", "")).title(), "accent")]))
            html(C.storyboard_preview("Storyboard preview only", "The MP4 of this project is not in outputs/videos/ (it may have been moved or "
                                      "deleted). The scenes and timeline below come from the saved report."))
        if silent:
            html(C.alert("warn", "This video has no sound", "It was made with the silent engine. Create it again with a system or Edge voice to hear the narration."))

        # ---- timeline
        html(C.section("Timeline"))
        html(C.timeline_tracks(tl["video"], tl["audio"], tl["subtitles"], tl["total_s"], selected_scene=ss["sel_scene"], silent=silent,
                               subtitles_note="No .srt file found for this project"))

        # ---- storyboard
        sb1, sb2 = st.columns([3, 1])
        with sb1:
            html(C.section("Storyboard"))
        with sb2:
            st.radio("View", ["Cards", "Table"], key=S.seed("board_view"), on_change=S.sync, args=("board_view",), horizontal=True,
                     label_visibility="collapsed")
        if ss["board_view"] == "Table":
            rows = [{"#": s["number"], "Start (s)": round(s["start_s"], 1), "Length (s)": round(s["duration_s"], 1), "Mode": s["mode"],
                     "Layout": s["layout"], "Narration": s["narration"], "Visual": s["visual"],
                     "Claims": ", ".join(c["claim_id"] for c in s["claims"]) or "—"} for s in scenes]
            st.dataframe(pd.DataFrame(rows), hide_index=True, **stretch(st.dataframe),
                         column_config={"Narration": st.column_config.TextColumn(width="large"), "Visual": st.column_config.TextColumn(width="large")})
        else:
            per_row = 2
            for i in range(0, len(scenes), per_row):
                for col, s in zip(st.columns(per_row), scenes[i:i + per_row]):
                    with col:
                        card_button(C.scene_card(dict(s, scene=s["number"]), selected=s["number"] == ss["sel_scene"]),
                                    "Inspect scene " + str(s["number"]), key=f"scene_{s['number']}", selected=s["number"] == ss["sel_scene"],
                                    on_click=_select, args=(s["number"],))

    with side:
        html(C.section("Properties"))
        voice = ((rec or {}).get("voice") or {}) if rec else {}
        if not voice:
            voice = {"engine": rep.get("voice_engine", "")}
        view = dict(selected, scene=selected["number"]) if selected else None
        note = "Claim links were not saved for this project (made before this UI existed)." if selected and selected["evidence_missing"] else ""
        html(C.property_panel(view, voice, note))
        st.caption("Read-only: scene editing is not part of the backend yet.")

        html(C.section("Checks"))
        for key, v in crit.items():
            html(C.alert("ok" if v.get("pass") else "err", f"{key} · {'passed' if v.get('pass') else 'failed'}", v.get("detail", "")))
        if rep.get("adjustments"):
            with st.expander("Automatic adjustments"):
                for line in rep["adjustments"]:
                    st.write("• " + line)
        pipe = (rec or {}).get("pipeline")
        if pipe:
            with st.expander("Pipeline stages"):
                st.markdown(C.progress_tracker(stage_view(pipe, video_ok=True, criteria=crit, engine_name=voice.get("engine", ""), silent=silent)),
                            unsafe_allow_html=True)

        html(C.section("Export"))
        if proj["video_path"] is not None:
            st.download_button("Download MP4", proj["video_path"].read_bytes(), file_name=proj["video_path"].name, mime="video/mp4", **stretch(st.download_button))
        if proj["srt_path"] is not None:
            st.download_button("Download subtitles (.srt)", proj["srt_path"].read_bytes(), file_name=proj["srt_path"].name, mime="text/plain",
                               **stretch(st.download_button))
        st.download_button("Download report (.json)", json.dumps(rep, ensure_ascii=False, indent=2), file_name=proj["id"] + ".report.json",
                           mime="application/json", **stretch(st.download_button))
