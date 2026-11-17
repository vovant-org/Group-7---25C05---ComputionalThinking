"""Tests of the pure UI layer: HTML components (escaping, states) and the studio logic (request,
validation, estimate, stage mapping, projects, tracks, storyboard). No Streamlit needed."""
import json

import pytest

from core.models import OutputFormat
from modules.pipeline.pipeline import PipelineStatus, run_pipeline
from modules.pipeline.sample_claims import get_sample_claims
from modules.router.intent_parser import parse_intent_v3
from modules.router.router import Request
from modules.voice_library.library import builtin_library
from ui import components as C
from ui import studio_logic as L

LIB = builtin_library()
ARIA, HOAIMY = LIB.get("en-aria"), LIB.get("vi-hoaimy")
OKAY = dict(ffmpeg_ok=True, edge_ok=True, system_ok=True, allow_online=False)


# ------------------------------------------------------------------ components
def test_every_text_is_escaped():
    evil = '<script>alert("x")</script>'
    pieces = [C.badge(evil), C.metric_card(evil, evil, evil), C.empty_state("i", evil, evil), C.error_box(evil, evil),
              C.hero(evil, evil), C.format_card(evil, evil, "i", note=evil), C.voice_card(evil, evil, evil, rate_note=evil),
              C.example_card("i", evil, evil), C.budget_card(1, 2, "ok", evil, evil), C.logo(evil), C.user_chip(evil, evil),
              C.progress_tracker([{"title": evil, "state": "done", "detail": evil}]),
              C.storyboard_card({"number": 1, "title": evil, "narration": evil, "visual": evil, "layout": evil,
                                 "duration_s": 3.0, "mode": evil, "claims": [evil]}),
              C.timeline_tracks({"video": [{"start": 0, "end": 5, "label": evil, "short": evil, "mode": "PAN"}]}, 5)]
    assert all("<script>" not in p for p in pieces)


def test_selected_and_unavailable_format_cards_look_different():
    on, off = C.format_card("A", "d", "i", selected=True), C.format_card("B", "d", "i", available=False)
    assert "sel" in on and "Selected" in on and "off" in off and "Not available yet" in off


def test_budget_card_states():
    assert "Within budget" in C.budget_card(10, 20, "ok", "m") and "50%" in C.budget_card(10, 20, "ok", "m")
    assert "Over budget" in C.budget_card(None, 5, "over", "m")
    assert "Not estimated" in C.budget_card(None, None, "unknown", "m")
    assert "width:100%" in C.budget_card(30, 20, "over", "m")           # the bar never overflows


def test_progress_tracker_counts_only_confirmed_steps():
    html = C.progress_tracker([{"title": "A", "state": "done"}, {"title": "B", "state": "run"},
                               {"title": "C", "state": "pending"}, {"title": "D", "state": "fail", "detail": "x"}])
    assert "1 of 4 steps confirmed" in html and "width:25%" in html


def test_timeline_tracks_has_three_lanes_and_marks_silence():
    tracks = {"video": [{"start": 0, "end": 5, "label": "s0", "short": "0", "mode": "PAN"}],
              "audio": [{"start": 0, "end": 5, "label": "a", "short": "", "silent": True}],
              "subtitles": [{"start": 0, "end": 2, "label": "t", "short": ""}]}
    html = C.timeline_tracks(tracks, 10)
    assert all(n in html for n in ("Video", "Audio", "Subtitles")) and "repeating-linear-gradient" in html
    assert "left:0.000%;width:50.000%" in html and C.timeline_tracks(tracks, 0) == ""


# ------------------------------------------------------------------ request composition
@pytest.mark.parametrize("fmt, lang, expect_fmt", [("INFOGRAPHIC", "en", OutputFormat.INFOGRAPHIC),
                                                    ("ANIMATION", "en", OutputFormat.ANIMATION),
                                                    ("INFOGRAPHIC", "vi", OutputFormat.INFOGRAPHIC),
                                                    ("ANIMATION", "vi", OutputFormat.ANIMATION)])
def test_composed_request_is_read_back_by_the_router_parser(fmt, lang, expect_fmt):
    text = L.compose_request("Explain How the Internet Works" if lang == "en" else "Mạng Internet hoạt động ra sao",
                             fmt, 75, lang, "Keep it friendly")
    intent = parse_intent_v3(text)
    assert intent.t_target == 75 and intent.fmt == expect_fmt and not intent.ambiguous_format, text


def test_instructions_are_appended_and_whitespace_is_normalised():
    assert L.compose_request("  sleep \n tips ", "INFOGRAPHIC", 90, "en", "  be   brief ").endswith("Topic: sleep tips. be brief")
    assert L.compose_request("sleep", "INFOGRAPHIC", 90, "en") == "Make a 90-second infographic video. Topic: sleep"


def test_resolve_claims_from_pack_and_from_reference():
    claims, lang = L.resolve_claims("pack", "sleep_vi", "ignored")
    assert len(claims) == 16 and lang == "vi"
    ref = " ".join(f"Sentence number {i} explains one more useful fact about the topic in plain words." for i in range(8))
    claims, lang = L.resolve_claims("reference", None, ref)
    assert len(claims) == 8 and lang == "en" and L.resolve_claims("reference", None, "  ") == ([], None)


# ------------------------------------------------------------------ validation
def issues(**kw):
    base = dict(idea="sleep", fmt_key="INFOGRAPHIC", source="pack", pack="sleep", reference="", voice=ARIA, engine="silent", **OKAY)
    return L.validate_config(**{**base, **kw})


def errors(**kw):
    return [i.message for i in L.blocking(issues(**kw))]


def test_a_complete_form_has_no_blocking_issue_and_silence_is_only_a_warning():
    found = issues()
    assert not L.blocking(found) and [i.kind for i in found] == ["warning"]


@pytest.mark.parametrize("kw, word", [({"idea": "  "}, "topic"), ({"fmt_key": "HYBRID"}, "not built"),
                                      ({"source": "reference", "reference": ""}, "reference"),
                                      ({"pack": None}, "claim pack"), ({"pack": "sleep_vi"}, "Tiếng Việt"),
                                      ({"ffmpeg_ok": False}, "FFmpeg"),
                                      ({"engine": "edge", "allow_online": False}, "online"),
                                      ({"engine": "edge", "edge_ok": False, "allow_online": True}, "edge-tts"),
                                      ({"engine": "system", "system_ok": False}, "pyttsx3")])
def test_each_problem_is_reported_in_words(kw, word):
    assert any(word in m for m in errors(**kw)), errors(**kw)


def test_reference_text_checks():
    short = "Only one usable sentence exists in this text so far and it is alone here."
    assert any("usable sentence" in m for m in errors(source="reference", reference=short))
    vi = " ".join(f"Giấc ngủ giúp não bộ sắp xếp ký ức và hồi phục cơ thể sau một ngày dài số {i}." for i in range(8))
    assert any("Tiếng Việt" in m for m in errors(source="reference", reference=vi))      # English voice, Vietnamese text
    assert any("1,500" in m for m in errors(idea="word " * 1501))


# ------------------------------------------------------------------ estimate with the real Budget Optimizer
def test_estimate_of_a_normal_plan_is_ok_and_matches_the_pipeline():
    text = L.compose_request("sleep", "INFOGRAPHIC", 90, "en")
    est = L.estimate_plan(text, get_sample_claims("sleep"), fmt_key="INFOGRAPHIC", duration_s=90, budget=None, voice=ARIA, speed=1.0)
    ref = run_pipeline(Request(topic=text, output_format=OutputFormat.INFOGRAPHIC, t_target=90),
                       get_sample_claims("sleep"), voice=ARIA)
    assert est.status == "ok" and est.cost == ref.optimize.total_cost and est.budget == ref.budget
    assert est.scenes == len(ref.scenes) and "automatic" in est.budget_source


def test_a_too_small_budget_is_over_budget_with_the_optimizers_reason():
    text = L.compose_request("sleep", "INFOGRAPHIC", 90, "en")
    est = L.estimate_plan(text, get_sample_claims("sleep"), fmt_key="INFOGRAPHIC", duration_s=90, budget=3, voice=ARIA, speed=1.0)
    assert est.status in ("over", "unknown") and est.cost is None and est.message


def test_estimate_without_claims_or_with_a_wrong_language_is_unknown():
    assert L.estimate_plan("x", [], fmt_key="INFOGRAPHIC", duration_s=90, budget=None, voice=ARIA, speed=1.0).status == "unknown"
    est = L.estimate_plan("x", get_sample_claims("sleep_vi"), fmt_key="INFOGRAPHIC", duration_s=90, budget=None, voice=ARIA, speed=1.0)
    assert est.status == "unknown" and "Tiếng Việt" in est.message


def test_estimate_of_animation_uses_only_modes_that_can_be_built():
    text = L.compose_request("sleep", "ANIMATION", 90, "en")
    est = L.estimate_plan(text, get_sample_claims("sleep"), fmt_key="ANIMATION", duration_s=90, budget=None, voice=ARIA, speed=1.0)
    assert est.status == "ok" and est.cost and est.cost < 14 * est.scenes        # no CLIP clips planned


# ------------------------------------------------------------------ the seven steps
def planned(**kw):
    text = L.compose_request("sleep", "INFOGRAPHIC", 90, "en")
    return run_pipeline(Request(topic=text, output_format=OutputFormat.INFOGRAPHIC, t_target=90), get_sample_claims("sleep"),
                        voice=ARIA, **kw)


def states(steps):
    return [s["state"] for s in steps]


def test_nothing_is_confirmed_before_the_backend_answers():
    assert states(L.stage_cards(None)) == ["pending"] * 7
    assert states(L.stage_cards(None, started=True)) == ["run"] + ["pending"] * 6
    assert L.stage_cards(None, error="boom")[0]["state"] == "fail"


def test_a_planned_run_confirms_six_steps_and_leaves_verification_pending():
    res = planned()
    assert res.ok and states(L.stage_cards(res)) == ["done"] * 6 + ["pending"]
    assert states(L.stage_cards(res, render_frac=0.4))[-1] == "run"
    assert "40%" in L.stage_cards(res, render_frac=0.4)[-1]["detail"]


def test_verification_is_done_only_with_a_report_and_fails_when_a_check_fails():
    res = planned()
    good = {"criteria": {"S12": {"pass": True, "detail": ""}, "S13": {"pass": True, "detail": ""}}}
    bad = {"criteria": {"S12": {"pass": True, "detail": ""}, "S13": {"pass": False, "detail": ""}}}
    assert L.stage_cards(res, report=good)[-1]["state"] == "done"
    last = L.stage_cards(res, report=bad)[-1]
    assert last["state"] == "fail" and "S13" in last["detail"]


def test_a_stopped_run_marks_the_failing_step_and_keeps_the_rest_pending():
    res = run_pipeline(Request(topic="Make a 90-second infographic video", output_format=OutputFormat.INFOGRAPHIC, t_target=90),
                       get_sample_claims("sleep_vi"), voice=ARIA)
    assert res.status == PipelineStatus.VOICE_LANGUAGE_MISMATCH
    steps = L.stage_cards(res)
    assert states(steps)[0] == "done" and steps[4]["state"] == "fail" and states(steps)[5:] == ["pending", "pending"]
    assert steps[1]["state"] == "pending"                      # nothing was planned


def test_a_budget_failure_stops_at_step_four():
    res = run_pipeline(Request(topic="Make a 90-second infographic video", output_format=OutputFormat.INFOGRAPHIC, t_target=90, budget=3),
                       get_sample_claims("sleep"), voice=ARIA)
    if res.status == PipelineStatus.BUDGET_INFEASIBLE:
        s = states(L.stage_cards(res))
        assert s[:3] == ["done"] * 3 and s[3] == "fail" and s[4:] == ["pending"] * 3
    else:                                                       # the router may reject a tiny budget before planning
        assert states(L.stage_cards(res))[0] == "fail"


# ------------------------------------------------------------------ report-based data
SRT = "1\n00:00:00,000 --> 00:00:04,500\nHello there\n\n2\n00:00:05,000 --> 00:00:09,000\nSecond cue\nline two\n"
REPORT = {"format": "INFOGRAPHIC", "total_s": 10.0, "t_target": 10.0, "scenes": 2, "voice_is_silent": False,
          "claims": [{"claim_id": "SLE01", "text": "Sleep is an active process, in which the brain sorts memories."},
                     {"claim_id": "SLE02", "text": "Second claim text."}],
          "criteria": {"S12": {"pass": True, "detail": "ok"}, "S13": {"pass": False, "detail": "off"}},
          "timeline": [{"scene": 0, "start_s": 0.0, "duration_s": 5.0, "mode": "REVEAL", "layout": "cause_chain",
                        "labels": ["Sleep", "Brain"], "narration": "Sleep is an active process, in which the brain sorts memories."},
                       {"scene": 1, "start_s": 5.0, "duration_s": 5.0, "mode": "PAN", "layout": "steps", "labels": [],
                        "narration": "Second claim text."}]}


def test_parse_srt_reads_times_and_joins_lines():
    cues = L.parse_srt(SRT)
    assert [(c["start"], c["end"]) for c in cues] == [(0.0, 4.5), (5.0, 9.0)] and cues[1]["text"] == "Second cue line two"
    assert L.parse_srt("garbage") == []


def test_tracks_follow_the_timeline_and_the_cues():
    t = L.tracks_from_report(REPORT, L.parse_srt(SRT))
    assert [(c["start"], c["end"]) for c in t["video"]] == [(0.0, 5.0), (5.0, 10.0)]
    assert [c["end"] for c in t["audio"]] == [4.5, 9.0]                  # narration ends at the last cue of the scene
    assert len(t["subtitles"]) == 2 and not any(c["silent"] for c in t["audio"])
    silent = L.tracks_from_report({**REPORT, "voice_is_silent": True})
    assert all(c["silent"] for c in silent["audio"]) and silent["subtitles"][0]["label"].startswith("Sleep is")


def test_scene_cards_link_claims_and_pick_titles():
    cards = L.scene_cards(REPORT)
    assert cards[0]["title"] == "Sleep" and cards[0]["claims"] == ["SLE01"] and "Labels: Sleep | Brain" in cards[0]["visual"]
    assert cards[1]["title"] == "Second claim text" and cards[1]["claims"] == ["SLE02"]
    assert [r["scene"] for r in L.scene_table(cards)] == [0, 1]
    anim = L.scene_cards({**REPORT, "format": "ANIMATION", "timeline": [{**REPORT["timeline"][0], "pose": "wave", "prop": "bulb"}]})
    assert "pose wave" in anim[0]["visual"]


def test_headline_cuts_long_clauses():
    assert L.headline("One two three four five six seven eight nine, ten") == "One two three four five six seven…"
    assert L.headline("Short one. Next") == "Short one"


def test_check_rows():
    assert [(r["id"], r["passed"]) for r in L.check_rows(REPORT)] == [("S12", True), ("S13", False)]


# ------------------------------------------------------------------ projects on disk
def test_projects_need_a_report_and_a_video_and_come_newest_first(tmp_path):
    import os
    for name, ts in (("old", 1_000_000), ("new", 2_000_000)):
        (tmp_path / f"{name}.mp4").write_bytes(b"x")
        (tmp_path / f"{name}.report.json").write_text(json.dumps({**REPORT, "video": "D:\\elsewhere\\x.mp4"}), encoding="utf-8")
        for f in tmp_path.glob(f"{name}.*"):
            os.utime(f, (ts, ts))
    (tmp_path / "noreport.mp4").write_bytes(b"x")
    (tmp_path / "novideo.report.json").write_text(json.dumps(REPORT), encoding="utf-8")
    (tmp_path / "broken.mp4").write_bytes(b"x")
    (tmp_path / "broken.report.json").write_text("{not json", encoding="utf-8")
    found = L.list_projects(tmp_path)
    assert [p.name for p in found] == ["new", "old"] and found[0].video_path == tmp_path / "new.mp4"
    assert found[0].fmt == "INFOGRAPHIC" and found[0].scenes == 2 and found[0].srt_path is None
    assert L.list_projects(tmp_path / "missing") == []


def test_sidecar_gives_the_project_its_title(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "a.report.json").write_text(json.dumps(REPORT), encoding="utf-8")
    L.write_sidecar(tmp_path / "a.mp4", {"title": "My sleep video", "voice": "Aria"})
    p, = L.list_projects(tmp_path)
    assert p.title == "My sleep video" and p.meta["voice"] == "Aria"


def test_project_name_is_a_safe_stable_slug():
    a = L.project_name("Giấc ngủ / Sleep?!", "INFOGRAPHIC", "x")
    assert a == L.project_name("Giấc ngủ / Sleep?!", "INFOGRAPHIC", "x") and a != L.project_name("Giấc ngủ / Sleep?!", "INFOGRAPHIC", "y")
    assert all(ch.isalnum() or ch == "-" for ch in a) and L.project_name("???", "ANIMATION", "x").startswith("video-anim-")
