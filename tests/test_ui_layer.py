"""Tests of the UI layer's pure logic (ui/adapters, ui/components, ui/storage, ui/theme, ui/runner estimate).

No Streamlit and no FFmpeg are needed. The key property under test: the progress tracker and the cost card
only ever say what the backend result says (a stage is never "done" without a backend confirmation).
"""
import json
import tempfile
from pathlib import Path

from ui import adapters as A
from ui import components as C
from ui import runner, storage
from ui.theme import CSS, LIGHT_CSS, LIGHT_TOKENS, TOKENS, css_for

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _stage(name, ok=True, summary="x"):
    return {"stage": name, "ok": ok, "summary": summary}


def _facts(**kw):
    base = {"stages": [], "messages": [], "status": "OK", "format": "INFOGRAPHIC", "t_target": 90, "word_count": 20, "router_codes": [],
            "claims_selected": None, "claims_available": 16, "selection_algorithm": "D2f", "n_scenes": None, "est_total_s": None,
            "budget": None, "budget_source": "", "cost": None, "motion_ratio": None, "voice_units": None, "voice_in_band": None,
            "timeline_built": False, "timeline_total_s": None, "deviation": None, "timeline_codes": []}
    base.update(kw)
    return base


def _states(stages):
    return {s["key"]: s["state"] for s in stages}


# ------------------------------------------------------------------------------------ stage tracker
def test_seven_stages_in_the_order_of_the_brief():
    assert [s["title"] for s in A.stage_view(None)] == ["Understanding Request", "Planning Story", "Organizing Scenes", "Optimizing Budget",
                                                        "Generating Narration", "Assembling Timeline", "Verifying Output"]
    assert set(_states(A.stage_view(None)).values()) == {"pending"}


def test_nothing_is_done_without_backend_confirmation():
    # router accepted, nothing else ran: only the first stage may be done
    f = _facts(stages=[_stage("router")])
    st = _states(A.stage_view(f))
    assert st["understanding"] == "done" and all(v == "pending" for k, v in st.items() if k != "understanding")


def test_router_rejection_stops_the_tracker_at_stage_one():
    f = _facts(stages=[_stage("router", False)], messages=["Duration 300 s is outside 60-120 s."], status="ROUTER_REJECTED")
    sv = A.stage_view(f)
    assert sv[0]["state"] == "failed" and "300 s" in sv[0]["detail"]
    assert all(s["state"] == "pending" for s in sv[1:])


def test_budget_infeasible_marks_only_the_budget_stage_failed():
    f = _facts(stages=[_stage("router"), _stage("scene_segmenter"), _stage("budget_optimizer", False)], claims_selected=12, n_scenes=12,
               messages=["minimum cost 36 > budget 10"], status="BUDGET_INFEASIBLE")
    st = _states(A.stage_view(f))
    assert st["understanding"] == st["planning"] == st["scenes"] == "done" and st["budget"] == "failed"
    assert st["narration"] == st["timeline"] == st["verify"] == "pending"


def test_full_success_and_the_render_gate():
    logs = [_stage("router"), _stage("scene_segmenter"), _stage("budget_optimizer"), _stage("voice_segmenter"), _stage("timeline_assembler")]
    f = _facts(stages=logs, claims_selected=12, n_scenes=12, cost=36, budget=72, motion_ratio=1.0, voice_units=8, timeline_built=True,
               timeline_total_s=89.0, deviation=0.01)
    ok = A.stage_view(f, video_ok=True, criteria={"S12": {"pass": True}, "S13": {"pass": True}})
    assert set(_states(ok).values()) == {"done"}
    failed = _states(A.stage_view(f, video_ok=False, error="ffmpeg failed"))
    assert failed["timeline"] == "failed" and failed["verify"] == "pending" and failed["narration"] == "done"
    warn = _states(A.stage_view(f, video_ok=True, criteria={"S12": {"pass": True}, "S13": {"pass": False}}))
    assert warn["verify"] == "warning"


def test_without_the_video_the_timeline_stage_is_not_claimed_done():
    logs = [_stage("router"), _stage("scene_segmenter"), _stage("budget_optimizer"), _stage("voice_segmenter"), _stage("timeline_assembler")]
    f = _facts(stages=logs, claims_selected=12, timeline_built=True, timeline_total_s=88.0, deviation=0.0)
    st = _states(A.stage_view(f))                       # video_ok unknown
    assert st["timeline"] == "pending" and st["verify"] == "pending"


def test_silent_engine_is_stated_in_the_narration_detail():
    logs = [_stage("router"), _stage("scene_segmenter"), _stage("budget_optimizer"), _stage("voice_segmenter")]
    f = _facts(stages=logs, claims_selected=6, voice_units=7, timeline_built=True)
    assert "no sound" in A.stage_view(f, silent=True)[4]["detail"]


# -------------------------------------------------------------------------------------- cost estimate
def test_estimate_states():
    assert A.estimate_from_facts(None)["status_key"] == "pending"
    ok = A.estimate_from_facts(_facts(cost=36, budget=72, budget_source="auto", n_scenes=12, claims_selected=12, motion_ratio=1.0))
    assert ok["status_key"] == "within" and ok["can_start"] and ok["cost"] == 36
    low = A.estimate_from_facts(_facts(status="ROUTER_REJECTED", router_codes=["BUDGET_BELOW_MIN"], messages=["Budget 3 < minimum 36"]))
    assert low["status_text"] == "Budget too low" and not low["can_start"]
    mismatch = A.estimate_from_facts(_facts(status="VOICE_LANGUAGE_MISMATCH", messages=["wrong voice"]))
    assert mismatch["blocking"] and not mismatch["can_start"]
    timing = A.estimate_from_facts(_facts(status="TIMELINE_CHECKS_FAILED", cost=36, budget=72))
    assert timing["can_start"] and timing["messages"]       # simulated timing only: real run adjusts it


def test_real_pipeline_estimate_uses_the_budget_optimizer():
    f = runner.estimate_plan("Why sleep matters", "", "", "demo", "sleep", "INFOGRAPHIC", 90, None, "en-aria", 1.0)
    e = A.estimate_from_facts(f)
    assert f["status"] == "OK" and e["can_start"] and e["cost"] is not None and e["budget"] >= e["cost"]
    tiny = A.estimate_from_facts(runner.estimate_plan("Why sleep matters", "", "", "demo", "sleep", "ANIMATION", 90, 3, "en-aria", 1.0))
    assert tiny["status_text"] == "Budget too low" and not tiny["can_start"]
    long = A.estimate_from_facts(runner.estimate_plan("Why sleep matters", "", "", "demo", "sleep", "INFOGRAPHIC", 300, None, "en-aria", 1.0))
    assert not long["can_start"]


# -------------------------------------------------------------------------------------- validation
def _validate(**kw):
    base = dict(topic="Why sleep matters", instructions="", reference="", source="demo", claims_text=["x y"], voice_language="en", ffmpeg_ok=True,
                engine_kind="system")
    base.update(kw)
    return A.validate_inputs(**base)


def test_validation_messages_block_only_real_problems():
    assert not A.has_blocking(_validate())
    assert A.has_blocking(_validate(topic="  "))
    assert A.has_blocking(_validate(ffmpeg_ok=False))
    assert A.has_blocking(_validate(source="text", reference="", claims_text=[]))
    assert A.has_blocking(_validate(source="text", reference="Short.", claims_text=[]))
    assert A.has_blocking(_validate(topic="word " * 1501))
    assert A.has_blocking(_validate(detected_language="vi"))
    assert A.has_blocking(_validate(engine_kind="edge", online_ok=False))
    assert not A.has_blocking(_validate(engine_kind="silent"))                       # silent is an info note, not an error
    assert any(m["level"] == "info" for m in _validate(engine_kind="silent"))


def test_word_limit_is_exactly_the_routers():
    assert not A.has_blocking(_validate(topic="word " * 1500))
    assert A.has_blocking(_validate(topic="word " * 1500, instructions="one"))


# -------------------------------------------------------------------------------------- srt + labels
SRT = "1\n00:00:00,000 --> 00:00:04,500\nHello there\n\n2\n00:00:04,500 --> 00:01:05,250\nSecond cue\nwith two lines\n\nbroken block\n"


def test_parse_srt():
    cues = A.parse_srt(SRT)
    assert len(cues) == 2 and cues[0] == {"text": "Hello there", "start_s": 0.0, "end_s": 4.5}
    assert cues[1]["text"] == "Second cue with two lines" and abs(cues[1]["end_s"] - 65.25) < 1e-9


def test_layout_and_pattern_names():
    assert A.layout_name("cutout:bulb") == "Cut-out · idea" and A.layout_name("cause_chain") == "Cause chain" and A.layout_name(None) == "Character scene"
    assert A.pattern_name("step_by_step") == "Step by step" and A.pattern_name("odd_new") == "Odd New"


def test_humanize_age():
    assert A.humanize_age(1000, now=1010) == "just now" and A.humanize_age(1000, now=1000 + 300) == "5 min ago"
    assert A.humanize_age(0, now=7200) == "2 h ago" and A.humanize_age(0, now=86400 * 2) == "2 days ago"


# ---------------------------------------------------------------------------- storyboard + timeline
REPORT = {"format": "INFOGRAPHIC", "total_s": 20.0, "t_target": 20, "deviation": 0.0, "scenes": 2, "request": "r", "claims": [{"claim_id": "C1", "text": "Claim one."}],
          "timeline": [{"scene": 0, "start_s": 0.0, "duration_s": 10.0, "mode": "REVEAL", "layout": "cause_chain", "labels": ["A", "B"], "narration": "n0"},
                       {"scene": 1, "start_s": 10.0, "duration_s": 10.0, "mode": "PAN", "layout": "big_number", "labels": [], "narration": "n1"}]}
RECORD = {"scenes": [{"scene": 0, "claim_ids": ["C1"], "explain_pattern": "cause_effect", "facet": "x", "cost": 3, "audio_s": 8.0},
                     {"scene": 1, "claim_ids": [], "explain_pattern": "analogy", "audio_s": 9.5}], "claims": [{"claim_id": "C1", "text": "Claim one."}]}


def test_storyboard_uses_only_recorded_data():
    sb = A.storyboard_scenes(REPORT, RECORD)
    assert [s["number"] for s in sb] == [1, 2] and sb[0]["title"] == "Cause → effect" and sb[0]["visual"] == "On-screen text: A | B"
    assert sb[0]["claims"] == [{"claim_id": "C1", "text": "Claim one."}] and not sb[0]["evidence_missing"]
    legacy = A.storyboard_scenes(REPORT, None)                         # no UI record: say so instead of guessing
    assert all(s["evidence_missing"] and s["claims"] == [] for s in legacy)


def test_timeline_tracks_come_from_real_times():
    sb = A.storyboard_scenes(REPORT, RECORD)
    cues = [{"text": "t", "start_s": 0.0, "end_s": 8.0}, {"text": "u", "start_s": 10.0, "end_s": 19.0}]
    tl = A.timeline_data(sb, cues, RECORD)
    assert tl["video"][1] == {"scene": 2, "start_s": 10.0, "end_s": 20.0, "mode": "PAN"} and tl["total_s"] == 20.0
    assert tl["audio"][0]["end_s"] == 8.0 and tl["audio"][1]["end_s"] == 19.5       # from the record
    from_cues = A.timeline_data(sb, cues, None)["audio"]                              # no record: span of the scene's cues
    assert from_cues[0]["end_s"] == 8.0 and from_cues[1]["end_s"] == 19.0


def test_bundled_sample_project_can_be_read():
    folder = PROJECT_ROOT / "outputs" / "videos"
    if not (folder / "sleep.report.json").exists():
        return
    view = storage.load_project("sleep", folder)
    sb = A.storyboard_scenes(view["report"], view["record"])
    tl = A.timeline_data(sb, view["cues"], view["record"])
    assert len(sb) == view["report"]["scenes"] == len(tl["video"]) and tl["subtitles"] and abs(tl["total_s"] - view["report"]["total_s"]) < 1.0


# ---------------------------------------------------------------------------------------- storage
def test_storage_lists_newest_first_and_skips_broken_reports():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "a.report.json").write_text(json.dumps(dict(REPORT, request="first", criteria={"S12": {"pass": True}})), encoding="utf-8")
        (d / "b.report.json").write_text("{not json", encoding="utf-8")
        (d / "c.report.json").write_text(json.dumps({"no": "timeline"}), encoding="utf-8")
        assert [p["id"] for p in storage.list_projects(d)] == ["a"]
        assert storage.list_projects(d)[0]["has_video"] is False and storage.list_projects(d)[0]["checks"] == (1, 1)
        storage.save_record("a", {"title": "My title", "voice": {"name": "Aria"}}, d)
        p = storage.list_projects(d)[0]
        assert p["title"] == "My title" and p["voice"] == "Aria" and p["made_with_ui"]
        assert storage.load_project("a", d)["video_path"] is None and storage.load_project("zzz", d) is None
    assert storage.list_projects(Path("/definitely/not/here")) == []
    assert storage.project_key("a", 1) == storage.project_key("a", 1) != storage.project_key("a", 2)


# ------------------------------------------------------------------------------------ components
def test_components_escape_user_text_and_dollars():
    out = C.scene_card({"scene": 1, "title": "<b>x</b>", "narration": "costs $5 and $6 <script>", "visual": "v", "layout": "l", "mode": "PAN",
                        "start_s": 0, "duration_s": 5, "claims": [{"claim_id": "<i>", "text": ""}]})
    assert "<script>" not in out and "<b>x</b>" not in out and "$" not in out and "&#36;5" in out


def test_component_html_is_one_line_without_blank_lines():
    samples = [C.brand(), C.format_card("T", "d", ["a", "b"], "infographic", selected=True), C.voice_card("Aria", "English", ["Female"], True),
               C.budget_card({"status_key": "within", "status_text": "ok", "cost": 3, "budget": 6}), C.progress_tracker(A.stage_view(None), "h", "s"),
               C.timeline_tracks([{"scene": 1, "start_s": 0, "end_s": 5, "mode": "PAN"}], [], [], 5), C.empty_state("t", "x"), C.alert("err", "t", "x"),
               C.property_panel(None, {}), C.storyboard_preview("t", "x")]
    for s in samples:
        assert "\n" not in s and not s.startswith(" ")


def test_budget_card_never_divides_by_zero_and_clamps():
    assert "width:100%" in C.budget_card({"status_key": "over", "cost": 50, "budget": 10})
    assert "—" in C.budget_card({"status_key": "pending"})
    assert "/ 0" not in C.budget_card({"status_key": "within", "cost": 5, "budget": 0})


def test_timeline_marks_silent_audio_and_the_selected_scene():
    html = C.timeline_tracks([{"scene": 1, "start_s": 0, "end_s": 5, "mode": "PAN"}, {"scene": 2, "start_s": 5, "end_s": 10, "mode": "REVEAL"}],
                             [{"scene": 1, "start_s": 0, "end_s": 4}], [{"text": "hi", "start_s": 0, "end_s": 2}], 10, selected_scene=2, silent=True)
    assert "audio silent" in html and "sel" in html and "narration (silent)" in html


def test_progress_tracker_draws_state_classes_and_waiting_label():
    html = C.progress_tracker([{"title": "A", "state": "done"}, {"title": "B", "state": "failed", "detail": "boom"}, {"title": "C", "state": "pending"}])
    assert "sf-step done" in html and "sf-step failed" in html and "boom" in html and "Not reached" in html
    assert "Waiting" in C.progress_tracker([{"title": "C", "state": "pending"}], pending_label="Waiting")


def test_unavailable_format_card_says_coming_soon_and_is_dimmed():
    out = C.format_card("Hybrid", "d", ["x"], "hybrid", available=False)
    assert "Coming soon" in out and "disabled" in out


# ------------------------------------------------------------------------------------------ theme
def test_theme_uses_the_palette_of_the_brief():
    expected = {"bg": "#0B0D12", "bg2": "#121620", "card": "#181E2A", "accent": "#8B5CF6", "accent2": "#06B6D4", "text": "#F8FAFC",
                "muted": "#94A3B8", "border": "#293244", "success": "#22C55E", "warning": "#F59E0B", "error": "#EF4444"}
    assert TOKENS == expected
    for value in expected.values():
        assert value.lower() in CSS.lower() or value.upper() in CSS
    cfg = (PROJECT_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert '"#8B5CF6"' in cfg and '"#0B0D12"' in cfg


def test_stepper_marks_done_current_and_pending_steps():
    html = C.stepper(["Question", "Format", "Voice", "Budget"], 3)
    assert html.count("sf-wiz-step done") == 2 and html.count("sf-wiz-step on") == 1
    assert html.count('class="sf-wiz-step ') == 4 and html.count("sf-wiz-line") == 3
    assert "<br" not in html and "\n" not in html


def test_stepper_escapes_labels():
    assert "<script>" not in C.stepper(["<script>alert(1)</script>"], 1)


def test_dark_is_the_default_and_light_adds_its_palette():
    assert css_for("dark") == CSS and css_for() == CSS and css_for("nonsense") == CSS
    light = css_for("light")
    assert light.startswith(CSS) and light.endswith(LIGHT_CSS)
    for key in ("bg", "card", "text", "muted", "border"):
        assert LIGHT_TOKENS[key] in LIGHT_CSS
    assert LIGHT_TOKENS["bg"] != TOKENS["bg"] and LIGHT_TOKENS["text"] != TOKENS["text"]


def test_dark_css_has_no_fixed_button_colours_left():
    assert "#1e2230 !important" not in CSS and "var(--sf-btn-bg)" in CSS


def test_wizard_stepper_does_not_reuse_the_progress_trackers_class_names():
    wiz = C.stepper(["A", "B"], 1)
    tracker = C.progress_tracker([{"title": "T", "desc": "d", "state": "running"}], "h")
    assert 'class="sf-step ' not in wiz and 'class="sf-steps"' not in wiz and "sf-wiz" in wiz
    assert 'class="sf-steps"' in tracker and 'class="sf-step running"' in tracker
    assert ".sf-wiz-step" in CSS and ".sf-wiz{" in CSS
    assert ".sf-steps{display:flex;align-items:center" not in CSS          # the old wizard rule that bent the tracker
