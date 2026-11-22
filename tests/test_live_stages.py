"""Live progress of a video being made: the backend reports each stage as it happens (on_stage) and the UI folds
those events into seven steps. A step is Working from its start event and Done only when the backend says so."""
from pathlib import Path

import pytest

from modules.pipeline.pipeline import run_pipeline
from modules.pipeline.sample_claims import get_sample_claims
from modules.router.router import Request
from modules.video.make_video import make_video
from modules.video.voice import make_engine
from modules.voice_library.library import builtin_library
from ui.adapters import STAGES, LiveStages

KEYS = [k for k, _, _ in STAGES]
SLEEP = get_sample_claims("sleep")
TEXT = "Make a 90-second infographic video about sleep"


def states(live: LiveStages) -> dict:
    return {s["key"]: s["state"] for s in live.view()}


def feed(live: LiveStages, events) -> LiveStages:
    for e in events:
        live.update(*e)
    return live


# --------------------------------------------------------------------------------------- the backend events
def test_pipeline_reports_every_stage_in_order():
    seen = []
    res = run_pipeline(Request(topic=TEXT), SLEEP, on_stage=lambda k, s, d: seen.append((k, s)))
    assert res.ok
    assert seen == [("router", "start"), ("router", "done"), ("claims", "start"), ("claims", "done"),
                    ("scene_segmenter", "start"), ("scene_segmenter", "done"), ("budget_optimizer", "start"),
                    ("budget_optimizer", "done"), ("voice_segmenter", "start"), ("voice_segmenter", "done"),
                    ("narration_audio", "start"), ("narration_audio", "done"), ("timeline_assembler", "start"),
                    ("timeline_assembler", "done")]


def test_pipeline_reports_where_it_stopped():
    seen = []
    res = run_pipeline(Request(topic="Make a 5-minute video about sleep"), SLEEP, on_stage=lambda k, s, d: seen.append((k, s)))
    assert not res.ok and seen == [("router", "start"), ("router", "failed")]


def test_pipeline_without_a_callback_is_unchanged():
    assert run_pipeline(Request(topic=TEXT), SLEEP).ok


def test_make_video_reports_the_planning_stages_then_verify(tmp_path: Path):
    seen = []
    voice = builtin_library().default("en")
    engine = make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))
    res = make_video(TEXT, SLEEP, tmp_path / "v.mp4", engine=engine, voice=voice, render=False,
                     on_stage=lambda k, s, d: seen.append((k, s)))
    assert res.ok
    keys = [k for k, _ in seen]
    assert keys.index("router") < keys.index("scene_segmenter") < keys.index("timeline_assembler") < keys.index("verify")
    assert ("render", "start") not in seen                      # a dry run renders nothing
    assert seen[-1] == ("verify", "done")


# ------------------------------------------------------------------------------------------ the UI folding
def test_nothing_is_done_or_running_before_the_first_event():
    live = LiveStages()
    assert set(states(live).values()) == {"pending"} and live.progress()[0] == 0.0


def test_a_stage_is_working_after_its_start_and_done_only_after_the_backend_says_so():
    live = feed(LiveStages(), [("router", "start", "")])
    assert states(live)["understanding"] == "running"
    live.update("router", "done", "Infographic video, 90 s target")
    s = states(live)
    assert s["understanding"] == "done" and s["planning"] == "pending"
    assert next(x for x in live.view() if x["key"] == "understanding")["detail"] == "Infographic video, 90 s target"


def test_full_run_marks_each_step_in_turn_and_ends_all_done():
    live = LiveStages()
    steps = [("router", "start"), ("router", "done"), ("claims", "start"), ("claims", "done"), ("scene_segmenter", "start"),
             ("scene_segmenter", "done"), ("budget_optimizer", "start"), ("budget_optimizer", "done"), ("voice_segmenter", "start"),
             ("voice_segmenter", "done"), ("narration_audio", "start"), ("narration_audio", "done"), ("timeline_assembler", "start"),
             ("timeline_assembler", "done"), ("render", "start"), ("render", "done"), ("verify", "start"), ("verify", "done")]
    last = -1.0
    for key, st in steps:
        live.update(key, st, "x")
        frac, text = live.progress()
        assert frac >= last and 0.0 <= frac <= 1.0                 # the bar never goes backwards
        last = frac
    assert set(states(live).values()) == {"done"} and live.progress()[0] == 1.0


def test_narration_and_timeline_stay_working_until_the_backend_finishes_them():
    live = feed(LiveStages(), [("router", "start", ""), ("router", "done", ""), ("claims", "start", ""), ("claims", "done", ""),
                               ("scene_segmenter", "start", ""), ("scene_segmenter", "done", ""), ("budget_optimizer", "start", ""),
                               ("budget_optimizer", "done", ""), ("voice_segmenter", "start", ""), ("voice_segmenter", "done", "9 voice units")])
    assert states(live)["narration"] == "running"                  # the voice engine has not measured the audio yet
    feed(live, [("narration_audio", "start", ""), ("narration_audio", "done", ""), ("timeline_assembler", "start", ""),
                ("timeline_assembler", "done", "90.2 s timeline")])
    assert states(live)["narration"] == "done" and states(live)["timeline"] == "running"   # still has to render the MP4
    feed(live, [("render", "start", "")])
    live.set_render(0.5, "scene 6/12")
    assert next(x for x in live.view() if x["key"] == "timeline")["detail"] == "Rendering frames · scene 6/12"
    assert live.progress()[0] > 5 / 7
    feed(live, [("render", "done", "2160 frames")])
    assert states(live)["timeline"] == "done" and states(live)["verify"] == "pending"


def test_a_failure_marks_only_that_step_and_leaves_the_rest_waiting():
    live = feed(LiveStages(), [("router", "start", ""), ("router", "done", ""), ("claims", "start", ""), ("claims", "done", ""),
                               ("scene_segmenter", "start", ""), ("scene_segmenter", "failed", "only 4 scenes")])
    s = states(live)
    assert s["scenes"] == "failed" and s["understanding"] == "done" and s["budget"] == s["verify"] == "pending"


def test_a_replan_starts_the_steps_over_and_keeps_the_note():
    live = feed(LiveStages(), [("router", "start", ""), ("router", "done", ""), ("timeline_assembler", "failed", "off target"),
                               ("replan", "info", "N0: re-planned"), ("router", "start", "")])
    assert live.note == "N0: re-planned" and states(live)["understanding"] == "running"
    assert states(live)["timeline"] == "pending"


def test_a_replan_does_not_show_a_red_failure_while_the_backend_retries():
    live = feed(LiveStages(), [("router", "start", ""), ("router", "done", ""), ("timeline_assembler", "failed", "off target"),
                               ("replan", "info", "N4: pauses changed")])
    assert "failed" not in states(live).values() and states(live)["timeline"] == "running"
    assert "N4: pauses changed" in next(x for x in live.view() if x["key"] == "timeline")["detail"]


def test_the_bar_text_names_the_working_step():
    live = feed(LiveStages(), [("router", "start", "")])
    assert live.progress()[1] == "Understanding Request…"
    assert LiveStages().progress()[1] == "Working…"


def test_ai_reading_keeps_the_first_step_working_and_ai_pictures_are_named():
    live = feed(LiveStages(), [("ai_read", "start", "The AI is reading your input…")])
    assert states(live)["understanding"] == "running"
    live.update("ai_read", "done", "")
    assert states(live)["understanding"] == "running"             # only the Router finishes this step
    feed(live, [("timeline_assembler", "start", "")])
    live.set_render(0.0, "AI picture 3/12")
    assert next(x for x in live.view() if x["key"] == "timeline")["detail"] == "Making AI picture 3/12"
    assert live.rendering is False


def test_unknown_events_are_ignored():
    live = feed(LiveStages(), [("something_new", "start", "")])
    assert set(states(live).values()) == {"pending"}


def test_running_steps_say_what_they_are_doing_and_waiting_steps_say_nothing():
    live = feed(LiveStages(), [("router", "start", ""), ("router", "done", ""), ("claims", "start", "")])
    v = {s["key"]: s for s in live.view()}
    assert v["planning"]["detail"] and not v["budget"]["detail"]
