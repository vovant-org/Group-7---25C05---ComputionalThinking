"""Streamlit page: make an INFOGRAPHIC or ANIMATION video (MP4 with voice-over and subtitles).

Open with `streamlit run app.py`, then choose "Make video" in the sidebar. All logic lives in
`modules/video/` (tested without Streamlit); this page only collects the settings and shows the result.

Layout: sidebar (1 request and format, 2 voice, 3 options) | headline numbers | tabs
Video, Scenes, Checks, Report. Data shaping lives in `modules/pipeline/ui_helpers.py` (unit-tested).
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import streamlit as st

from core.config import OUTPUT_DIR
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, topic_keys
from modules.pipeline.ui_helpers import (VIDEO_FORMATS, Check, chips_html, format_from_choice, legend_html,
                                         timeline_bar_html, video_check_names, video_metrics, video_scene_rows,
                                         voice_caption, voice_option_label)
from modules.providers import edge_tts_provider as tts_engine
from modules.video.claims import claims_from_text
from modules.video.make_video import make_video
from modules.video.voice import FFmpegMissing, find_ffmpeg, make_engine
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
CUSTOM = "(write your own)"
EXAMPLES = {"Make a 90-second infographic video about sleep": "infographic",
            "Make a 90-second animated video about sleep": "animation: the character acts out each claim",
            "Make a 60-second animated video about sleep": "animation, shorter",
            "Tạo video hoạt hình 90 giây về giấc ngủ": "Vietnamese animation: pick Tiếng Việt narration"}
FORMAT_ICONS = {"auto": "🧭", "infographic": "📊", "animation": "🧍"}

if "vid_req" not in st.session_state:
    st.session_state["vid_req"] = next(iter(EXAMPLES))


def _on_example():
    chosen = st.session_state.get("vid_example", CUSTOM)
    if chosen != CUSTOM:
        st.session_state["vid_req"] = chosen


st.title("🎥 Make a video")
st.caption("Request → plan → voice-over → frames drawn by code → MP4 with subtitles. "
           "Infographic and animation are built; the hybrid format is not.")

try:
    find_ffmpeg()
    FFMPEG_OK = True
except FFmpegMissing as exc:
    FFMPEG_OK = False
    st.error(f"{exc}  ·  run `pip install -r requirements-video.txt`")

with st.sidebar:
    st.header("1 · Request")
    st.selectbox("Example requests", [CUSTOM] + list(EXAMPLES), key="vid_example", on_change=_on_example,
                 format_func=lambda x: x if x not in EXAMPLES else f"{x}  —  {EXAMPLES[x]}")
    request_text = st.text_area("Request", key="vid_req", height=90)
    fmt_key = st.radio("Format", list(VIDEO_FORMATS), horizontal=True,
                       format_func=lambda k: f"{FORMAT_ICONS[k]} {VIDEO_FORMATS[k][0]}",
                       help="Auto reads the format from the request. A choice here wins over the words of the request.")
    st.caption(VIDEO_FORMATS[fmt_key][1])
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
        words = len(request_text.split()) + len(reference.split())
        st.caption(f"{words:,} / 1,500 words" + ("  ⚠️ over the limit, the Router will reject it" if words > 1500 else ""))

    st.header("2 · Voice")
    if LIB_ERROR:
        st.error(f"data/voice_library.json was not loaded, built-in voices only: {LIB_ERROR}")
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
    go = st.button("🎬 Create video", type="primary", use_container_width=True,
                   disabled=not FFMPEG_OK or not request_text.strip())
    st.caption("Takes about 30–60 s for a 90 s video.")


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
    key = hashlib.sha1(f"{request_text}|{fmt_key}|{pack}|{reference}|{voice_id}|{speed}|{engine.name}|{burn}"
                       .encode()).hexdigest()[:10]
    out = OUTPUT_DIR / "videos" / f"web-{key}.mp4"
    bar = st.progress(0.0, text="Planning…")
    res = make_video(request_text, claims, out, engine=engine, voice=voice, speed=speed, reference_text=reference,
                     output_format=format_from_choice(fmt_key), burn_subtitles=burn,
                     progress=lambda f, m: bar.progress(min(1.0, f), text=f"Rendering {m}"))
    bar.empty()
    return res, ""


if go:
    with st.spinner("Creating the video… (about 30–60 s)"):
        result, err = _run()
    st.session_state["video"] = (result, err)

if "video" not in st.session_state:
    st.info("Choose a request and a format in the sidebar, then press **🎬 Create video**.")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**1 · Plan**  \nThe Router checks the request, the Scene Segmenter picks the claims, the Budget "
                "Optimizer chooses a render mode for every scene.")
    c2.markdown("**2 · Voice**  \nThe narration is spoken (or timed, with the silent engine). If the length misses the "
                "target, pauses, speed and the number of claims are adjusted.")
    c3.markdown("**3 · Frames**  \nEvery frame is drawn by code: cards and numbers for the infographic, a cut-out "
                "character with keyframes for the animation. FFmpeg joins picture, voice and subtitles.")
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
for col, (label, value, hint) in zip(st.columns(4), video_metrics(rep)):
    col.metric(label, value, help=hint)

tab_video, tab_scenes, tab_checks, tab_report = st.tabs(["🎬 Video", "🎞️ Scenes", "✅ Checks", "📄 Report"])

with tab_video:
    left, right = st.columns([3, 2])
    with left:
        st.video(result.video_path.read_bytes())
    with right:
        st.success(f"**Video ready** · {rep['total_s']:.1f} s · {rep['scenes']} scenes · "
                   f"{rep['resolution'][0]}×{rep['resolution'][1]} · {rep['fps']} fps")
        srt = Path(rep["video"]).with_suffix(".srt")
        st.download_button("⬇ MP4", result.video_path.read_bytes(), file_name=result.video_path.name,
                           mime="video/mp4", use_container_width=True)
        st.download_button("⬇ Subtitles (.srt)", srt.read_bytes(), file_name=srt.name, mime="text/plain",
                           use_container_width=True)
        if rep["voice_is_silent"]:
            st.warning("The audio track is silent (silent engine). Choose a system or Edge voice for a spoken video.")

with tab_scenes:
    entries = result.pipeline.timeline.entries
    st.markdown(timeline_bar_html(entries), unsafe_allow_html=True)
    st.markdown(legend_html(entries), unsafe_allow_html=True)
    st.dataframe(video_scene_rows(rep), hide_index=True, use_container_width=True,
                 column_config={"labels": st.column_config.TextColumn("labels", width="large"),
                                "narration": st.column_config.TextColumn("narration", width="large")})

with tab_checks:
    names = video_check_names(rep["format"])
    st.markdown("**Checks on the finished MP4**")
    st.markdown(chips_html([Check(k, names.get(k, ""), "pass" if v["pass"] else "fail", v["detail"])
                            for k, v in rep["criteria"].items()]), unsafe_allow_html=True)
    if result.log:
        st.markdown("**Duration adjustments (N0 → N4 → N3 → N2)**")
        for line in result.log:
            st.write("• " + line)
    notes = [n for n in rep["notes"] if "SILENT" not in n]
    if notes:
        st.markdown("**Notes**")
        for note in notes:
            st.caption("ℹ️ " + note)

with tab_report:
    st.download_button("⬇ Report (.json)", json.dumps(rep, ensure_ascii=False, indent=2),
                       file_name="video-report.json", mime="application/json")
    st.json(rep, expanded=False)
