"""Session state: defaults, navigation and the "keep what the user typed" helpers.

Streamlit forgets a widget's value when the widget is not drawn in a run (for example after the user
opens another screen). So every setting lives in a plain key (`topic`), and the widget uses the key
`w_topic`, seeded from the plain key and copied back on change.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

VIEWS = ("create", "generate", "studio", "projects", "templates", "voices", "settings")

DEFAULTS: dict[str, Any] = {
    "view": "create", "theme": "dark", "step": 1, "quality": "standard", "topic": "", "instructions": "", "reference": "", "upload_name": "", "upload_error": "", "upload_n": 0,
    "source": "text", "pack": "sleep", "language": "en", "fmt": "INFOGRAPHIC", "duration": 90, "auto_budget": True, "budget": 100,
    "speed": 1.0, "engine": None, "allow_online": False, "subtitles": "burn", "topic_aware": True,
    "ai_read": "off", "ai_image": "off", "ai_online": False, "ai_folder": "",
    "voice_en": None, "voice_vi": None, "project": None, "sel_scene": None, "board_view": "Cards",
    "job": None, "gen_state": "idle", "last_outcome": None, "project_filter": "All formats", "preview": None,
}


def init(default_engine: str) -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    if st.session_state["engine"] is None:
        st.session_state["engine"] = default_engine


def get(key: str) -> Any:
    return st.session_state[key]


def put(key: str, value: Any) -> None:
    """Set a setting and its widget copy (safe inside a callback)."""
    st.session_state[key] = value
    st.session_state["w_" + key] = value


def seed(key: str) -> str:
    """Call right before drawing the widget `w_<key>`: restores its value from the plain key."""
    wkey = "w_" + key
    if wkey not in st.session_state:
        st.session_state[wkey] = st.session_state[key]
    return wkey


def sync(key: str) -> None:
    """on_change callback of the widget `w_<key>`."""
    st.session_state[key] = st.session_state["w_" + key]


def goto(view: str, **values: Any) -> None:
    """Callback: switch screen (and optionally set settings first)."""
    for k, v in values.items():
        put(k, v) if k in DEFAULTS and k not in ("project", "sel_scene", "step") else st.session_state.__setitem__(k, v)
    if view == "create" and "step" not in values:        # a new project always starts at the first step
        st.session_state["step"] = 1
    st.session_state["view"] = view


def open_project(project_id: str) -> None:
    st.session_state["project"] = project_id
    st.session_state["sel_scene"] = None
    st.session_state["view"] = "studio"
