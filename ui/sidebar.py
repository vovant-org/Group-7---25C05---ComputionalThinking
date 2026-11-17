"""Left sidebar: logo, navigation, recent projects, tools, user area."""
from __future__ import annotations

import streamlit as st

from ui import components as C
from ui import state as S
from ui.studio_logic import Project


def _short(text: str, n: int = 26) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def render(projects: list[Project]) -> None:
    view = st.session_state["view"]
    with st.sidebar:
        st.markdown(C.logo(), unsafe_allow_html=True)
        for key, icon, label in S.NAV:
            active = view == key or (key == "projects" and view == "studio")
            st.button(f"{icon}  {label}", key=f"nav_{key}", on_click=S.go, args=(key,), use_container_width=True,
                      type="primary" if active else "secondary")

        st.markdown(C.section_label("Recent projects"), unsafe_allow_html=True)
        if not projects:
            st.caption("No videos yet. Your finished videos will appear here.")
        for p in projects[:3]:
            st.button(f"🎬  {_short(p.title)}", key=f"recent_{p.name}", on_click=S.open_project, args=(p.name,),
                      use_container_width=True, help=f"{p.fmt.title()} · {p.total_s:.0f} s")

        st.markdown(C.section_label("Tools"), unsafe_allow_html=True)
        if hasattr(st, "page_link"):
            st.page_link("pages/1_Make_video.py", label="Classic video maker", icon="🎥")
            st.page_link("pages/2_Pipeline_lab.py", label="Pipeline lab", icon="🧪")
        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        st.markdown(C.user_chip("Local workspace", "No accounts: everything stays on this computer"), unsafe_allow_html=True)
