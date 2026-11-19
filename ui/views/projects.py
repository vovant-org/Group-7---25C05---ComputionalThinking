"""My Projects: every rendered video found in outputs/videos/."""
from __future__ import annotations

import streamlit as st

from ui import components as C
from ui import state as S
from ui import storage
from ui.adapters import humanize_age
from ui.widgets import btn, card_button, html


def render() -> None:
    html(C.heading("My Projects", "Videos rendered on this computer (outputs/videos/)."))
    items = storage.list_projects()
    if not items:
        html(C.empty_state("No projects yet", "Create your first video and it will appear here.", "folder"))
        btn("New Project", key="proj_new", type="primary", on_click=S.goto, args=("create",), fill=False)
        return
    formats = ["All formats"] + sorted({i["format"].title() for i in items if i["format"]})
    st.selectbox("Filter", formats, key=S.seed("project_filter"), on_change=S.sync, args=("project_filter",), label_visibility="collapsed")
    if st.session_state["project_filter"] != "All formats":
        items = [i for i in items if i["format"].title() == st.session_state["project_filter"]]
    html(C.badge(f"{len(items)} project" + ("" if len(items) == 1 else "s"), "neutral"))
    for row in range(0, len(items), 3):
        for col, p in zip(st.columns(3), items[row:row + 3]):
            with col:
                status, kind = ("Checks passed", "ok") if p["checks"] and p["checks"][0] == p["checks"][1] else \
                               (("Check failed", "err") if p["checks"] else ("No checks", "neutral"))
                if not p["has_video"]:
                    status, kind = "No video file", "warn"
                sub = f'{p["scenes"]} scenes · voice: {p["voice"]}' if p["voice"] else f'{p["scenes"]} scenes'
                card_button(C.project_card(p["title"], p["format"], p["total_s"], humanize_age(p["mtime"]), status, kind, sub), "Open",
                            key=f"open_{p['id']}", on_click=S.open_project, args=(p["id"],))
