"""Tests of the voice choice inside the pipeline, the Vietnamese claim packs, the helpers behind the
voice picker and the CLI flags. Expected values come from the rules in the report and the module
docstrings (W_target = wpm * T / 60, S12, S13, language of the voice must match the narration)."""
import pytest

from core.config import VOICE_WPM
from modules.pipeline import cli
from modules.pipeline.pipeline import PipelineStatus, Stage, run_pipeline
from modules.pipeline.sample_claims import TOPIC_LABELS, get_sample_claims, pack_language, topic_keys
from modules.pipeline.ui_helpers import (result_summary, voice_caption, voice_info, voice_library_rows,
                                         voice_option_label)
from modules.router.router import Request
from modules.voice_library.library import SPEED_MAX, SPEED_MIN, VoiceProfile, builtin_library

LIB = builtin_library()
EN_TEXT = "Make a 90-second infographic video about sleep"
VI_TEXT = "Tạo video infographic 90 giây về giấc ngủ"


def run(text, pack, voice_id=None, speed=1.0, **kw):
    voice = LIB.get(voice_id) if voice_id else None
    return run_pipeline(Request(topic=text), get_sample_claims(pack), voice=voice, voice_speed=speed, **kw)


def timings(res):
    return [(e.scene_id, e.start_s, e.duration_s) for e in res.timeline.entries]


# ------------------------------------------------------------------ claim packs
def test_pack_languages_and_labels():
    assert topic_keys("en") == ["sleep", "inflation"]
    assert topic_keys("vi") == ["sleep_vi", "inflation_vi"]
    assert topic_keys() == topic_keys("en") + topic_keys("vi")
    assert all(k in TOPIC_LABELS for k in topic_keys())
    assert pack_language("sleep") == "en" and pack_language("inflation_vi") == "vi"


def test_unknown_pack_is_an_error_for_language_lookup_too():
    with pytest.raises(KeyError):
        pack_language("nope")


def test_claim_ids_of_a_vietnamese_pack_differ_from_the_english_one():
    assert get_sample_claims("sleep_vi")[0].claim_id == "SLEV01"
    assert get_sample_claims("sleep")[0].claim_id == "SLE01"


# ------------------------------------------------------------------ no voice = old behaviour
def test_without_a_voice_nothing_about_the_voice_is_recorded():
    r = run(EN_TEXT, "sleep")
    assert r.voice_profile is None and r.planning_wpm == VOICE_WPM and r.voice_speed == 1.0
    assert voice_info(r) == "" and "voice " not in result_summary(r).split("voice units")[-1]


def test_an_unmeasured_voice_at_normal_speed_plans_exactly_like_no_voice():
    """Its wpm is the same assumption (VOICE_WPM), so nothing may change."""
    base = run(EN_TEXT, "sleep")
    with_voice = run(EN_TEXT, "sleep", "en-aria")
    assert timings(with_voice) == timings(base)
    assert [c.claim_id for c in with_voice.selection.claims] == [c.claim_id for c in base.selection.claims]


# ------------------------------------------------------------------ the voice sets the plan
def test_the_voice_sets_the_speaking_rate_the_planner_uses():
    measured = VoiceProfile("en-fast", "Fast", "en", "en-US", "male", "edge-tts", "en-US-FastNeural", measured_wpm=200.0)
    r = run_pipeline(Request(topic=EN_TEXT), get_sample_claims("sleep"), voice=measured)
    assert r.planning_wpm == 200.0
    assert r.selection.w_target == pytest.approx(200.0 * 90 / 60)             # W_target = wpm * T / 60


def test_speaking_speed_scales_the_planned_script_length():
    slow, fast = run(EN_TEXT, "sleep", "en-aria", 0.8), run(EN_TEXT, "sleep", "en-aria", 1.2)
    assert slow.planning_wpm == pytest.approx(VOICE_WPM * 0.8) and fast.planning_wpm == pytest.approx(VOICE_WPM * 1.2)
    assert slow.selection.words < fast.selection.words
    assert slow.voice_speed == 0.8 and fast.voice_profile.voice_id == "en-aria"


@pytest.mark.parametrize("speed", [SPEED_MIN - 0.05, SPEED_MAX + 0.05])
def test_out_of_range_speed_is_an_error_not_a_silent_clamp(speed):
    with pytest.raises(ValueError):
        run(EN_TEXT, "sleep", "en-aria", speed)


def test_stage_log_names_the_voice_and_says_when_the_rate_is_assumed():
    summary = run(EN_TEXT, "sleep", "en-guy", 1.1).stages[3].summary
    assert "voice Guy" in summary and "x1.1" in summary and "(assumed)" in summary
    measured = VoiceProfile("en-m", "Meas", "en", "en-US", "male", "edge-tts", "en-US-MNeural", measured_wpm=170.0)
    ok = run_pipeline(Request(topic=EN_TEXT), get_sample_claims("sleep"), voice=measured)
    assert "(assumed)" not in ok.stages[3].summary and "170 wpm" in ok.stages[3].summary


# ------------------------------------------------------------------ Vietnamese end to end
@pytest.mark.parametrize("pack, voice", [("sleep_vi", "vi-hoaimy"), ("inflation_vi", "vi-namminh")])
def test_vietnamese_voice_with_vietnamese_narration_builds_a_valid_timeline(pack, voice):
    r = run(VI_TEXT, pack, voice)
    assert r.ok and r.voice_profile.language == "vi"
    tl = r.timeline
    assert 6 <= len(r.scenes) <= 30 and 60 <= tl.total_s <= 120 and tl.deviation <= 0.05     # S12, S13
    assert "Hoài My" in result_summary(r) or "Nam Minh" in result_summary(r)


def test_vietnamese_request_text_is_understood_by_the_router():
    r = run(VI_TEXT, "sleep_vi", "vi-hoaimy")
    assert r.decision.t_target == 90 and r.decision.fmt.value == "INFOGRAPHIC"


# ------------------------------------------------------------------ language mismatch
@pytest.mark.parametrize("pack, voice, spoken, wanted", [("sleep_vi", "en-aria", "vi", "en"),
                                                         ("sleep", "vi-hoaimy", "en", "vi"),
                                                         ("inflation", "vi-namminh", "en", "vi")])
def test_a_voice_of_the_wrong_language_stops_the_run_before_planning(pack, voice, spoken, wanted):
    r = run(EN_TEXT, pack, voice)
    assert r.status == PipelineStatus.VOICE_LANGUAGE_MISMATCH and r.stopped_at == Stage.VOICE
    assert [(s.stage, s.ok) for s in r.stages] == [(Stage.ROUTER, True), (Stage.VOICE, False)]
    assert r.scenes == [] and r.optimize is None and r.timeline is None
    assert spoken in r.stages[-1].summary and wanted in r.stages[-1].summary
    assert r.messages and "claim pack" in r.messages[-1]


def test_router_rejection_comes_before_the_voice_check():
    r = run("Make a 300-second video about sleep", "sleep_vi", "en-aria")
    assert r.status == PipelineStatus.ROUTER_REJECTED


def test_no_claims_means_nothing_to_compare_and_the_scene_check_reports_it():
    r = run_pipeline(Request(topic=EN_TEXT), [], voice=LIB.get("vi-hoaimy"))
    assert r.status == PipelineStatus.SCENES_INVALID


# ------------------------------------------------------------------ the simulated TTS follows the voice
def test_default_simulated_tts_speaks_at_the_voices_planned_rate():
    """With no explicit tts, MockTTS true_wpm == planning wpm, so a faster voice yields shorter scenes."""
    slow, fast = run(EN_TEXT, "sleep", "en-aria", 0.9), run(EN_TEXT, "sleep", "en-aria", 1.1)
    assert fast.timeline.total_s / len(fast.scenes) < slow.timeline.total_s / len(slow.scenes)


# ------------------------------------------------------------------ UI helpers
def test_voice_option_label_and_caption():
    v = LIB.get("vi-hoaimy")
    assert voice_option_label(v) == "Hoài My — female, vi-VN"
    assert voice_caption(v, 1.0) == f"Planned at {VOICE_WPM:.0f} words/min (assumed, not measured yet)."
    m = VoiceProfile("en-m", "M", "en", "en-US", "male", "edge-tts", "x", measured_wpm=180.0)
    assert voice_caption(m, 1.0) == "Planned at 180 words/min (measured)."
    assert voice_caption(m, 1.1).startswith("Planned at 198 ")


def test_voice_library_rows_one_per_voice_with_a_single_default_per_language():
    rows = voice_library_rows(LIB)
    assert len(rows) == len(LIB)
    for lang in LIB.languages():
        assert sum(r["default"] == "★" for r in rows if r["language"] == lang) == 1
    assert {r["language"] for r in voice_library_rows(LIB, "vi")} == {"vi"}
    assert {r["wpm source"] for r in rows} == {"assumed"}


def test_voice_info_reports_the_voice_speed_and_that_durations_are_simulated():
    info = voice_info(run(EN_TEXT, "sleep", "en-guy", 1.2))
    assert "Guy" in info and "×1.2" in info and "198 words/min" in info and "simulated" in info


# ------------------------------------------------------------------ CLI
def test_cli_runs_with_a_vietnamese_voice(capsys):
    code = cli.main([VI_TEXT, "--topic", "sleep_vi", "--voice", "vi-hoaimy"])
    out = capsys.readouterr().out
    assert code == 0 and "Status : OK" in out
    assert "voice: Hoài My · female · vi-VN (id vi-hoaimy), speed x1" in out and "(assumed, not measured)" in out


def test_cli_reports_a_language_mismatch_with_a_failing_exit_code(capsys):
    code = cli.main([EN_TEXT, "--topic", "sleep", "--voice", "vi-hoaimy"])
    assert code == 1 and "VOICE_LANGUAGE_MISMATCH" in capsys.readouterr().out


def test_cli_rejects_unknown_voices_and_bad_speeds(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main([EN_TEXT, "--voice", "nope"])
    assert exc.value.code == 2 and "unknown voice" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        cli.main([EN_TEXT, "--voice", "en-aria", "--speed", "3"])


def test_cli_without_a_voice_prints_no_voice_line(capsys):
    assert cli.main([EN_TEXT]) == 0
    assert "voice:" not in capsys.readouterr().out
