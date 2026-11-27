"""Video Studio: preview, a clickable timeline and a read-only properties panel for one project.

Everything shown is read from the project's files (see ui/storage.py). There are no editing controls: the
backend cannot edit a scene, so none is drawn.
"""
from __future__ import annotations

import html as _html
import json
import math

import streamlit as st

from ui import components as C
from ui import state as S
from ui import storage
from ui.adapters import stage_view, storyboard_scenes, timeline_data
from ui.widgets import btn, html, stretch, timeline_video_row

def _jump(number: int, start_s: float) -> None:
    """Timeline click: select the scene (Properties panel) and move the preview to the scene's start."""
    st.session_state["sel_scene"] = number
    st.session_state["studio_seek"] = (st.session_state.get("project"), start_s)


def _start_time(project_id: str) -> int:
    seek = st.session_state.get("studio_seek")
    if not seek or seek[0] != project_id:                    # a jump made in another project does not carry over
        return 0
    # st.video seeks in whole seconds: round up so the preview lands inside the scene, not at the end of the previous one
    return int(math.ceil(seek[1] - 1e-6))


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
            st.video(str(proj["video_path"]), start_time=_start_time(proj["id"]))
        else:
            html(C.badges([("No video file", "warn"), (str(rep.get("format", "")).title(), "accent")]))
            html(C.storyboard_preview("Storyboard preview only", "The MP4 of this project is not in outputs/videos/ (it may have been moved or "
                                      "deleted). The timeline below comes from the saved report."))
        if silent:
            html(C.alert("warn", "This video has no sound", "It was made with the silent engine. Create it again with a system or Edge voice to hear the narration."))
        ai_img, ai_notes = rep.get("ai_images"), rep.get("ai_notes") or []
        if ai_img and ai_img.get("scenes_with_image", 0) < ai_img.get("scenes_total", 0):
            errs = "; ".join(e[:160] for e in ai_img.get("errors", [])[:3]) or "no picture was returned"
            html(C.alert("warn", f"AI pictures: {ai_img.get('scenes_with_image', 0)} of {ai_img.get('scenes_total', 0)} scenes ({ai_img.get('provider', '')})",
                         _html.escape(errs) + " The other scenes are drawn by code."))
        if ai_notes:
            html(C.alert("info", "AI reader", _html.escape(" ".join(ai_notes)[:600])))

        # ---- timeline (click a scene on the Video track to jump to it)
        html(C.section("Timeline"))
        with st.container(border=True):
            timeline_video_row(tl["video"], tl["total_s"], ss["sel_scene"], on_click=_jump)
            html(C.timeline_tracks(tl["video"], tl["audio"], tl["subtitles"], tl["total_s"], selected_scene=ss["sel_scene"], silent=silent,
                                   subtitles_note="No .srt file found for this project", include_video=False, framed=False))
        st.caption("Click a scene on the Video track to jump to it in the preview and see its details on the right.")

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
