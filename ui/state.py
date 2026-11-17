"""Streamlit session state, navigation, the voice library and voice preview, shared by every screen."""
from __future__ import annotations

import importlib.util
from typing import Any, Optional

import streamlit as st

from core.config import OUTPUT_DIR
from modules.providers import edge_tts_provider as tts_engine
from modules.video.voice import FFmpegMissing, find_ffmpeg
from modules.voice_library.library import VoiceLibrary, VoiceLibraryError, VoiceProfile, builtin_library, load_library

VIDEOS_DIR = OUTPUT_DIR / "videos"

NAV = (("new", "➕", "New Project"), ("projects", "📁", "My Projects"), ("templates", "🧩", "Templates"),
       ("voices", "🎙️", "Voice Library"), ("settings", "⚙️", "Settings"))

DEFAULTS: dict[str, Any] = {
    "cfg_idea": "", "cfg_instructions": "", "cfg_reference": "", "cfg_source": "pack", "cfg_pack": None,
    "cfg_format": "INFOGRAPHIC", "cfg_duration": 90, "cfg_budget": 0, "cfg_language": "en", "cfg_speed": 1.0,
    "cfg_engine": "silent", "cfg_online": False, "cfg_burn": True, "cfg_topic_engine": True,
}


def init() -> None:
    """Defaults that must exist before any widget is drawn."""
    st.session_state.setdefault("view", "new")
    st.session_state.setdefault("current", None)          # name of the project open in the Studio
    st.session_state.setdefault("job", None)               # settings of the generation in progress
    st.session_state.setdefault("_sticky", {})


def sticky(key: str, default: Any = None) -> None:
    """Call BEFORE drawing the widget with this key. Streamlit forgets a widget's value when the widget is not
    drawn (for example while another screen is open); this brings the remembered value back."""
    if key not in st.session_state:
        st.session_state[key] = st.session_state["_sticky"].get(key, DEFAULTS.get(key, default) if default is None else default)


def stash(*keys: str) -> None:
    """Call at the end of a screen: remember the values of these widget keys."""
    store = st.session_state["_sticky"]
    for k in keys:
        if k in st.session_state:
            store[k] = st.session_state[k]


def go(view: str) -> None:
    """Button callback: open a screen."""
    st.session_state["view"] = view


def open_project(name: str) -> None:
    """Button callback: open a finished video in the Studio."""
    st.session_state["current"] = name
    st.session_state["sel_scene"] = 0
    st.session_state["view"] = "studio"


def set_value(key: str, value: Any) -> None:
    """Button callback: set a form value (runs before the next rerun, so it may set a widget's key)."""
    st.session_state[key] = value
    st.session_state["_sticky"][key] = value


# ------------------------------------------------------------------ environment
def library() -> tuple[VoiceLibrary, Optional[str]]:
    try:
        return load_library(), None
    except VoiceLibraryError as exc:                         # a broken team file must be visible
        return builtin_library(), str(exc)


def environment() -> dict:
    """What this computer can do, for validation and the Settings screen."""
    try:
        ffmpeg, ffmpeg_ok = find_ffmpeg(), True
    except FFmpegMissing:
        ffmpeg, ffmpeg_ok = "", False
    return {"ffmpeg_ok": ffmpeg_ok, "ffmpeg": ffmpeg, "edge_ok": tts_engine.is_available(),
            "system_ok": importlib.util.find_spec("pyttsx3") is not None,
            "pillow_ok": importlib.util.find_spec("PIL") is not None}


# ------------------------------------------------------------------ voice preview (one audio slot)
def play(v: VoiceProfile, speed: float) -> None:
    """Button callback-style helper: load a sample of `v` (bundled file, else live synthesis) into the audio slot."""
    try:
        with st.spinner(f"Loading {v.name}…"):
            path = tts_engine.get_preview(v, speed)
        st.session_state["preview"] = (v.voice_id, v.name, round(speed, 2), path.read_bytes())
        st.session_state.pop("preview_error", None)
    except tts_engine.TTSUnavailable as exc:
        st.session_state.pop("preview", None)
        st.session_state["preview_error"] = str(exc)


def show_player() -> None:
    if st.session_state.get("preview_error"):
        st.warning(st.session_state["preview_error"])
    elif st.session_state.get("preview"):
        _, name, spd, audio = st.session_state["preview"]
        st.caption(f"Sample: {name} at {spd:.2f}x")
        st.audio(audio, format="audio/mp3")
