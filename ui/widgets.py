"""Thin Streamlit wrappers: version-safe buttons, HTML output and the sidebar."""
from __future__ import annotations

import inspect
from typing import Callable, Optional

import streamlit as st

from ui import components as C
from ui import state as S
from ui import storage
from ui.adapters import short_title


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
        html(C.profile("Group 7", "Local workspace · CSC10014"))
