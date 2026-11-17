"""New Project screen: prompt composer (left) and configuration panel (right)."""
from __future__ import annotations

import json

import streamlit as st

from modules.pipeline.sample_claims import TOPIC_LABELS, pack_language, topic_keys
from modules.providers import edge_tts_provider as tts_engine
from modules.voice_library.library import LANGUAGES, SPEED_MAX, SPEED_MIN, VoiceLibrary
from ui import components as C
from ui import state as S
from ui import studio_logic as L

KEYS = ("cfg_idea", "cfg_instructions", "cfg_reference", "cfg_source", "cfg_pack", "cfg_format", "cfg_duration",
        "cfg_budget", "cfg_language", "cfg_speed", "cfg_engine", "cfg_online", "cfg_burn", "cfg_topic_engine")


def selected_voice(lib: VoiceLibrary, language: str):
    """The voice picked for this language (a card's Select button), else the library default."""
    key = f"cfg_voice_{language}"
    wanted = st.session_state.get(key) or st.session_state["_sticky"].get(key)
    return lib.get(wanted) if wanted in lib else lib.default(language)


def snapshot(lib: VoiceLibrary) -> dict:
    """The form as it is NOW, copied out of the widget state, so the generation screen does not depend on widgets
    that Streamlit forgets as soon as another screen is shown."""
    ss = st.session_state
    language = ss["cfg_language"]
    voice = selected_voice(lib, language)
    claims, _ = L.resolve_claims(ss["cfg_source"], ss.get("cfg_pack"), ss["cfg_reference"])
    request_text = L.compose_request(ss["cfg_idea"], ss["cfg_format"], ss["cfg_duration"], language, ss["cfg_instructions"])
    key = json.dumps([request_text, ss["cfg_format"], ss["cfg_duration"], ss["cfg_budget"], voice.voice_id, ss["cfg_speed"],
                      ss["cfg_engine"], ss["cfg_burn"], ss["cfg_topic_engine"], ss["cfg_source"], ss.get("cfg_pack"),
                      ss["cfg_reference"]], ensure_ascii=False)
    return {"state": "queued", "idea": ss["cfg_idea"].strip(), "request": request_text, "fmt": ss["cfg_format"],
            "duration": int(ss["cfg_duration"]), "budget": int(ss["cfg_budget"]) or None, "voice": voice,
            "speed": float(ss["cfg_speed"]), "engine": ss["cfg_engine"], "online": bool(ss["cfg_online"]),
            "burn": bool(ss["cfg_burn"]), "topic_engine": bool(ss["cfg_topic_engine"]), "reference": ss["cfg_reference"],
            "claims": claims, "language": language, "source": ss["cfg_source"],
            "name": L.project_name(ss["cfg_idea"], ss["cfg_format"], key)}


def _use_example(title: str) -> None:
    S.set_value("cfg_idea", title)
    S.set_value("cfg_source", "reference")       # no built-in claims exist for these topics: reference material is needed


def _read_upload(file) -> str:
    if file is None:
        return ""
    raw = file.getvalue()
    for enc in ("utf-8-sig", "utf-16", "cp1258", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return ""


# ------------------------------------------------------------------ right panel
def _format_panel() -> None:
    st.markdown(C.section_label("Video format"), unsafe_allow_html=True)
    chosen = st.session_state["cfg_format"]
    for f in L.FORMATS:
        st.markdown(C.format_card(f.title, f.description, f.icon, selected=(chosen == f.key), available=f.available,
                                  note=f.note if (chosen == f.key or not f.available) else ""), unsafe_allow_html=True)
        st.button("Selected ✓" if chosen == f.key else ("Coming soon" if not f.available else "Select"),
                  key=f"fmt_{f.key}", on_click=S.set_value, args=("cfg_format", f.key), use_container_width=True,
                  disabled=(chosen == f.key or not f.available))


def _settings_panel(lib: VoiceLibrary, env: dict):
    st.markdown(C.section_label("Generation settings"), unsafe_allow_html=True)
    st.slider("Duration (seconds)", L.DURATION_MIN, L.DURATION_MAX, key="cfg_duration", step=5,
              help="The Router accepts 60 to 120 seconds. The finished video lands within 5% of this target.")
    st.number_input("Budget (credits)", 0, 1000, key="cfg_budget", step=1,
                    help="0 = automatic: twice the cheapest feasible plan. Credit costs per render mode are the team's "
                         "assumptions, not measured prices.")
    st.radio("Narration language", lib.languages(), key="cfg_language", format_func=LANGUAGES.get, horizontal=True,
             help="The voice must speak the language of the narration, so this also filters the voices below.")
    st.checkbox("Burn subtitles into the picture", key="cfg_burn",
                help="A separate .srt subtitle file is always written next to the video.")


def _voice_panel(lib: VoiceLibrary, language: str, env: dict, lib_error):
    st.markdown(C.section_label("Voice"), unsafe_allow_html=True)
    if lib_error:
        st.error(f"data/voice_library.json was not loaded, built-in voices only: {lib_error}")
    current = selected_voice(lib, language)
    speed = st.slider("Speaking speed", SPEED_MIN, SPEED_MAX, key="cfg_speed", step=0.05, format="%.2fx",
                      help="1.00x is the voice's normal pace. The planner sizes the script for this speed.")
    player = st.container()
    try:
        box = st.container(height=330)
    except TypeError:                                         # older Streamlit: no fixed-height container
        box = st.container()
    with box:
        for v in lib.list(language=language):
            st.markdown(C.voice_card(v.name, LANGUAGES[v.language], f"{v.gender}, {v.locale}",
                                     selected=(v.voice_id == current.voice_id),
                                     rate_note=f"~{v.planning_wpm(speed):.0f} words/min" + ("" if v.wpm_is_measured else " (assumed)")),
                        unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            b1.button("Selected ✓" if v.voice_id == current.voice_id else "Select", key=f"pick_{v.voice_id}",
                      on_click=S.set_value, args=(f"cfg_voice_{language}", v.voice_id), use_container_width=True,
                      disabled=(v.voice_id == current.voice_id))
            if tts_engine.can_preview(v, speed):                 # shown only when preview really works
                if b2.button("▶ Preview", key=f"prev_{v.voice_id}", use_container_width=True):
                    S.play(v, speed)
            else:
                b2.button("▶ Preview", key=f"prev_{v.voice_id}", use_container_width=True, disabled=True,
                          help="Needs a bundled sample (speed 1.00x) or `pip install edge-tts` with internet.")
    with player:
        S.show_player()
    st.selectbox("Narration engine", list(L.ENGINES), key="cfg_engine", format_func=L.ENGINES.get,
                 help="Silent preview lets you check picture and timing without any text-to-speech.")
    if st.session_state["cfg_engine"] == "edge":
        st.checkbox("I understand the narration text is sent to an online service", key="cfg_online",
                    help="Do not use private or sensitive text with an online voice (project AI-tool policy).")
        if not env["edge_ok"]:
            st.warning("edge-tts is not installed: pip install edge-tts")
    if st.session_state["cfg_engine"] == "system" and not env["system_ok"]:
        st.warning("pyttsx3 is not installed: pip install pyttsx3")
    return current, speed


# ------------------------------------------------------------------ left panel
def _composer(lib: VoiceLibrary, language: str, issues, est) -> None:
    st.markdown(C.hero("What would you like to create today?", "Transform your ideas into engaging visual stories."),
                unsafe_allow_html=True)
    with st.container(border=True):
        st.text_area("Topic or idea", key="cfg_idea", height=110, label_visibility="collapsed",
                     placeholder="Describe your video, e.g. “Explain how vaccines train the immune system”")
        words = len(st.session_state["cfg_idea"].split()) + len(st.session_state["cfg_reference"].split())
        st.caption(f"{len(st.session_state['cfg_idea'])} characters · {words:,} / {L.MAX_INPUT_WORDS:,} words in total")

        st.radio("Content", ["pack", "reference"], key="cfg_source", horizontal=True,
                 format_func={"pack": "Demo claim pack", "reference": "My reference material"}.get,
                 help="The research step that finds facts by itself is not built yet. Either use the built-in demo "
                      "claims, or give your own text: sentences of 8-24 words become the claims (not verified).")
        if st.session_state["cfg_source"] == "pack":
            st.selectbox("Claim pack", topic_keys(language), key="cfg_pack", format_func=TOPIC_LABELS.get)
            st.info("Demo content: the narration comes from this pack, not from your idea text. "
                    "The idea only names the project.", icon="ℹ️")
        else:
            st.file_uploader("Reference material", type=["txt", "md"], key="cfg_upload",
                             help="Plain text or Markdown. PDF and Word files are not read yet.")
            with st.expander("Or paste text (a loaded file is shown here and can be edited)",
                             expanded=bool(st.session_state["cfg_reference"])):
                st.text_area("Reference text", key="cfg_reference", height=170, label_visibility="collapsed",
                             placeholder="Paste the facts the video should explain. One idea per sentence works best.")
        st.text_input("Additional instructions (optional)", key="cfg_instructions",
                      placeholder="e.g. keep the tone friendly for first-year students")

    errors = L.blocking(issues)
    for i in issues:
        if i.kind == "warning":
            st.caption("ℹ️ " + i.message)
    if errors and st.session_state["cfg_idea"].strip():
        st.markdown(C.error_box("Before you can create the video", "  •  ".join(e.message for e in errors), "warning"),
                    unsafe_allow_html=True)
    elif errors:
        st.caption(errors[0].message)
    if st.button("✨  Create Video", type="primary", use_container_width=True, disabled=bool(errors), key="create"):
        st.session_state["job"] = snapshot(lib)
        S.go("generate")
        st.rerun()

    st.markdown(C.section_label("Try an idea"), unsafe_allow_html=True)
    for row in (L.EXAMPLE_PROMPTS[:2], L.EXAMPLE_PROMPTS[2:]):
        for col, (icon, title, _) in zip(st.columns(2), row):
            with col:
                st.markdown(C.example_card(icon, title, "needs reference material"), unsafe_allow_html=True)
                st.button("Use this idea", key=f"ex_{title}", on_click=_use_example, args=(title,), use_container_width=True)


def _apply_upload() -> None:
    """Copy a newly uploaded file into the reference text once (later edits of the text are kept)."""
    up = st.session_state.get("cfg_upload")
    if up is None:
        return
    ident = (up.name, up.size)
    if st.session_state.get("_upload_id") != ident:
        st.session_state["_upload_id"] = ident
        st.session_state["cfg_reference"] = _read_upload(up)


def render(lib: VoiceLibrary, lib_error) -> None:
    for k in KEYS:
        S.sticky(k)
    _apply_upload()
    env = S.environment()
    language = st.session_state["cfg_language"]
    if language not in lib.languages():
        language = st.session_state["cfg_language"] = lib.languages()[0]
    packs = topic_keys(language)                              # a pack of the chosen language, before anything reads it
    if st.session_state.get("cfg_pack") not in packs:
        st.session_state["cfg_pack"] = packs[0]
    if st.session_state["cfg_format"] not in L.FORMAT_BY_KEY or not L.FORMAT_BY_KEY[st.session_state["cfg_format"]].available:
        st.session_state["cfg_format"] = "INFOGRAPHIC"

    left, right = st.columns([5, 3], gap="large")
    with right:
        _format_panel()
        _settings_panel(lib, env)
        voice, speed = _voice_panel(lib, language, env, lib_error)
        language = st.session_state["cfg_language"]
        # estimate (the real Router + Scene Segmenter + Budget Optimizer) with the current form
        issues = L.validate_config(idea=st.session_state["cfg_idea"], fmt_key=st.session_state["cfg_format"],
                                   source=st.session_state["cfg_source"], pack=st.session_state.get("cfg_pack"),
                                   reference=st.session_state["cfg_reference"], voice=voice,
                                   engine=st.session_state["cfg_engine"], allow_online=st.session_state["cfg_online"],
                                   ffmpeg_ok=env["ffmpeg_ok"], edge_ok=env["edge_ok"], system_ok=env["system_ok"])
        claims, _ = L.resolve_claims(st.session_state["cfg_source"], st.session_state.get("cfg_pack"),
                                     st.session_state["cfg_reference"])
        est = None
        if claims and st.session_state["cfg_idea"].strip():
            request_text = L.compose_request(st.session_state["cfg_idea"], st.session_state["cfg_format"],
                                             st.session_state["cfg_duration"], language, st.session_state["cfg_instructions"])
            est = L.estimate_plan(request_text, claims, fmt_key=st.session_state["cfg_format"],
                                  duration_s=st.session_state["cfg_duration"], budget=st.session_state["cfg_budget"] or None,
                                  voice=voice, speed=float(speed), reference=st.session_state["cfg_reference"])
        st.markdown(C.section_label("Cost estimation"), unsafe_allow_html=True)
        if est is None:
            st.markdown(C.budget_card(None, None, "unknown", "Fill in the idea and content to see the estimate."),
                        unsafe_allow_html=True)
        else:
            st.markdown(C.budget_card(est.cost, est.budget, est.status, est.message, est.budget_source), unsafe_allow_html=True)
            for d in est.details:
                st.caption("ℹ️ " + d)
            if est.status == "over":
                issues.append(L.Issue("error", "The budget is too small for this plan. Raise it, or set it to 0 for automatic."))
            elif est.status == "unknown" and est.message and not L.blocking(issues):
                issues.append(L.Issue("error", est.message))
    with left:
        _composer(lib, language, issues, est)
    S.stash(*KEYS, f"cfg_voice_{language}")
