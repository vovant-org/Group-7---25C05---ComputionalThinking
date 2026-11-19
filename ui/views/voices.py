"""Voice Library: the voices of modules/voice_library, with the existing preview where it is available."""
from __future__ import annotations

import streamlit as st

from modules.pipeline.ui_helpers import voice_library_rows
from modules.voice_library.library import LANGUAGES
from ui import components as C
from ui import runner
from ui import state as S
from ui.widgets import btn, card_button, html, stretch


def _use(language: str, voice_id: str) -> None:
    S.put("language", language)
    st.session_state[f"voice_{language}"] = voice_id


def render() -> None:
    ss = st.session_state
    lib, err = runner.load_voices()
    html(C.heading("Voice Library", "Voices available for narration. Speaking rates marked “assumed” have not been measured yet."))
    if err:
        html(C.alert("err", "data/voice_library.json was not loaded", f"Showing built-in voices only. {err}"))
    lang = st.radio("Language", ["all"] + lib.languages(), horizontal=True, format_func=lambda k: "All" if k == "all" else LANGUAGES[k],
                    label_visibility="collapsed", key="voices_lang")
    voices = lib.list(language=None if lang == "all" else lang)
    for row in range(0, len(voices), 3):
        for col, v in zip(st.columns(3), voices[row:row + 3]):
            with col:
                chosen = ss.get(f"voice_{v.language}") == v.voice_id
                traits = [v.gender.title(), v.locale, f"{v.base_wpm:.0f} wpm " + ("measured" if v.wpm_is_measured else "assumed")]
                card_button(C.voice_card(v.name, LANGUAGES[v.language], traits, selected=chosen, note=v.notes),
                            "In use for new videos" if chosen else "Use for new videos", key=f"vl_{v.voice_id}", selected=chosen,
                            on_click=_use, args=(v.language, v.voice_id))
                if runner.preview_available(v, 1.0):
                    if st.button("▶ Preview", key=f"vlp_{v.voice_id}"):
                        audio, perr = runner.preview_audio(v, 1.0)
                        ss["preview"] = (v.voice_id, audio, perr)
                if ss.get("preview") and ss["preview"][0] == v.voice_id:
                    _, audio, perr = ss["preview"]
                    st.audio(audio, format="audio/mp3") if audio else st.warning(perr)
    if not any(runner.preview_available(v, 1.0) for v in voices):
        html(C.alert("info", "Voice previews are not available", "Install edge-tts (needs internet) or add bundled samples to assets/voice_previews/. "
                     "Previews only ever speak a fixed public sentence, never your text."))
    with st.expander("Library table"):
        st.dataframe(voice_library_rows(lib), hide_index=True, **stretch(st.dataframe))
