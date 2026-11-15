"""Tests of the pure helpers behind the Streamlit page (no streamlit needed)."""
import json
from pathlib import Path

from core.models import OutputFormat
from modules.pipeline.pipeline import PipelineStatus, run_pipeline
from modules.pipeline.sample_claims import get_sample_claims
from modules.pipeline.ui_helpers import (benchmark_summaries, chips_html, criteria_checks, legend_html,
                                         result_summary, scene_rows, timeline_bar_html, voice_rows)
from modules.router.router import Request
from modules.timeline_assembler.export import timeline_to_dict

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


def ok_run():
    return run_pipeline(Request(topic="Make a 90-second infographic video about sleep"), get_sample_claims("sleep"))


def by_id(checks):
    return {c.id: c for c in checks}


def test_checks_on_a_successful_run():
    res = ok_run()
    assert res.status == PipelineStatus.OK
    c = by_id(criteria_checks(res))
    assert {c[k].status for k in ("S11", "S12", "S13", "S14", "S18")} == {"pass"}
    assert c["S19"].status == "info"          # no threshold exists yet, so never pass/fail
    assert result_summary(res).startswith("INFOGRAPHIC")


def test_checks_on_a_router_rejection():
    res = run_pipeline(Request(topic="Make a 300-second video about sleep"), get_sample_claims("sleep"))
    assert res.status == PipelineStatus.ROUTER_REJECTED
    c = by_id(criteria_checks(res))
    assert c["S12"].status == "fail" and "300" in c["S12"].detail
    assert "S13" not in c and "S11" not in c      # nothing was built, nothing to check
    assert result_summary(res) == ""


def test_slow_voice_fails_s13_on_the_timeline():
    from modules.pipeline.pipeline import DEFAULT_TTS_PARAMS
    from modules.providers.mock_tts import MockTTS
    tts = MockTTS(**{**DEFAULT_TTS_PARAMS, "true_wpm": 120.0})
    res = run_pipeline(Request(topic="Make a 90-second infographic video about sleep"),
                       get_sample_claims("sleep"), tts=tts)
    assert res.status == PipelineStatus.TIMELINE_CHECKS_FAILED
    assert by_id(criteria_checks(res))["S13"].status == "fail"


def test_timeline_bar_and_legend():
    res = ok_run()
    bar = timeline_bar_html(res.timeline.entries)
    assert bar.count("<b style=") == len(res.timeline.entries)      # one block per scene
    assert "0s" in bar and bar.count("translateX") >= 5   # time axis, ticks never beyond the total
    assert "REVEAL" in legend_html(res.timeline.entries)
    assert timeline_bar_html([]) == ""


def test_scene_and_voice_rows():
    res = ok_run()
    rows = scene_rows(res)
    assert len(rows) == len(res.scenes) and all(r["narration"] for r in rows)
    assert rows[1]["start_s"] == round(res.timeline.entries[1].start_s, 1)
    v = voice_rows(res)
    assert len(v) == len(res.voice.units) and {r["in 10–12 s"] for r in v} <= {"✅", "❌"}
    assert voice_rows(run_pipeline(Request(topic="a 300-second video"), get_sample_claims("sleep"))) == []


def test_chips_escape_html():
    from modules.pipeline.ui_helpers import Check
    assert "<script>" not in chips_html([Check("S1", "<script>", "pass", "x")])


def test_timeline_json_has_three_tracks_and_matches_the_timeline():
    res = ok_run()
    j = timeline_to_dict(res.timeline)
    json.dumps(j)                                                   # serialisable
    n = len(res.timeline.entries)
    assert {len(j["tracks"][t]) for t in ("video", "audio", "subtitle")} == {n}
    assert j["fps"] == 24 and j["resolution"] == [1280, 720]
    last = j["tracks"]["video"][-1]
    assert abs(last["end_s"] - res.timeline.total_s) < 1e-3
    for a, v in zip(j["tracks"]["audio"], j["tracks"]["video"]):    # narration never outlasts its scene
        assert a["start_s"] == v["start_s"] and a["end_s"] <= v["end_s"] + 1e-3


def test_benchmark_summaries_reproduce_the_iteration_logs():
    s = benchmark_summaries(OUTPUTS)
    score = {k: dict(zip(df["algorithm"], df["score"])) for k, df in s.items()}
    assert round(score["budget"]["v1_dp_post_check"], 3) == 0.886 and score["budget"]["v2_dp_motion_state"] == 1.0
    assert round(score["router"]["v0_policy_table"] * 55) == 27 and score["router"]["v3_hardened"] == 1.0
    assert round(score["voice"]["F1_greedy"], 3) == 0.253 and round(score["voice"]["F4_dp_share"], 3) == 0.350
    assert round(score["scene"]["D1_greedy"], 3) == 0.654 and round(score["scene"]["D2f_mmr_facet"], 3) == 0.880


def test_benchmark_summaries_tolerate_missing_files(tmp_path):
    assert benchmark_summaries(tmp_path) == {}
