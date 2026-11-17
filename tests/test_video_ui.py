"""Tests of the UI of the video maker: pure helpers, the subtitle line balancing, and the Streamlit page
itself (run headless with Streamlit's AppTest, silent voice, so no TTS and no network are needed)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.models import OutputFormat
from modules.pipeline.sample_claims import get_sample_claims
from modules.pipeline.ui_helpers import (VIDEO_FORMATS, format_from_choice, layout_label, video_check_names,
                                         video_metrics, video_scene_rows)
from modules.video.composer import wrap
from modules.video.fonts import get_font
from modules.video.make_video import make_video
from modules.video.subtitles import balanced_lines
from modules.video.voice import FFmpegMissing, find_ffmpeg, make_engine
from modules.voice_library.library import builtin_library

PAGE = str(Path(__file__).resolve().parent.parent / "pages" / "1_Make_video.py")
CLAIMS = get_sample_claims("sleep")


def _report(request):
    voice = builtin_library().default("en")
    engine = make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))
    res = make_video(request, CLAIMS, "unused.mp4", engine=engine, voice=voice, render=False)
    assert res.ok, res.error
    return res.report


# ------------------------------------------------------------------ subtitle line balancing
SENTENCE = "Remember new facts and react quickly to what happens around you"


def _orphan_width(size):
    """A line width at which greedy wrapping leaves ONE word on the last line (the bug we fix)."""
    font = get_font(size)
    for w in range(300, 1200, 10):
        lines = wrap(SENTENCE, font, w)
        if len(lines) >= 2 and len(lines[-1].split()) == 1:
            return w
    pytest.skip("no width gives a one-word last line with this font")


def test_balanced_lines_remove_the_one_word_last_line():
    width = _orphan_width(34)
    font = get_font(34)
    greedy, fixed = wrap(SENTENCE, font, width), balanced_lines(SENTENCE, 34, width)
    assert len(greedy[-1].split()) == 1                       # the problem exists ...
    assert len(fixed) == len(greedy) and len(fixed[-1].split()) >= 2   # ... and is gone, same number of lines
    assert all(font.getlength(x) <= width for x in fixed)
    assert " ".join(fixed) == SENTENCE                         # nothing lost, nothing reordered


def test_balanced_lines_keep_short_text_on_one_line():
    assert balanced_lines("Short line", 34, 1140) == ["Short line"]


def test_balanced_lines_never_add_a_line():
    for w in range(300, 1200, 60):
        assert len(balanced_lines(SENTENCE, 34, w)) == len(wrap(SENTENCE, get_font(34), w))


# ------------------------------------------------------------------ pure helpers
def test_format_choices():
    assert format_from_choice("auto") is None
    assert format_from_choice("infographic") == OutputFormat.INFOGRAPHIC
    assert format_from_choice("animation") == OutputFormat.ANIMATION
    assert set(VIDEO_FORMATS) == {"auto", "infographic", "animation"}      # no hybrid on offer: it is not built
    with pytest.raises(KeyError):
        format_from_choice("hybrid")


def test_check_names_depend_on_the_format():
    anim, info = video_check_names("ANIMATION"), video_check_names("INFOGRAPHIC")
    assert set(anim) == set(info) == {"S11", "S12", "S13", "S15"}
    assert anim["S11"] != info["S11"] and "n/a" in anim["S15"]
    assert video_check_names("SOMETHING") == info                           # unknown: the infographic names


def test_cutout_layouts_get_readable_labels():
    assert layout_label("cutout:cause_effect") == "🧍 cut-out · cause → effect"
    assert layout_label("cutout:bulb") == "🧍 cut-out · idea"
    assert layout_label("cutout:new_prop") == "🧍 cut-out · new_prop"       # unknown props still show something
    assert layout_label("cause_chain") == "🔗 cause chain" and layout_label(None).startswith("🎞️")


def test_scene_rows_for_an_animation_show_the_motion_plan():
    rep = _report("Make a 90-second animated video about sleep")
    rows = video_scene_rows(rep)
    assert len(rows) == rep["scenes"] and rows[0]["pose"] == "wave"          # the hook waves
    assert all({"pose", "prop", "energy", "narration"} <= set(r) and "labels" not in r for r in rows)
    assert all(r["layout"].startswith("🧍") for r in rows)


def test_scene_rows_for_an_infographic_show_the_labels():
    rep = _report("Make a 90-second infographic video about sleep")
    rows = video_scene_rows(rep)
    assert all("labels" in r and "pose" not in r for r in rows) and rows[0]["labels"]


def test_metrics():
    rep = _report("Make a 90-second animated video about sleep")
    m = {label: value for label, value, _ in video_metrics(rep)}
    assert m["Format"] == "Animation" and m["Scenes"] == str(rep["scenes"])
    assert m["Length"].endswith(" s") and m["Off target"].endswith("%")


# ------------------------------------------------------------------ the page itself
def _ffmpeg_ok():
    try:
        find_ffmpeg()
        return True
    except FFmpegMissing:
        return False


def _radio(at, label):
    return next(r for r in at.radio if r.label == label)


def test_page_opens_without_error_and_offers_the_formats():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    assert not at.exception, at.exception
    fmt = _radio(at, "Format")
    assert [o for o in fmt.options] == [f"{i} {VIDEO_FORMATS[k][0]}" for k, i in
                                        (("auto", "🧭"), ("infographic", "📊"), ("animation", "🧍"))]
    assert fmt.value == "auto"
    assert any("Animation" in o for o in fmt.options) and not any("Hybrid" in o for o in fmt.options)


def test_example_request_fills_the_text_box():
    at = AppTest.from_file(PAGE, default_timeout=60).run()
    at.selectbox(key="vid_example").select("Make a 90-second animated video about sleep").run()
    assert at.text_area(key="vid_req").value == "Make a 90-second animated video about sleep"


@pytest.mark.skipif(not _ffmpeg_ok(), reason="FFmpeg is not installed")
def test_page_makes_an_animation_video_end_to_end():
    at = AppTest.from_file(PAGE, default_timeout=240).run()
    _radio(at, "Format").set_value("animation")
    next(r for r in at.radio if r.label == "Voice engine").set_value("silent")
    next(b for b in at.button if "Create video" in b.label).click()
    at.run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Format"] == "Animation" and metrics["Length"].endswith(" s")
    assert len(at.tabs) == 4
