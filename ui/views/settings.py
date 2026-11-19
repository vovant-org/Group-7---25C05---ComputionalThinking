"""Settings: environment status, developer tools and an honest list of what is not built."""
from __future__ import annotations

import streamlit as st

from ui import components as C
from ui import runner, storage
from ui.widgets import html

NOT_BUILT = [
    ("Researching a topic", "The REASON step is not built. Content comes from a demo template or from your own text (sentences of 8–24 words)."),
    ("Hybrid format", "The Router accepts it but the video maker stops with a message, so the card is disabled."),
    ("AI image-to-video clips (CLIP)", "No provider is connected, so animation scenes are LAYERED cut-outs drawn by code."),
    ("Measured speaking rates", "Voice speeds are assumed until measured (evaluation/measure_tts.py)."),
    ("Credits", "Per-render-mode costs are assumptions; credits are a planning budget, not money."),
    ("Scene editing, accounts, cloud projects", "Not part of the backend. Projects are files in outputs/videos/."),
]


def _status(label: str, ok: bool, yes: str, no: str) -> str:
    return C.alert("ok" if ok else "warn", f"{label}: {yes if ok else no}")


def render() -> None:
    html(C.heading("Settings", "Environment, developer tools and project limits."))
    html(C.section("Environment"))
    html(_status("FFmpeg", runner.ffmpeg_ok(), "found", "not found (pip install -r requirements-video.txt)"))
    html(_status("System voice (pyttsx3)", runner.system_voice_installed(), "installed", "not installed, optional"))
    html(_status("Edge neural voices (edge-tts)", runner.edge_installed(), "installed", "not installed, optional (needs internet)"))
    st.caption(f"Videos and project files are saved in: {storage.videos_dir()}")

    html(C.section("Developer tools"))
    st.caption("Original pages of the project, kept as they were: algorithm comparison with simulated TTS and the benchmark evidence.")
    for path, label in (("pages/2_Pipeline_lab.py", "Pipeline lab · algorithms, simulated TTS, benchmark evidence"),
                        ("pages/1_Make_video.py", "Classic video maker")):
        try:
            st.page_link(path, label=label)
        except Exception:                                   # old Streamlit without page_link: say where it is
            st.caption(f"{label}: open `{path}` from the URL (/{path.split('/')[-1].rsplit('.', 1)[0].split('_', 1)[-1]})")

    html(C.section("Not built yet / simulated"))
    for title, text in NOT_BUILT:
        html(C.alert("info", title, text))
