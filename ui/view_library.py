"""My Projects, Templates, Voice Library and Settings screens."""
from __future__ import annotations

import time

import streamlit as st

from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, pack_language, topic_keys
from modules.pipeline.ui_helpers import voice_caption, voice_library_rows
from modules.providers import edge_tts_provider as tts_engine
from modules.voice_library.library import LANGUAGES, VoiceLibrary
from ui import components as C
from ui import state as S
from ui import studio_logic as L


# ------------------------------------------------------------------ My Projects
def projects(items: list[L.Project]) -> None:
    st.markdown(C.hero("My Projects", "Videos you made on this computer."), unsafe_allow_html=True)
    if not items:
        st.markdown(C.empty_state("📁", "No projects yet",
                                  "Create your first video. Finished videos are saved in outputs/videos and listed here."),
                    unsafe_allow_html=True)
        st.button("➕ New Project", on_click=S.go, args=("new",), key="empty_new", type="primary")
        return
    per_row = 3
    for i in range(0, len(items), per_row):
        for col, p in zip(st.columns(per_row), items[i:i + per_row]):
            with col:
                when = time.strftime("%d %b %Y, %H:%M", time.localtime(p.modified))
                st.markdown(
                    f'<div class="sf-card"><div class="sf-title">{C._e(p.title)}</div><div style="margin:6px 0">'
                    f'{C.badge(p.fmt.title() or "Video", "accent")} {C.badge(f"{p.total_s:.0f} s", "muted")} '
                    f'{C.badge(f"{p.scenes} scenes", "muted")}</div><div class="sf-sub">{C._e(when)}</div></div>',
                    unsafe_allow_html=True)
                st.button("Open in Studio", key=f"open_{p.name}", on_click=S.open_project, args=(p.name,),
                          use_container_width=True)


# ------------------------------------------------------------------ Templates
def _use_template(key: str) -> None:
    S.set_value("cfg_idea", TOPIC_LABELS[key])
    S.set_value("cfg_source", "pack")
    S.set_value("cfg_pack", key)
    S.set_value("cfg_language", pack_language(key))
    S.set_value("cfg_format", "INFOGRAPHIC")
    S.go("new")


def templates() -> None:
    st.markdown(C.hero("Templates", "Start from a ready-made set of claims."), unsafe_allow_html=True)
    st.caption("These are hand-written demo claim packs, standing in for the research step that is not built yet. "
               "They are not verified research.")
    keys = topic_keys()
    for i in range(0, len(keys), 2):
        for col, key in zip(st.columns(2), keys[i:i + 2]):
            with col:
                lang = pack_language(key)
                st.markdown(
                    f'<div class="sf-card"><div class="sf-row"><div class="sf-icon">🧩</div><div>'
                    f'<div class="sf-title" style="margin:0">{C._e(TOPIC_LABELS[key])}</div>'
                    f'<div class="sf-sub">{len(get_sample_claims(key))} claims · {C._e(LANGUAGES[lang])}</div></div></div></div>',
                    unsafe_allow_html=True)
                st.button("Use this template", key=f"tpl_{key}", on_click=_use_template, args=(key,), use_container_width=True)


# ------------------------------------------------------------------ Voice Library
def _use_voice(lang: str, voice_id: str) -> None:
    S.set_value(f"cfg_voice_{lang}", voice_id)
    S.set_value("cfg_language", lang)


def voices(lib: VoiceLibrary, lib_error) -> None:
    st.markdown(C.hero("Voice Library", "Listen, then choose the voice for your next video."), unsafe_allow_html=True)
    if lib_error:
        st.error(f"data/voice_library.json was not loaded, built-in voices only: {lib_error}")
    player = st.container()
    langs = lib.languages()
    for tab, lang in zip(st.tabs([LANGUAGES[l] for l in langs]), langs):
        with tab:
            vs = lib.list(language=lang)
            for i in range(0, len(vs), 2):
                for col, v in zip(st.columns(2), vs[i:i + 2]):
                    with col:
                        st.markdown(C.voice_card(v.name, LANGUAGES[v.language], f"{v.gender}, {v.locale}",
                                                 rate_note=voice_caption(v, 1.0)), unsafe_allow_html=True)
                        b1, b2 = st.columns(2)
                        if tts_engine.can_preview(v, 1.0):
                            if b1.button("▶ Preview", key=f"lib_play_{v.voice_id}", use_container_width=True):
                                S.play(v, 1.0)
                        else:
                            b1.button("▶ Preview", key=f"lib_play_{v.voice_id}", use_container_width=True, disabled=True,
                                      help="Needs a bundled sample or `pip install edge-tts` with internet.")
                        b2.button("Use for new projects", key=f"lib_use_{v.voice_id}", on_click=_use_voice,
                                  args=(lang, v.voice_id), use_container_width=True)
    with player:
        S.show_player()
    if not any(tts_engine.can_preview(v, 1.0) for v in lib):
        st.info("No samples can be played yet. Run `pip install edge-tts` (needs internet), or have a teammate run "
                "`python -m modules.voice_library.cli --make-previews` and commit `assets/voice_previews/`.")
    with st.expander("All voices (table)"):
        st.dataframe(voice_library_rows(lib), hide_index=True, use_container_width=True)
        st.caption("Add voices or measured speaking rates in data/voice_library.json (see docs/voice-library.md). "
                   "Speaking rates are assumed until a voice has been measured.")


# ------------------------------------------------------------------ Settings
def _reset_form() -> None:
    for k in list(S.DEFAULTS) + [k for k in st.session_state if str(k).startswith("cfg_voice_")]:
        st.session_state.pop(k, None)
    st.session_state["_sticky"].clear()


def settings() -> None:
    env = S.environment()
    st.markdown(C.hero("Settings", "What this computer can do, and what is not built yet."), unsafe_allow_html=True)
    rows = [("FFmpeg", env["ffmpeg_ok"], env["ffmpeg"] or "pip install imageio-ffmpeg", True),
            ("Pillow (drawing)", env["pillow_ok"], "pip install Pillow", True),
            ("edge-tts (online voices and live preview)", env["edge_ok"], "pip install edge-tts", False),
            ("pyttsx3 (offline system voice)", env["system_ok"], "pip install pyttsx3", False)]
    for name, ok, detail, needed in rows:
        kind = "success" if ok else ("error" if needed else "muted")
        st.markdown(C.badge("Ready" if ok else ("Missing" if needed else "Optional, not installed"), kind) +
                    f" &nbsp;**{name}** <span class='sf-sub'>· {C._e(detail)}</span>", unsafe_allow_html=True)
    st.caption(f"Videos are written to {S.VIDEOS_DIR}")
    st.button("Reset the form to defaults", on_click=_reset_form, key="reset_form")

    st.markdown(C.section_label("Feature status"), unsafe_allow_html=True)
    a, b, c = st.columns(3)
    with a:
        st.markdown(C.badge("Working", "success"), unsafe_allow_html=True)
        st.markdown("- Router, Scene Segmenter, Budget Optimizer, Voice Segmenter, Timeline Assembler\n"
                    "- Infographic video (MP4, subtitles)\n- Animation video (cut-out, MP4)\n- Voice library, English and Vietnamese\n"
                    "- Cost estimate before generation")
    with b:
        st.markdown(C.badge("Simulated or assumed", "warning"), unsafe_allow_html=True)
        st.markdown("- Claims: demo packs or an extractive heuristic, not verified research\n"
                    "- Credit cost per render mode is an assumption\n- Speaking rates are assumed until measured\n"
                    "- The silent engine has no sound")
    with c:
        st.markdown(C.badge("Not built yet", "muted"), unsafe_allow_html=True)
        st.markdown("- Hybrid format\n- AI video clips (CLIP mode)\n- Editing scenes in the Studio\n"
                    "- PDF and Word reference files\n- Accounts and cloud projects")
