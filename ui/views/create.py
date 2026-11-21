"""New Project: a four-step flow instead of one crowded form.

    1. Your question (+ optional related material)  ->  2. Format  ->  3. Voice  ->  4. Budget (+ Create)

Everything that is not one of these four answers has a sensible default and lives under
"More options" on the last step: duration, subtitles, speaking speed, voice engine, topic-aware visuals,
extra instructions. The language is not asked: it is detected from the content, and the voices offered
are the ones that speak it. The content source is not asked either: material typed or uploaded by the
user is used; otherwise a ready-made demo can be picked (the REASON step is not built yet, so a topic
alone cannot be researched).
"""
from __future__ import annotations

import streamlit as st

from modules.voice_library.language import detect_language
from modules.voice_library.library import LANGUAGES
from ui import components as C
from ui import runner
from ui import state as S
from ui.adapters import MAX_WORDS, count_words, estimate_from_facts, has_blocking, short_title, validate_inputs
from ui.widgets import btn, card_button, html, stretch

STEPS = ["Your question", "Format", "Voice", "Budget"]
LAST = len(STEPS)

FORMATS = [   # (value, title, icon, text, bullets)
    ("INFOGRAPHIC", "Infographic", "infographic", "Clear and precise, with low cost.",
     ["Charts, icons, diagrams and labels", "Text and numbers drawn by code"]),
    ("ANIMATION", "Animation", "animation", "Lively storytelling with a character.",
     ["Cut-out character with keyframe motion", "Motion that follows the topic"]),
]                                                  # HYBRID is not built in the backend, so it is not offered


# ------------------------------------------------------------------------------------------ callbacks
def _go(step: int) -> None:
    st.session_state["step"] = max(1, min(LAST, step))


def _use_demo(pack: str, label: str, language: str) -> None:
    S.put("topic", label)
    S.put("source", "demo")
    S.put("pack", pack)
    S.put("language", language)
    _clear_upload()
    S.put("source", "demo")                           # _clear_upload resets the reference only; keep the demo choice


def _use_own_material() -> None:
    S.put("source", "text")


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


# --------------------------------------------------------------------------------------------- helpers
def _setup() -> dict:
    """Detect the language from the content, keep a valid voice per language, and gather what the steps share."""
    ss = st.session_state
    lib, lib_error = runner.load_voices()
    languages = lib.languages()
    claims = runner.build_claims(ss["source"], ss["pack"], ss["reference"])
    if ss["source"] == "demo":
        detected = next((t["language"] for t in runner.demo_templates() if t["key"] == ss["pack"]), None)
    else:
        detected = runner.claims_language(claims) or detect_language(ss["topic"] + " " + ss["reference"])
    if detected in languages and detected != ss["language"]:
        S.put("language", detected)
    if ss["language"] not in languages:
        S.put("language", languages[0])
    for L in languages:
        if ss.get(f"voice_{L}") not in [v.voice_id for v in lib.list(language=L)]:
            ss[f"voice_{L}"] = lib.default(L).voice_id
    return {"lib": lib, "lib_error": lib_error, "claims": claims, "ctexts": [c.text for c in claims], "detected": detected}


def _validate(ctx: dict, *, final: bool) -> list[dict]:
    """Content problems for step 1; every problem (FFmpeg, voice engine, ...) for the last step."""
    ss = st.session_state
    kw = dict(topic=ss["topic"], instructions=ss["instructions"] if final else "",
              reference=ss["reference"] if ss["source"] == "text" else "", source=ss["source"], claims_text=ctx["ctexts"],
              voice_language=ss["language"], upload_error=ss["upload_error"], detected_language=ctx["detected"])
    if final:
        return validate_inputs(ffmpeg_ok=runner.ffmpeg_ok(), online_ok=bool(ss["allow_online"]), engine_kind=ss["engine"], **kw)
    return validate_inputs(ffmpeg_ok=True, online_ok=True, engine_kind="system", **kw)


def _alerts(msgs: list[dict]) -> None:
    for m in msgs:
        html(C.alert(m["level"], m["title"], m["text"]))


def _nav(step: int, *, next_label: str = "Continue", can_next: bool = True, why: str | None = None) -> None:
    """Back / Continue buttons under a step."""
    st.write("")
    left, right = st.columns([1, 1])
    with left:
        if step > 1:
            btn("Back", icon="arrow_back", key=f"back_{step}", on_click=_go, args=(step - 1,))
    with right:
        btn(next_label, icon="arrow_forward", key=f"next_{step}", type="primary", on_click=_go, args=(step + 1,),
            disabled=not can_next, help=None if can_next else why)


# ------------------------------------------------------------------------------------------------ steps
def _step_content(ctx: dict) -> None:
    ss = st.session_state
    html(C.heading("What would you like to explain?", "Ask a question, then add the material the video should be based on."))
    st.text_area("Your question", key=S.seed("topic"), on_change=S.sync, args=("topic",), height=100, label_visibility="collapsed",
                 placeholder="e.g. Why do prices keep rising? / Why does Ho Chi Minh City flood in heavy rain?")

    if ss["source"] == "demo":
        label = next((t["label"] for t in runner.demo_templates() if t["key"] == ss["pack"]), ss["pack"])
        html(C.alert("info", f"Using the demo content “{label}”",
                     "Hand-written claims that ship with the project. You can still change the question above."))
        btn("Use my own material instead", key="own_material", on_click=_use_own_material)
    else:
        html(C.section("Related material (recommended)"))
        st.file_uploader("Upload material (.txt or .md)", type=["txt", "md"], key=f"w_upload_{ss['upload_n']}", on_change=_on_upload,
                         label_visibility="collapsed", help="Plain text only. It is read in this session and stays on your computer.")
        if ss["upload_name"]:
            u1, u2 = st.columns([4, 1])
            u1.caption(f"Loaded: {ss['upload_name']}")
            u2.button("Remove", key="rm_upload", on_click=_clear_upload)
        st.text_area("Related material", key=S.seed("reference"), on_change=S.sync, args=("reference",), height=170, label_visibility="collapsed",
                     placeholder="Or paste the text here. Use full sentences of 8–24 words. The video is built only from this text; "
                                 "StoryFrame cannot research a topic by itself yet.")
        words = count_words(ss["topic"]) + count_words(ss["reference"])
        st.markdown(f"<div class='sf-count{' over' if words > MAX_WORDS else ''}'>{words:,} / {MAX_WORDS:,} words</div>", unsafe_allow_html=True)

        html(C.section("No material yet? Try a ready-made example"))
        demos = runner.demo_templates()
        for col, t in zip(st.columns(len(demos)), demos):
            col.button(f"{t['label']} · {LANGUAGES[t['language']]}", key=f"demo_{t['key']}", on_click=_use_demo,
                       args=(t["key"], t["label"], t["language"]), **stretch())

    msgs = _validate(ctx, final=False)
    _alerts(msgs)
    ok = bool(ss["topic"].strip()) and not has_blocking(msgs)
    _nav(1, can_next=ok, why="Fix the messages above first." if msgs else "Type your question first.")


def _step_format(ctx: dict) -> None:
    ss = st.session_state
    html(C.heading("Choose a format", "You can switch format later without rewriting the script."))
    for col, (key, title, ico, text, bullets) in zip(st.columns(len(FORMATS), gap="large"), FORMATS):
        with col:
            sel = ss["fmt"] == key
            card_button(C.format_card(title, text, bullets, ico, selected=sel), "Selected" if sel else f"Choose {title}",
                        key=f"fmt_{key}", selected=sel, on_click=_pick, args=("fmt", key))
    st.caption("Hybrid (infographic and animation combined) is coming soon.")
    _nav(2, can_next=ss["fmt"] in {f[0] for f in FORMATS}, why="Pick a format.")


def _step_voice(ctx: dict) -> None:
    ss = st.session_state
    lang, lib = ss["language"], ctx["lib"]
    html(C.heading("Pick a voice", f"Narration language: {LANGUAGES[lang]} (matched to your content)."))
    if ctx["lib_error"]:
        html(C.alert("err", "Voice library file not loaded", f"Built-in voices only. {ctx['lib_error']}"))
    voices, current = lib.list(language=lang), ss[f"voice_{lang}"]
    for row in range(0, len(voices), 2):
        for col, v in zip(st.columns(2, gap="large"), voices[row:row + 2]):
            with col:
                traits = [v.gender.title(), v.locale]
                card_button(C.voice_card(v.name, LANGUAGES[v.language], traits, selected=v.voice_id == current, note=v.notes),
                            "Selected" if v.voice_id == current else "Select", key=f"voice_{v.voice_id}", selected=v.voice_id == current,
                            on_click=_pick_voice, args=(lang, v.voice_id))
                if runner.preview_available(v, float(ss["speed"])) and st.button("▶ Preview", key=f"prev_{v.voice_id}"):
                    audio, err = runner.preview_audio(v, float(ss["speed"]))
                    ss["preview"] = (v.voice_id, audio, err)
    if ss["preview"] and ss["preview"][0] in [v.voice_id for v in voices]:
        _, audio, err = ss["preview"]
        st.audio(audio, format="audio/mp3") if audio else st.warning(err)
    if ss["engine"] == "silent":
        html(C.alert("info", "No voice engine is active, so the video will be silent",
                     "Install pyttsx3 (offline) or edge-tts (online), then choose it under “More options” on the last step."))
    _nav(3, can_next=bool(current))


def _step_budget(ctx: dict) -> None:
    ss = st.session_state
    lang = ss["language"]
    html(C.heading("Set your budget", "Credits are planning units, not money. The cost is shown before anything is made."))
    st.radio("Budget", [True, False], key=S.seed("auto_budget"), on_change=S.sync, args=("auto_budget",), horizontal=True,
             label_visibility="collapsed",
             format_func=lambda auto: "Automatic (recommended)" if auto else "I will set the maximum",
             help="Automatic = twice the cheapest plan that works, so there is room for the best render modes.")
    if not ss["auto_budget"]:
        st.number_input("Maximum credits", 1, 1000, key=S.seed("budget"), on_change=S.sync, args=("budget",), step=1)

    with st.expander("More options (duration, subtitles, speed, voice engine)"):
        st.slider("Duration (seconds)", 60, 120, key=S.seed("duration"), on_change=S.sync, args=("duration",), step=5,
                  help="The video must last 60–120 s. The result may miss the target by at most 5 %.")
        st.radio("Subtitles", list(runner.SUBTITLE_MODES), key=S.seed("subtitles"), on_change=S.sync, args=("subtitles",), horizontal=True,
                 format_func=runner.SUBTITLE_MODES.get, help="\n".join(f"{runner.SUBTITLE_MODES[k]}: {v}" for k, v in runner.SUBTITLE_HELP.items()))
        st.slider("Speaking speed", 0.75, 1.25, key=S.seed("speed"), on_change=S.sync, args=("speed",), step=0.05, format="%.2fx",
                  help="1.00x is the voice's normal pace. The planner sizes the script for this speed.")
        st.radio("Voice engine", list(runner.ENGINES), key=S.seed("engine"), on_change=S.sync, args=("engine",), horizontal=True,
                 format_func=runner.engine_label, help="\n".join(f"{runner.ENGINES[k]}: {v}" for k, v in runner.ENGINE_HELP.items()))
        if ss["engine"] == "system" and not runner.system_voice_installed():
            html(C.alert("warn", "pyttsx3 is not installed", "Run  pip install pyttsx3  or choose another engine."))
        if ss["engine"] == "edge":
            if not runner.edge_installed():
                html(C.alert("warn", "edge-tts is not installed", "Run  pip install edge-tts  or choose another engine."))
            st.checkbox("I understand the narration text is sent to an online service", key=S.seed("allow_online"), on_change=S.sync,
                        args=("allow_online",), help="Do not send private or sensitive text (report R7 / AI tool policy).")
        if ss["fmt"] == "ANIMATION":
            st.checkbox("Topic-aware visuals", key=S.seed("topic_aware"), on_change=S.sync, args=("topic_aware",),
                        help="On: objects and motion follow the topic. Off: the generic stick figure with six standard props.")
        st.text_area("Extra instructions (optional)", key=S.seed("instructions"), on_change=S.sync, args=("instructions",), height=70,
                     placeholder="e.g. keep a friendly tone, focus on everyday examples")

    msgs = _validate(ctx, final=True)
    facts = None
    if ss["topic"].strip() and ctx["claims"]:
        facts = _cached_estimate(ss["topic"], ss["instructions"], ss["reference"], ss["source"], ss["pack"], ss["fmt"], int(ss["duration"]),
                                 None if ss["auto_budget"] else int(ss["budget"]), ss[f"voice_{lang}"], float(ss["speed"]))
    est = estimate_from_facts(facts)
    html(C.section("Your video"))
    voice = ctx["lib"].get(ss[f"voice_{lang}"])
    html(C.badges([(short_title(ss["topic"], 48) or "—", "accent"), (ss["fmt"].title(), "info"), (voice.name, "neutral"),
                   (f"{int(ss['duration'])} s", "neutral")]))
    html(C.budget_card(est))
    _alerts(msgs)
    blocked = has_blocking(msgs) or not est.get("can_start")
    why = "Fix the messages above first." if has_blocking(msgs) else ("Resolve the cost estimate message first." if not est.get("can_start") else None)
    st.write("")
    left, right = st.columns([1, 2])
    with left:
        btn("Back", icon="arrow_back", key="back_4", on_click=_go, args=(LAST - 1,))
    with right:
        btn("Create Video", icon="play_arrow", key="create_video", type="primary", on_click=_start, disabled=blocked, help=why)
    st.caption("Takes about 30–60 s for a 90 s video. Nothing is spent: credits are an internal planning budget.")


_RENDER = {1: _step_content, 2: _step_format, 3: _step_voice, 4: _step_budget}


# ------------------------------------------------------------------------------------------------- view
def render() -> None:
    step = min(max(int(st.session_state["step"]), 1), LAST)
    ctx = _setup()
    html(C.hero("What would you like to create today?", "Four quick steps: question, format, voice, budget."))
    html(C.stepper(STEPS, step))
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        with st.container(border=True):
            _RENDER[step](ctx)
