"""New Project screen: prompt composer (left) and configuration panel (right)."""
from __future__ import annotations

import streamlit as st

from modules.voice_library.library import LANGUAGES
from ui import components as C
from ui import runner
from ui import state as S
from ui.adapters import MAX_WORDS, count_words, estimate_from_facts, has_blocking, validate_inputs
from ui.widgets import btn, card_button, html, split_marker, stretch

EXAMPLES = [  # (prompt, hint): these only fill the topic box. The backend cannot research a topic by itself yet.
    ("Explain Artificial Intelligence", "Needs your reference text"),
    ("Create a video about Climate Change", "Needs your reference text"),
    ("Explain How the Internet Works", "Needs your reference text"),
    ("Introduce the History of Computer Science", "Needs your reference text"),
]

FORMATS = [
    ("INFOGRAPHIC", "Infographic", "infographic", "Data-driven visuals.", ["Charts, icons, diagrams and text", "Text and numbers drawn by code"], True, ""),
    ("ANIMATION", "Animation", "animation", "Animated storytelling.", ["Motion graphics and scene transitions", "Cut-out character with keyframes"], True, ""),
    ("HYBRID", "Hybrid", "hybrid", "Infographic and animation combined.", ["Not built in the backend yet"], False,
     "The pipeline stops with a message for this format, so it cannot be selected."),
]


# ------------------------------------------------------------------------------------------ callbacks
def _use_example(prompt: str) -> None:
    S.put("topic", prompt)
    S.put("source", "text")          # no demo pack exists for these topics: the user must supply the material


def _use_demo(pack: str, label: str, language: str) -> None:
    S.put("topic", label)
    S.put("source", "demo")
    S.put("pack", pack)
    S.put("language", language)


def _pick(key: str, value) -> None:
    S.put(key, value)


def _pick_voice(language: str, voice_id: str) -> None:
    st.session_state[f"voice_{language}"] = voice_id


def _on_upload() -> None:
    f = st.session_state.get(f"w_upload_{st.session_state['upload_n']}")
    if f is None:
        return
    try:
        text = f.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError:
        st.session_state["upload_error"] = f"{f.name} is not UTF-8 text. Save it as plain text (.txt or .md) and try again."
        return
    st.session_state["upload_error"] = ""
    st.session_state["upload_name"] = f.name
    S.put("reference", text)
    S.put("source", "text")


def _clear_upload() -> None:
    st.session_state["upload_n"] += 1
    st.session_state["upload_name"] = ""
    st.session_state["upload_error"] = ""
    S.put("reference", "")


def _start() -> None:
    ss = st.session_state
    lang = ss["language"]
    ss["job"] = runner.GenParams(
        topic=ss["topic"], instructions=ss["instructions"], reference=ss["reference"], source=ss["source"],
        pack=ss["pack"] if ss["source"] == "demo" else None, fmt=ss["fmt"], t_target=int(ss["duration"]),
        budget=None if ss["auto_budget"] else int(ss["budget"]), voice_id=ss[f"voice_{lang}"], speed=float(ss["speed"]),
        engine_kind=ss["engine"], allow_online=bool(ss["allow_online"]), subtitles=ss["subtitles"],
        topic_aware=bool(ss["topic_aware"]), language=lang)
    ss["gen_state"] = "running"
    ss["last_outcome"] = None
    ss["view"] = "generate"


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_estimate(*args):
    return runner.estimate_plan(*args)


# ----------------------------------------------------------------------------------------------- view
def render() -> None:
    ss = st.session_state
    lib, lib_error = runner.load_voices()
    languages = lib.languages()
    if ss["language"] not in languages:
        S.put("language", languages[0])
    lang = ss["language"]
    voices = lib.list(language=lang)
    for L in languages:                                                   # a valid default voice per language
        if ss.get(f"voice_{L}") not in [v.voice_id for v in lib.list(language=L)]:
            ss[f"voice_{L}"] = lib.default(L).voice_id
    packs = [t for t in runner.demo_templates() if t["language"] == lang]
    if ss["pack"] not in [t["key"] for t in packs] and packs:
        S.put("pack", packs[0]["key"])

    html(C.hero("What would you like to create today?", "Transform your ideas into engaging visual stories."))
    main, panel = st.columns([2.1, 1], gap="large")

    # ===================================================================== A. prompt composer
    with main:
        split_marker()
        with st.container(border=True):
            html(C.heading("Your idea", "Describe the topic. StoryFrame builds the story from the material you give it."))
            st.text_area("Topic or idea", key=S.seed("topic"), on_change=S.sync, args=("topic",), height=120, label_visibility="collapsed",
                         placeholder="e.g. Explain how inflation works and why prices keep rising…")
            c1, c2 = st.columns([1, 1])
            c1.radio("Content source", ["demo", "text"], key=S.seed("source"), on_change=S.sync, args=("source",), horizontal=True,
                     format_func=lambda k: {"demo": "Demo template", "text": "My reference material"}[k],
                     help="Demo template: a hand-written set of claims shipped with the project. My reference material: sentences "
                          "(8–24 words each) are extracted from your text; nothing is fact-checked.")
            if ss["source"] == "demo":
                c2.selectbox("Template", [t["key"] for t in packs], key=S.seed("pack"), on_change=S.sync, args=("pack",),
                             format_func=lambda k: next(t["label"] for t in packs if t["key"] == k) + f" · {LANGUAGES[lang]}")
            else:
                html(C.badge("Own text", "info"))
            if ss["source"] == "text":
                st.file_uploader("Upload reference material (.txt or .md)", type=["txt", "md"], key=f"w_upload_{ss['upload_n']}",
                                 on_change=_on_upload, help="Plain text only. The text is read in your browser session and never leaves this computer.")
                if ss["upload_name"]:
                    u1, u2 = st.columns([4, 1])
                    u1.caption(f"Loaded: {ss['upload_name']}")
                    u2.button("Remove", key="rm_upload", on_click=_clear_upload)
                st.text_area("Reference material", key=S.seed("reference"), on_change=S.sync, args=("reference",), height=170,
                             placeholder="Paste the text the video should be based on. Use full sentences of 8–24 words.")
            with st.expander("Additional instructions (optional)"):
                st.caption("Added to the topic. The Router reads format, duration and budget hints from it and the visual engine uses it "
                           "to recognise the subject. It is not a free-form AI prompt.")
                st.text_area("Additional instructions", key=S.seed("instructions"), on_change=S.sync, args=("instructions",), height=80,
                             label_visibility="collapsed", placeholder="e.g. keep a friendly tone, focus on everyday examples")
            words = count_words(ss["topic"]) + count_words(ss["instructions"]) + (count_words(ss["reference"]) if ss["source"] == "text" else 0)
            over = words > MAX_WORDS
            st.markdown(f"<div style='text-align:right;font-size:.78rem;color:{'#F87171' if over else '#94A3B8'}'>"
                        f"{words:,} / {MAX_WORDS:,} words</div>", unsafe_allow_html=True)

        html(C.section("Try an example"))
        cols = st.columns(len(EXAMPLES))
        for i, (col, (prompt, hint)) in enumerate(zip(cols, EXAMPLES)):
            with col:
                card_button(C.example_card(prompt, hint), "Use", key=f"ex_{i}", on_click=_use_example, args=(prompt,))
        demos = runner.demo_templates()
        html(C.section("Or start from a demo that works out of the box"))
        dcols = st.columns(len(demos))
        for i, (col, t) in enumerate(zip(dcols, demos)):
            with col:
                card_button(C.example_card(t["label"], f"{LANGUAGES[t['language']]} · {t['claims']} claims", "sparkle"), "Use template",
                            key=f"demo_{t['key']}", on_click=_use_demo, args=(t["key"], t["label"], t["language"]))

    # ===================================================================== C. configuration panel
    with panel:
        html(C.heading("Video format", "Choose how the story is presented."))
        for key, title, ico, text, bullets, available, note in FORMATS:
            card_button(C.format_card(title, text, bullets, ico, selected=ss["fmt"] == key, available=available, note=note),
                        "Selected" if ss["fmt"] == key else f"Choose {title}", key=f"fmt_{key}", selected=ss["fmt"] == key,
                        on_click=_pick, args=("fmt", key), disabled=not available)

        t_set, t_voice = st.tabs(["Settings", "Voice"])
        with t_set:
            st.slider("Duration (seconds)", 60, 120, key=S.seed("duration"), on_change=S.sync, args=("duration",), step=5,
                      help="The video must last 60–120 s (checks S12/S13). The result is allowed to miss the target by at most 5 %.")
            b1, b2 = st.columns([1, 1])
            b1.checkbox("Automatic budget", key=S.seed("auto_budget"), on_change=S.sync, args=("auto_budget",),
                        help="Automatic = twice the cheapest feasible plan. Credits are the project's assumed per-render-mode costs, not money.")
            b2.number_input("Budget (credits)", 1, 1000, key=S.seed("budget"), on_change=S.sync, args=("budget",), step=1,
                            disabled=bool(ss["auto_budget"]), label_visibility="collapsed")
            st.radio("Narration language", languages, key=S.seed("language"), on_change=S.sync, args=("language",), horizontal=True,
                     format_func=LANGUAGES.get, help="Chooses the voices on offer. The voice must speak the language of the content.")

            st.radio("Subtitles", list(runner.SUBTITLE_MODES), key=S.seed("subtitles"), on_change=S.sync, args=("subtitles",), horizontal=True,
                     format_func=runner.SUBTITLE_MODES.get, help="\n".join(f"{runner.SUBTITLE_MODES[k]}: {v}" for k, v in runner.SUBTITLE_HELP.items()))

            with st.expander("Advanced settings"):
                st.checkbox("Topic-aware visuals (animation)", key=S.seed("topic_aware"), on_change=S.sync, args=("topic_aware",),
                            help="Animation only. On: objects and motion follow the topic. Off: the generic stick figure with six standard props.")
                st.caption("Router, claim-selection, optimizer and voice-segmenter algorithms are compared in the Pipeline Lab (Settings → Developer tools). "
                           "The video maker uses the project defaults.")

        with t_voice:
            if lib_error:
                html(C.alert("err", "Voice library file not loaded", f"Built-in voices only. {lib_error}"))
            current = ss[f"voice_{lang}"]
            vcols = st.columns(2)
            for i, v in enumerate(voices):
                with vcols[i % 2]:
                    traits = [v.gender.title(), v.locale, f"{v.base_wpm:.0f} wpm " + ("measured" if v.wpm_is_measured else "assumed")]
                    card_button(C.voice_card(v.name, LANGUAGES[v.language], traits, selected=v.voice_id == current, note=v.notes),
                                "Selected" if v.voice_id == current else "Select", key=f"voice_{v.voice_id}", selected=v.voice_id == current,
                                on_click=_pick_voice, args=(lang, v.voice_id))
                    if runner.preview_available(v, float(ss["speed"])):
                        if st.button("▶ Preview", key=f"prev_{v.voice_id}"):
                            audio, err = runner.preview_audio(v, float(ss["speed"]))
                            ss["preview"] = (v.voice_id, audio, err)
            if ss["preview"] and ss["preview"][0] in [v.voice_id for v in voices]:
                _, audio, err = ss["preview"]
                st.audio(audio, format="audio/mp3") if audio else st.warning(err)
            st.slider("Speaking speed", 0.75, 1.25, key=S.seed("speed"), on_change=S.sync, args=("speed",), step=0.05, format="%.2fx",
                      help="1.00x is the voice's normal pace. The planner sizes the script for this speed.")
            st.radio("Voice engine", list(runner.ENGINES), key=S.seed("engine"), on_change=S.sync, args=("engine",), horizontal=True,
                     format_func=runner.engine_label,
                     help="\n".join(f"{runner.ENGINES[k]}: {v}" for k, v in runner.ENGINE_HELP.items()))
            if ss["engine"] == "system" and not runner.system_voice_installed():
                html(C.alert("warn", "pyttsx3 is not installed", "Run  pip install pyttsx3  or choose another engine."))
            if ss["engine"] == "edge":
                if not runner.edge_installed():
                    html(C.alert("warn", "edge-tts is not installed", "Run  pip install edge-tts  or choose another engine."))
                st.checkbox("I understand the narration text is sent to an online service", key=S.seed("allow_online"), on_change=S.sync,
                            args=("allow_online",), help="Do not send private or sensitive text (report R7 / AI tool policy).")
        # ---- validation + estimate
        claims = runner.build_claims(ss["source"], ss["pack"], ss["reference"])
        ctexts = [c.text for c in claims]
        msgs = validate_inputs(topic=ss["topic"], instructions=ss["instructions"], reference=ss["reference"] if ss["source"] == "text" else "",
                               source=ss["source"], claims_text=ctexts, voice_language=lang, ffmpeg_ok=runner.ffmpeg_ok(),
                               upload_error=ss["upload_error"], online_ok=bool(ss["allow_online"]), engine_kind=ss["engine"],
                               detected_language=runner.claims_language(claims))
        facts = None
        if ss["topic"].strip() and claims:
            facts = _cached_estimate(ss["topic"], ss["instructions"], ss["reference"], ss["source"], ss["pack"], ss["fmt"], int(ss["duration"]),
                                     None if ss["auto_budget"] else int(ss["budget"]), ss[f"voice_{lang}"], float(ss["speed"]))
        est = estimate_from_facts(facts)
        html(C.section("Cost estimate"))
        html(C.budget_card(est))

    # ===================================================================== action (under the composer)
    with main:
        for m in msgs:
            html(C.alert({"err": "err", "warn": "warn", "info": "info"}[m["level"]], m["title"], m["text"]))
        blocked = has_blocking(msgs) or not est.get("can_start")
        why = "Fix the messages above first." if has_blocking(msgs) else ("Resolve the cost estimate message first." if not est.get("can_start") else None)
        btn("Create Video", icon="play_arrow", key="create_video", type="primary", on_click=_start, disabled=blocked, help=why)
        st.caption("Takes about 30–60 s for a 90 s video. Nothing is spent: credits are an internal planning budget.")
