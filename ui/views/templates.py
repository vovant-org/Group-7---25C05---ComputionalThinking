"""Templates: the demo claim packs that ship with the project, as one-click starting points."""
from __future__ import annotations

from modules.voice_library.library import LANGUAGES
from ui import components as C
from ui import runner
from ui import state as S
from ui.widgets import card_button, html
import streamlit as st


def _use(pack: str, label: str, language: str, fmt: str) -> None:
    S.put("topic", label)
    S.put("source", "demo")
    S.put("pack", pack)
    S.put("language", language)
    S.put("fmt", fmt)
    S.put("reference", "")
    st.session_state["step"] = 3            # content and format are already chosen: continue at the voice step
    st.session_state["view"] = "create"


def render() -> None:
    html(C.heading("Templates", "Ready-made content to try the studio without writing anything."))
    html(C.alert("info", "Demo content, not researched content",
                 "These are hand-written sets of claims that stand in for the REASON step, which is not built yet. "
                 "A template fills the topic and content for you; you can still change format, voice and length."))
    items = runner.demo_templates()
    for row in range(0, len(items), 2):
        for col, t in zip(st.columns(2), items[row:row + 2]):
            with col:
                for fmt, name, ico in (("INFOGRAPHIC", "Infographic", "infographic"), ("ANIMATION", "Animation", "animation")):
                    card_button(C.example_card(f'{t["label"]} · {name}', f'{LANGUAGES[t["language"]]} · {t["claims"]} claims', ico),
                                f"Use as {name.lower()}", key=f"tpl_{t['key']}_{fmt}", on_click=_use, args=(t["key"], t["label"], t["language"], fmt))
