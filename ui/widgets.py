"""Thin Streamlit wrappers: version-safe buttons, HTML output and the sidebar."""
from __future__ import annotations

import inspect
from typing import Callable, Optional, Sequence

import streamlit as st

from ui import components as C
from ui import state as S
from ui import storage
from ui.adapters import short_title
from ui.theme import MODE_COLORS


def _supports(func: Callable, name: str) -> bool:
    try:
        return name in inspect.signature(func).parameters
    except (TypeError, ValueError):
        return False


_STRETCH_BUTTON = {"width": "stretch"} if _supports(st.button, "width") else {"use_container_width": True}
_HAS_ICON = _supports(st.button, "icon")


def stretch(func: Callable = st.button) -> dict:
    """Keyword that makes a widget fill its column, whichever Streamlit version is installed."""
    return {"width": "stretch"} if _supports(func, "width") else {"use_container_width": True}


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def rerun() -> None:
    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()


def btn(label: str, *, icon: Optional[str] = None, fill: bool = True, **kw) -> bool:
    """st.button with an optional Material icon (used only when this Streamlit version supports it)."""
    if icon and _HAS_ICON:
        kw["icon"] = f":material/{icon}:"
    if fill:
        kw.update(_STRETCH_BUTTON)
    return st.button(label, **kw)


def card_button(card_html: str, label: str, *, key: str, selected: bool = False, on_click: Optional[Callable] = None,
                args: tuple = (), disabled: bool = False, help: Optional[str] = None) -> bool:
    """A card (HTML) with its action button underneath; the button is primary when the card is selected."""
    html(card_html)
    return btn(("✓ " if selected else "") + label, key=key, type="primary" if selected else "secondary",
               on_click=on_click, args=args, disabled=disabled, help=help)


# The innermost columns block that holds the Video-row marker (outer layout columns also contain it, so they are excluded).
_TLV = ('div[data-testid="stHorizontalBlock"]:has(.sf-tlv-mark)'
        ':not(:has(div[data-testid="stHorizontalBlock"] .sf-tlv-mark))')


def timeline_video_row(video: Sequence[dict], total_s: float, selected_scene: Optional[int],
                       on_click: Callable, key_prefix: str = "tl_scene") -> None:
    """The timeline's Video track drawn as one button per scene; clicking calls on_click(scene_number, start_s).

    Each button's width follows the scene's real length, and idle time between clips is kept as an empty spacer, so the
    row lines up with the Audio/Subtitles tracks drawn underneath by components.timeline_tracks(include_video=False)."""
    if not video:
        html(C.h('<div class="sf-tl-row">', C.timeline_label("Video", "video"),
                 '<div class="sf-tl-track"><div class="sf-card-text" style="padding:.55rem .8rem;margin:0">No video clips</div></div></div>'))
        return
    total = max(total_s, max(c["end_s"] for c in video), 0.001)
    clips = sorted(video, key=lambda c: c["start_s"])
    spec, items, t = [total * 0.09], [], 0.0                  # first column: the "Video" label (fixed width in CSS)
    for c in clips:
        if c["start_s"] - t > 0.05:                           # a gap in the real timeline: keep it as empty space
            spec.append(c["start_s"] - t)
            items.append(None)
        spec.append(max(c["end_s"] - c["start_s"], 0.05))
        items.append(c)
        t = max(t, c["end_s"])
    if total - t > 0.05:
        spec.append(total - t)
        items.append(None)

    # per-column colours (mode colour of each scene); nth-child counts the label column as 1
    css = [f'{_TLV}>div:nth-child({i + 2}) button{{background:{MODE_COLORS.get(c["mode"], "#64748B")}!important}}'
           for i, c in enumerate(items) if c is not None]
    html("<style>" + "".join(css) + "</style>")
    cols = st.columns(spec)
    with cols[0]:
        html(C.timeline_label("Video", "video", "sf-tlv-mark"))
    for col, c in zip(cols[1:], items):
        if c is None:
            continue
        with col:
            sel = c["scene"] == selected_scene
            btn(str(c["scene"]), key=f"{key_prefix}_{c['scene']}", type="primary" if sel else "secondary",
                help="Scene %s: %.1f-%.1f s, %s. Click to jump to this scene." % (c["scene"], c["start_s"], c["end_s"], c["mode"]),
                on_click=on_click, args=(c["scene"], float(c["start_s"])))


def split_marker() -> None:
    """Marks a columns block so the CSS can stack its columns on tablets."""
    html('<span class="sf-split"></span>')


def sidebar() -> None:
    view = st.session_state["view"]
    with st.sidebar:
        html(C.brand())
        btn("New Project", icon="add", key="nav_create", on_click=S.goto, args=("create",),
            type="primary" if view in ("create", "generate") else "secondary")
        btn("My Projects", icon="folder_open", key="nav_projects", on_click=S.goto, args=("projects",),
            type="primary" if view == "projects" else "secondary")
        btn("Templates", icon="space_dashboard", key="nav_templates", on_click=S.goto, args=("templates",),
            type="primary" if view == "templates" else "secondary")
        btn("Voice Library", icon="record_voice_over", key="nav_voices", on_click=S.goto, args=("voices",),
            type="primary" if view == "voices" else "secondary")
        btn("Settings", icon="settings", key="nav_settings", on_click=S.goto, args=("settings",),
            type="primary" if view == "settings" else "secondary")
        html(C.side_label("Recent projects"))
        recent = storage.list_projects()[:3]
        if not recent:
            html(C.side_empty("No videos yet. Your finished videos appear here."))
        for p in recent:
            current = view == "studio" and st.session_state.get("project") == p["id"]
            btn(short_title(p["title"], 30), icon="movie", key=f"recent_{p['id']}", on_click=S.open_project, args=(p["id"],),
                type="primary" if current else "secondary", help=p["title"])
        html(C.side_label("Appearance"))
        st.radio("Theme", ["dark", "light"], key=S.seed("theme"), on_change=S.sync, args=("theme",), horizontal=True,
                 label_visibility="collapsed", format_func=lambda m: {"dark": "🌙 Dark", "light": "☀️ Light"}[m])
        html(C.profile("Group 7", "Local workspace · CSC10014"))
