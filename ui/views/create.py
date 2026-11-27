"""New Project: a four-step flow instead of one crowded form.

    1. Your question (+ optional related material)  ->  2. Format  ->  3. Voice  ->  4. Budget (+ Create)

Everything that is not one of these four answers has a sensible default and lives under
"More options" on the last step: duration, subtitles, speaking speed, voice engine, topic-aware visuals,
extra instructions. The language is not asked: it is detected from the content (also Vietnamese typed without
tone marks), and the voices offered are the ones that speak it. The voice itself is cast from the topic
(modules/voice_library/casting.py): a calm voice for sleep, an authoritative one for economics, a lively one for
technology... together with a matching speaking speed and pitch. The user can switch this off and pick any voice. The content source is not asked either: material typed or uploaded by the
user is used; with a question only, the REASON step (modules/reason) can research it: a free online AI writes the
material into the box, where the user reviews it before continuing; otherwise a ready-made demo can be picked.
"""
from __future__ import annotations

import streamlit as st

from modules.video.render import QUALITY_PROFILES
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


def _ask_research() -> None:
    """Button callback: the research itself runs in the next script run, under a spinner (it takes 10-60 s)."""
    st.session_state["research_pending"] = True


def _on_reference() -> None:
    S.sync("reference")
    if not st.session_state["reference"].strip():              # box emptied: whatever comes next is not the AI's text
        st.session_state["ref_origin"] = "user"
        st.session_state["research_info"] = None


def _run_research() -> None:
    ss = st.session_state
    ss["research_pending"] = False
    with st.spinner("Researching your question with AI… (usually 10–60 s)"):
        res = runner.research(ss["topic"], ss["instructions"], ss["research_ai"], float(ss["duration"]))
    ss["research_info"] = {"ok": res.ok, "provider": res.provider, "error": res.error, "rejected": len(res.rejected),
                           "sentences": len(res.sentences), "title": res.title}
    if res.ok:
        S.put("reference", res.text)
        S.put("source", "text")
        ss["ref_origin"] = "ai"


def _pick(key: str, value) -> None:
    S.put(key, value)


def _pick_voice(language: str, voice_id: str) -> None:
    """A voice picked by hand: the automatic casting stops overriding it (pitch back to the voice's own)."""
    ss = st.session_state
    ss[f"voice_{language}"] = voice_id
    S.put("auto_voice", False)
    S.put("pitch", 0)
    ss["voice_mood"] = ""


def _apply_cast(language: str, cast) -> None:
    ss = st.session_state
    ss[f"voice_{language}"] = cast.voice_id
    S.put("speed", cast.speed)
    S.put("pitch", cast.pitch_hz)
    ss["voice_mood"] = cast.mood
    ss["cast_applied"] = (language,) + cast.key


def _use_suggested(language: str, cast) -> None:
    S.put("auto_voice", True)
    _apply_cast(language, cast)


def _on_auto_voice() -> None:
    S.sync("auto_voice")
    st.session_state["cast_applied"] = None              # switched on again: re-apply the suggestion on the next run
    if not st.session_state["auto_voice"]:
        st.session_state["voice_mood"] = ""


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
    st.session_state["ref_origin"] = "user"
    st.session_state["research_info"] = None


def _clear_upload() -> None:
    st.session_state["upload_n"] += 1
    st.session_state["upload_name"] = ""
    st.session_state["upload_error"] = ""
    S.put("reference", "")
    st.session_state["ref_origin"] = "user"
    st.session_state["research_info"] = None


def _start() -> None:
    ss = st.session_state
    lang = ss["language"]
    ss["job"] = runner.GenParams(
        topic=ss["topic"], instructions=ss["instructions"], reference=ss["reference"], source=ss["source"],
        pack=ss["pack"] if ss["source"] == "demo" else None, fmt=ss["fmt"], t_target=int(ss["duration"]),
        budget=None if ss["auto_budget"] else int(ss["budget"]), voice_id=ss[f"voice_{lang}"], speed=float(ss["speed"]),
        engine_kind=ss["engine"], allow_online=bool(ss["allow_online"]), subtitles=ss["subtitles"],
        topic_aware=bool(ss["topic_aware"]), language=lang, quality=ss["quality"],
        ai_read=ss["ai_read"], ai_image=ss["ai_image"], ai_online=bool(ss["ai_online"]), ai_folder=ss["ai_folder"].strip(),
        pitch_hz=int(ss["pitch"]) if ss["engine"] == "edge" else 0, voice_mood=ss["voice_mood"] if ss["auto_voice"] else "",
        content_origin=ss["ref_origin"] if ss["source"] == "text" and ss["reference"].strip() else "user")
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
    ctexts = [c.text for c in claims]
    texts = ctexts or ([ss["reference"]] if ss["source"] == "text" and ss["reference"].strip() else [])
    cast = runner.cast_voice(lib, ss["language"], ss["topic"], texts, ss["instructions"])
    if ss["auto_voice"] and ss["cast_applied"] != (ss["language"],) + cast.key:
        _apply_cast(ss["language"], cast)                # the topic (or language) changed: follow it
    return {"lib": lib, "lib_error": lib_error, "claims": claims, "ctexts": ctexts, "detected": detected, "cast": cast}


def _validate(ctx: dict, *, final: bool) -> list[dict]:
    """Content problems for step 1; every problem (FFmpeg, voice engine, ...) for the last step."""
    ss = st.session_state
    kw = dict(topic=ss["topic"], instructions=ss["instructions"] if final else "",
              reference=ss["reference"] if ss["source"] == "text" else "", source=ss["source"], claims_text=ctx["ctexts"],
              voice_language=ss["language"], upload_error=ss["upload_error"], detected_language=ctx["detected"],
              ai_reads=ss["ai_read"] != "off")
    if final:
        needs = ss["ai_read"] != "off" or ss["ai_image"] in ("pollinations", "cloudflare")
        return validate_inputs(ffmpeg_ok=runner.ffmpeg_ok(), online_ok=bool(ss["allow_online"]), engine_kind=ss["engine"],
                               ai_online_needed=needs, ai_online_ok=bool(ss["ai_online"]), **kw)
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
        if ss["research_pending"]:
            _run_research()
        html(C.section("Related material (recommended)"))
        st.file_uploader("Upload material (.txt or .md)", type=["txt", "md"], key=f"w_upload_{ss['upload_n']}", on_change=_on_upload,
                         label_visibility="collapsed", help="Plain text only. It is read in this session and stays on your computer.")
        if ss["upload_name"]:
            u1, u2 = st.columns([4, 1])
            u1.caption(f"Loaded: {ss['upload_name']}")
            u2.button("Remove", key="rm_upload", on_click=_clear_upload)
        info = ss["research_info"]
        if info and info["ok"] and ss["ref_origin"] == "ai":
            extra = f" {info['rejected']} sentence(s) were dropped by the checks." if info["rejected"] else ""
            html(C.alert("warn", f"Material written by AI ({info['provider']}), not verified",
                         f"{info['sentences']} sentences. Read them and correct anything that looks wrong: the video says exactly "
                         f"this text.{extra}"))
        st.text_area("Related material", key=S.seed("reference"), on_change=_on_reference, height=220 if ss["ref_origin"] == "ai" else 170,
                     label_visibility="collapsed",
                     placeholder="Or paste the text here. Use full sentences of 8–24 words. The video is built only from this text. "
                                 "No material? Let the AI research your question below.")
        words = count_words(ss["topic"]) + count_words(ss["reference"])
        st.markdown(f"<div class='sf-count{' over' if words > MAX_WORDS else ''}'>{words:,} / {MAX_WORDS:,} words</div>", unsafe_allow_html=True)

        _research_panel()

        html(C.section("No material yet? Try a ready-made example"))
        demos = runner.demo_templates()
        for col, t in zip(st.columns(len(demos)), demos):
            col.button(f"{t['label']} · {LANGUAGES[t['language']]}", key=f"demo_{t['key']}", on_click=_use_demo,
                       args=(t["key"], t["label"], t["language"]), **stretch())

    msgs = _validate(ctx, final=False)
    _alerts(msgs)
    ok = bool(ss["topic"].strip()) and not has_blocking(msgs)
    _nav(1, can_next=ok, why="Fix the messages above first." if msgs else "Type your question first.")


def _research_panel() -> None:
    """REASON step: let a free online AI write the material from the question (modules/reason/research.py)."""
    ss = st.session_state
    own_text = bool(ss["reference"].strip()) and ss["ref_origin"] != "ai"
    html(C.section("No material? Let AI research your question"))
    c1, c2 = st.columns([1, 2])
    c1.selectbox("AI provider", ["auto", "gemini", "pollinations"], key=S.seed("research_ai"), on_change=S.sync, args=("research_ai",),
                 format_func={"auto": "Auto (Gemini, then Pollinations)", "gemini": "Gemini (free key)",
                              "pollinations": "Pollinations (no key)"}.get,
                 help="Gemini needs GEMINI_API_KEY (free at aistudio.google.com). Pollinations needs no key but is slower.")
    with c2:
        st.write("")
        st.checkbox("I understand my question is sent to an online AI service", key=S.seed("ai_online"), on_change=S.sync,
                    args=("ai_online",))
    why = ("Type your question first." if not ss["topic"].strip() else
           "Clear the material box first: AI research never overwrites your own text." if own_text else
           "Tick the confirmation first." if not ss["ai_online"] else None)
    label = "Research again" if ss["ref_origin"] == "ai" and ss["reference"].strip() else "Research this topic with AI"
    btn(label, icon="auto_awesome", key="research", on_click=_ask_research, disabled=why is not None, help=why)
    st.caption("The AI writes general, well-established explanations in the language of your question, without numbers or names. "
               "It is not a fact-checked source: review the text before you continue.")
    info = ss["research_info"]
    if info and not info["ok"]:
        html(C.alert("err", "AI research failed", f"{info['error']} You can paste your own text or pick a demo instead."))


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
    lang, lib, cast = ss["language"], ctx["lib"], ctx["cast"]
    how = "detected from your content" if ctx["detected"] else "no text to detect yet"
    html(C.heading("Pick a voice", f"Narration language: {LANGUAGES[lang]} ({how}). Only voices that speak it are shown."))
    if ctx["lib_error"]:
        html(C.alert("err", "Voice library file not loaded", f"Built-in voices only. {ctx['lib_error']}"))
    st.toggle("Auto-match the voice to my topic", key=S.seed("auto_voice"), on_change=_on_auto_voice,
              help="On: the app reads your question and material and picks the voice, speaking speed and pitch that suit "
                   "the subject (calm for sleep, authoritative for economics, lively for technology...). Picking a voice "
                   "below switches this off. Offline: nothing is sent anywhere.")
    suggested = lib.get(cast.voice_id)
    tune = f"Speed {cast.speed:.2f}x" + (f", pitch {cast.pitch_hz:+d} Hz (Edge voices)" if cast.pitch_hz else "")
    if ss["auto_voice"]:
        html(C.alert("ok", f"Voice for this topic: {suggested.name} · {cast.label}", f"{cast.reason} {tune}."))
    else:
        html(C.alert("info", f"Suggested for this topic: {suggested.name} · {cast.label}", f"{cast.reason} {tune}."))
        btn("Use the suggested voice", icon="auto_awesome", key="use_cast", on_click=_use_suggested, args=(lang, cast))
    voices, current = lib.list(language=lang), ss[f"voice_{lang}"]
    pitch = int(ss["pitch"])
    for row in range(0, len(voices), 2):
        for col, v in zip(st.columns(2, gap="large"), voices[row:row + 2]):
            with col:
                traits = [v.gender.title(), v.locale]
                note = " · ".join(n for n in ["★ Best match for this topic" if v.voice_id == cast.voice_id else "", v.notes] if n)
                card_button(C.voice_card(v.name, LANGUAGES[v.language], traits, selected=v.voice_id == current, note=note),
                            "Selected" if v.voice_id == current else "Select", key=f"voice_{v.voice_id}", selected=v.voice_id == current,
                            on_click=_pick_voice, args=(lang, v.voice_id))
                vp = pitch if v.voice_id == current and runner.preview_available(v, float(ss["speed"]), pitch) else 0
                if runner.preview_available(v, float(ss["speed"]), vp) and st.button("▶ Preview", key=f"prev_{v.voice_id}"):
                    audio, err = runner.preview_audio(v, float(ss["speed"]), vp)
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

    with st.expander("More options (video quality, duration, subtitles, speed, voice engine)"):
        st.radio("Video quality", list(runner.QUALITY_LABELS), key=S.seed("quality"), on_change=S.sync, args=("quality",), horizontal=True,
                 format_func=runner.QUALITY_LABELS.get,
                 help="\n\n".join(f"{k}: {v}" for k, v in runner.QUALITY_HELP.items()))
        st.caption(QUALITY_PROFILES[ss["quality"]].note)
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
            st.slider("Voice pitch (Hz)", -10, 10, key=S.seed("pitch"), on_change=S.sync, args=("pitch",), step=1,
                      help="0 = the voice's own pitch. Set automatically when “Auto-match the voice to my topic” is on.")
            if not runner.edge_installed():
                html(C.alert("warn", "edge-tts is not installed", "Run  pip install edge-tts  or choose another engine."))
            st.checkbox("I understand the narration text is sent to an online service", key=S.seed("allow_online"), on_change=S.sync,
                        args=("allow_online",), help="Do not send private or sensitive text (report R7 / AI tool policy).")
        st.markdown("**AI (free)**")
        st.radio("AI reads my input", ["off", "auto", "pollinations", "gemini"], key=S.seed("ai_read"), on_change=S.sync, args=("ai_read",), horizontal=True,
                 format_func={"off": "Off", "auto": "Auto (Gemini, then Pollinations)", "pollinations": "Pollinations (no key)", "gemini": "Gemini (free key)"}.get,
                 help="An AI reads your topic and material, picks the claims and describes one picture per scene. With reference text, "
                      "every claim must come from your text (the app checks this). Gemini needs the GEMINI_API_KEY environment variable.")
        if ss["fmt"] == "INFOGRAPHIC":
            st.radio("AI picture of each claim", ["off", "pollinations", "cloudflare", "folder"], key=S.seed("ai_image"), on_change=S.sync, args=("ai_image",),
                     horizontal=True, format_func={"off": "Off", "pollinations": "Pollinations (free, slow)", "cloudflare": "Cloudflare (free key)", "folder": "My own pictures"}.get,
                     help="Pollinations: about one picture per 15 s. My own pictures: make them in Google Flow / ImageFX and save them as "
                          "<claim id>.png in a folder (the prompt kit comes from the command line: --export-kit). Text on screen is still drawn by code.")
            if ss["ai_image"] == "folder":
                st.text_input("Folder with the pictures", key=S.seed("ai_folder"), on_change=S.sync, args=("ai_folder",))
        if ss["ai_read"] != "off" or (ss["fmt"] == "INFOGRAPHIC" and ss["ai_image"] in ("pollinations", "cloudflare")):
            st.checkbox("I understand my text is sent to an online AI service", key=S.seed("ai_online"), on_change=S.sync, args=("ai_online",),
                        help="Do not send private or sensitive text.")
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
    if facts is None and ss["topic"].strip() and ss["ai_read"] != "off" and ss["source"] == "text" and not ss["reference"].strip():
        est = {"status_key": "pending", "status_text": "Estimated after the AI reads your topic", "can_start": True,
               "blocking": False, "messages": ["The cost is planned after the AI has written the claims."]}
    html(C.section("Your video"))
    voice = ctx["lib"].get(ss[f"voice_{lang}"])
    mood = ctx["cast"].label if ss["auto_voice"] else "Voice picked by you"
    html(C.badges([(short_title(ss["topic"], 48) or "—", "accent"), (ss["fmt"].title(), "info"), (voice.name, "neutral"), (mood, "neutral"),
                   (f"{int(ss['duration'])} s", "neutral"), (runner.QUALITY_LABELS[ss["quality"]], "neutral")]))
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
