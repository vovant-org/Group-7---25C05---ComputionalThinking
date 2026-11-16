"""Streamlit page: make an INFOGRAPHIC video (MP4 with voice-over and subtitles).

Open with `streamlit run app.py`, then choose "Make video" in the sidebar. All logic lives in
`modules/video/` (tested without Streamlit); this page only collects the settings and shows the result.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import streamlit as st

from core.config import OUTPUT_DIR
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, topic_keys
from modules.pipeline.ui_helpers import Check, chips_html, voice_caption, voice_option_label
from modules.providers import edge_tts_provider as tts_engine
from modules.video.claims import claims_from_text
from modules.video.make_video import make_video
from modules.video.voice import FFmpegMissing, VoiceError, find_ffmpeg, make_engine
from modules.voice_library.library import LANGUAGES, SPEED_MAX, SPEED_MIN, VoiceLibraryError, builtin_library, load_library

st.set_page_config(page_title="StoryFrame Studio – make a video", page_icon="🎥", layout="wide")

try:
    LIB = load_library()
    LIB_ERROR = None
except VoiceLibraryError as exc:
    LIB, LIB_ERROR = builtin_library(), str(exc)

ENGINES = {"silent": "Silent (no sound, offline)",
           "system": "System voice (offline, needs pyttsx3)",
           "edge": "Edge neural voice (ONLINE, needs edge-tts)"}
SAMPLE_REQUEST = "Make a 90-second infographic video about sleep"

st.title("🎥 Make an infographic video")
st.caption("Request → plan → real voice-over → frames drawn by code → MP4 with subtitles. "
           "Only the INFOGRAPHIC format is built.")

try:
    find_ffmpeg()
    FFMPEG_OK = True
except FFmpegMissing as exc:
    FFMPEG_OK = False
    st.error(f"{exc}")

with st.sidebar:
    st.header("1 · Request")
    request_text = st.text_area("Request", SAMPLE_REQUEST, height=90)
    language = st.radio("Narration language", LIB.languages(), format_func=LANGUAGES.get, horizontal=True)
    source = st.radio("Content", ["Demo claim pack", "My own text"], horizontal=True,
                      help="Own text: sentences of 8-24 words become the claims (a simple extractive step, "
                           "not verified against sources).")
    if source == "Demo claim pack":
        pack = st.selectbox("Claim pack", topic_keys(language), format_func=TOPIC_LABELS.get)
        reference = ""
    else:
        pack = None
        reference = st.text_area("Your text", height=220, help="At most 1,500 words together with the request.")
        st.caption(f"{len(reference.split()):,} words")

    st.header("2 · Voice")
    voice_id = st.selectbox("Voice", [v.voice_id for v in LIB.list(language=language)],
                            format_func=lambda i: voice_option_label(LIB.get(i)))
    voice = LIB.get(voice_id)
    speed = st.slider("Speaking speed", SPEED_MIN, SPEED_MAX, 1.0, 0.05, format="%.2fx")
    st.caption(voice_caption(voice, speed))
    have_system = importlib.util.find_spec("pyttsx3") is not None
    engine_kind = st.radio("Voice engine", list(ENGINES), format_func=ENGINES.get,
                           help="The silent engine lets you check the picture and timing without any TTS.")
    allow_online = False
    if engine_kind == "edge":
        allow_online = st.checkbox("I understand the narration text is sent to an online service",
                                   help="Report R7 / AI tool policy: do not send private or sensitive text.")
        if not tts_engine.is_available():
            st.warning("edge-tts is not installed: pip install edge-tts")
    if engine_kind == "system" and not have_system:
        st.warning("pyttsx3 is not installed: pip install pyttsx3")

    st.header("3 · Options")
    burn = st.checkbox("Burn subtitles into the picture", True)
    go = st.button("🎬 Create video", type="primary", disabled=not FFMPEG_OK or not request_text.strip())


def _run():
    """Build the video; returns (result, error text)."""
    wpm = voice.planning_wpm(speed)
    try:
        engine = make_engine(engine_kind, voice, speed, allow_online, wpm)
    except Exception as exc:                       # missing package, not confirmed online, ...
        return None, f"Voice engine: {exc}"
    claims = get_sample_claims(pack) if pack else claims_from_text(reference)
    if not claims:
        return None, "No usable sentence (8-24 words) was found in your text."
    key = hashlib.sha1(f"{request_text}|{pack}|{reference}|{voice_id}|{speed}|{engine.name}|{burn}".encode()).hexdigest()[:10]
    out = OUTPUT_DIR / "videos" / f"web-{key}.mp4"
    bar = st.progress(0.0, text="Planning…")
    res = make_video(request_text, claims, out, engine=engine, voice=voice, speed=speed, reference_text=reference,
                     burn_subtitles=burn, progress=lambda f, m: bar.progress(min(1.0, f), text=f"Rendering {m}"))
    bar.empty()
    return res, ""


if go:
    with st.spinner("Creating the video… (about 30–60 s)"):
        result, err = _run()
    st.session_state["video"] = (result, err)

if "video" not in st.session_state:
    st.info("Choose a request and a voice, then press **🎬 Create video**.")
    st.stop()

result, err = st.session_state["video"]
if err:
    st.error(err)
    st.stop()
if not result.ok:
    st.error(result.error)
    for line in result.log:
        st.caption("adjust: " + line)
    st.stop()

rep = result.report
left, right = st.columns([3, 2])
with left:
    st.video(result.video_path.read_bytes())
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ MP4", result.video_path.read_bytes(), file_name=result.video_path.name, mime="video/mp4")
    srt = Path(rep["video"]).with_suffix(".srt")
    d2.download_button("⬇ Subtitles (.srt)", srt.read_bytes(), file_name=srt.name, mime="text/plain")
    d3.download_button("⬇ Report (.json)", json.dumps(rep, ensure_ascii=False, indent=2),
                       file_name="video-report.json", mime="application/json")
with right:
    st.success(f"**Video ready** · {rep['total_s']:.1f} s · {rep['scenes']} scenes · {rep['resolution'][0]}×{rep['resolution'][1]} · {rep['fps']} fps")
    st.markdown("**Checks on the finished MP4**")
    names = {"S11": "format", "S12": "60–120 s", "S13": "≤ 5 % off target", "S15": "labels"}
    st.markdown(chips_html([Check(k, names.get(k, ""), "pass" if v["pass"] else "fail", v["detail"])
                            for k, v in rep["criteria"].items()]), unsafe_allow_html=True)
    if rep["voice_is_silent"]:
        st.warning("The audio track is silent (silent engine). Choose a system or Edge voice for a spoken video.")
    if result.log:
        with st.expander("Duration adjustments (N4 → N3 → N2)"):
            for line in result.log:
                st.write("• " + line)
    for note in rep["notes"]:
        if "SILENT" not in note:
            st.caption("ℹ️ " + note)

with st.expander("Scenes, layouts and on-screen labels"):
    st.dataframe([{"scene": t["scene"], "start_s": t["start_s"], "length_s": t["duration_s"], "mode": t["mode"],
                   "layout": t["layout"], "labels": " | ".join(t["labels"])} for t in rep["timeline"]],
                 hide_index=True, column_config={"labels": st.column_config.TextColumn("labels", width="large")})
