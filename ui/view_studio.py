"""Video Studio: preview, properties, timeline tracks, storyboard, checks. Built from the JSON report
that `make_video` writes, so a video just made and a video opened from My Projects look the same."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from ui import components as C
from ui import state as S
from ui import studio_logic as L


def _download_row(project: L.Project, report: dict) -> None:
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇ MP4", project.video_path.read_bytes(), file_name=project.video_path.name, mime="video/mp4",
                       use_container_width=True)
    if project.srt_path:
        c2.download_button("⬇ Subtitles", project.srt_path.read_bytes(), file_name=project.srt_path.name, mime="text/plain",
                           use_container_width=True)
    c3.download_button("⬇ Report", json.dumps(report, ensure_ascii=False, indent=2), file_name=project.name + ".report.json",
                       mime="application/json", use_container_width=True)


def _properties(cards: list[dict], project: L.Project, report: dict) -> None:
    st.markdown(C.section_label("Properties"), unsafe_allow_html=True)
    idx = st.selectbox("Scene", range(len(cards)), key="sel_scene",
                       format_func=lambda i: f"Scene {cards[i]['number']} · {cards[i]['title']}")
    c = cards[idx]
    meta = project.meta
    voice = (f"{meta['voice_name']} ({meta.get('language', '')}) · speed {meta.get('speed', 1.0):g}x" if meta.get("voice_name")
             else "not recorded for this video")
    with st.container(border=True):
        st.markdown(f"**{c['title']}**")
        st.markdown(C.badge(c["mode"], "accent") + " " + C.badge(f"{c['duration_s']:.1f} s", "muted"), unsafe_allow_html=True)
        st.caption(f"Starts at {c['start_s']:.1f} s · {c['layout']}")
        st.markdown("**Narration**")
        st.write(c["narration"])
        st.markdown("**Visual**")
        st.write(c["visual"])
        st.markdown("**Voice**")
        st.caption(f"{voice}  \nengine: {report.get('voice_engine', '-')}  \n"
                   + ("audio track is silent" if report.get("voice_is_silent") else "audio track has speech"))
        st.markdown("**Claims and evidence**")
        if c["claims"]:
            st.caption(f"{', '.join(c['claims'])}: “{c['claim_texts'][0]}”  \nThe claim text is the narration; "
                       "it is not checked against external sources.")
        else:
            st.caption("No claim is linked to this scene.")
    st.caption("🔒 Read-only: editing a scene is not available yet.")


def _storyboard(cards: list[dict]) -> None:
    view = st.radio("View", ["Cards", "Table"], horizontal=True, label_visibility="collapsed", key="story_view")
    if view == "Table":
        st.dataframe(L.scene_table(cards), hide_index=True, use_container_width=True,
                     column_config={"narration": st.column_config.TextColumn("narration", width="large")})
        return
    per_row = 3
    for i in range(0, len(cards), per_row):
        for col, (j, c) in zip(st.columns(per_row), enumerate(cards[i:i + per_row], start=i)):
            with col:
                st.markdown(C.storyboard_card(c, selected=(st.session_state.get("sel_scene") == j)), unsafe_allow_html=True)
                st.button("Inspect", key=f"insp_{j}", on_click=S.set_value, args=("sel_scene", j), use_container_width=True)


def _checks(report: dict) -> None:
    rows = L.check_rows(report)
    names = {"S11": "Render modes", "S12": "Length 60–120 s", "S13": "Within 5% of target", "S15": "Labels"}
    for r in rows:
        st.markdown(C.badge("Pass" if r["passed"] else "Fail", "success" if r["passed"] else "error") +
                    f" &nbsp;**{r['id']}** · {names.get(r['id'], '')} — {r['detail']}", unsafe_allow_html=True)
    if report.get("adjustments"):
        st.markdown("**Duration adjustments**")
        for line in report["adjustments"]:
            st.caption("• " + line)
    for note in [n for n in report.get("notes", []) if "SILENT" not in n]:
        st.caption("ℹ️ " + note)


def render(projects: list[L.Project]) -> None:
    project = next((p for p in projects if p.name == st.session_state.get("current")), None)
    if project is None:
        st.markdown(C.empty_state("🎬", "No video selected", "Open a video from My Projects, or create a new one."),
                    unsafe_allow_html=True)
        st.button("➕ New Project", on_click=S.go, args=("new",), key="studio_new")
        return
    report = L.load_report(project.report_path)
    if report is None:
        st.markdown(C.error_box("This project's report cannot be read", str(project.report_path)), unsafe_allow_html=True)
        return
    cards = L.scene_cards(report)
    cues = L.parse_srt(project.srt_path.read_text(encoding="utf-8")) if project.srt_path else None
    failed = [r["id"] for r in L.check_rows(report) if not r["passed"]]

    head, act = st.columns([5, 1])
    head.markdown(C.hero(project.title, f"{report['format'].title()} video · {len(cards)} scenes"), unsafe_allow_html=True)
    act.button("➕ New Project", on_click=S.go, args=("new",), use_container_width=True, key="studio_new2")
    m = st.columns(4)
    status = ("Checks failed: " + ", ".join(failed)) if failed else "All checks passed"
    for col, (label, value, hint) in zip(m, [("Status", "Video ready", status),
                                               ("Format", report["format"].title(), "format that was built"),
                                               ("Length", f"{report['total_s']:.1f} s", f"requested {report['t_target']:.0f} s"),
                                               ("Resolution", f"{report['resolution'][0]}×{report['resolution'][1]}", f"{report['fps']} fps")]):
        col.markdown(C.metric_card(label, value, hint), unsafe_allow_html=True)

    main, side = st.columns([5, 3], gap="large")
    with main:
        st.video(str(project.video_path))
        if report.get("voice_is_silent"):
            st.markdown(C.badge("Silent audio track", "warning", "Generated with the silent engine"), unsafe_allow_html=True)
        _download_row(project, report)
    with side:
        _properties(cards, project, report)

    st.markdown(C.section_label("Timeline"), unsafe_allow_html=True)
    tracks = L.tracks_from_report(report, cues)
    st.markdown(C.timeline_tracks(tracks, float(report["total_s"])), unsafe_allow_html=True)
    st.markdown(C.track_legend([c["mode"] for c in cards]), unsafe_allow_html=True)
    st.caption("Clips come from the Timeline Assembler's result"
               + (" and the subtitle file." if cues else "; no subtitle file was found, so each scene is one subtitle clip."))

    tab_story, tab_checks = st.tabs(["🎞️ Storyboard", "✅ Checks"])
    with tab_story:
        _storyboard(cards)
    with tab_checks:
        _checks(report)
