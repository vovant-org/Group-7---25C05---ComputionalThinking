"""AI director (modules/ai/director.py + stickman.beats_from_directions + wiring). A fake LLM: no network."""
import json

import pytest

from core.models import Scene
from modules.ai.director import ALLOWED, direct_scenes
from modules.ai.net import AIError
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.animation import GROUND_Y, Stage
from modules.video.composer import Style
from modules.video.make_video import make_video
from modules.video.stickman import MIN_BEAT_S, WALK_IN_PX, beats_from_directions, stickman_layer
from modules.video.voice import make_engine
from modules.visual_engine import analyse_topic
from modules.visual_engine.engine import compose_topic_scene
from modules.voice_library.library import builtin_library

ST = Style()
NARR = "At night sleep helps the brain sort memories and clear waste."          # 11 words


class FakeLLM:
    name = "fake-director"

    def __init__(self, answer=None, exc=None):
        self.answer, self.exc, self.calls = answer, exc, []

    def complete(self, system, user):
        self.calls.append((system, user))
        if self.exc:
            raise self.exc
        if callable(self.answer):
            return self.answer(user)
        return self.answer


def scenes_in(user):
    return json.loads(user.split("SCENES:\n", 1)[1])


def default_answer(user):
    out = []
    for it in scenes_in(user):
        n = len(it["words"].split())
        out.append({"scene": it["scene"], "beats": [{"from_word": 0, "action": "point"},
                                                    {"from_word": max(1, n // 2), "action": "idea"}]})
    return json.dumps({"scenes": out})


def sc(i, text=NARR):
    return Scene(scene_id=i, narration=text, facet="science", claim_ids=[f"C{i}"])


# ------------------------------------------------------------------ director: validation
def test_menu_has_no_walk_or_run():
    assert "walk" not in ALLOWED and "run" not in ALLOWED and {"point", "idea", "think"} <= set(ALLOWED)


def test_valid_answer_is_kept_sorted_and_numbered_words_are_sent():
    ans = json.dumps({"scenes": [{"scene": 0, "beats": [{"from_word": 6, "action": "idea"}, {"from_word": 0, "action": "Point"}]}]})
    llm = FakeLLM(ans)
    res = direct_scenes(llm, [sc(0)])
    assert res.directions == {0: [("point", 0), ("idea", 6)]} and res.info["scenes_directed"] == 1
    assert "0:At 1:night" in llm.calls[0][1] and "hook" in llm.calls[0][1]


def test_bad_beats_are_dropped_with_a_reason_and_repeats_merged():
    beats = [{"from_word": 0, "action": "dance"}, {"from_word": 99, "action": "wave"}, {"from_word": "x", "action": "nod"},
             {"from_word": 0, "action": "walk"}, {"from_word": 1, "action": "talk"}, {"from_word": 5, "action": "talk"},
             {"from_word": 8, "action": "shrug"}]
    res = direct_scenes(FakeLLM(json.dumps({"scenes": [{"scene": 0, "beats": beats}]})), [sc(0)])
    assert res.directions[0] == [("talk", 1), ("shrug", 8)]
    why = " | ".join(res.info["rejected"])
    for part in ("dance", "outside the narration", "not a number", "walk"):
        assert part in why


def test_at_most_max_beats_and_unknown_scene_ids_are_ignored():
    beats = [{"from_word": i, "action": a} for i, a in enumerate(["talk", "point", "idea", "think", "shrug", "nod", "cheer"])]
    ans = json.dumps({"scenes": [{"scene": 0, "beats": beats}, {"scene": 77, "beats": beats}]})
    res = direct_scenes(FakeLLM(ans), [sc(0, " ".join(["w"] * 12))], max_beats=4)
    assert len(res.directions[0]) == 4 and 77 not in res.directions


@pytest.mark.parametrize("llm", [FakeLLM(exc=AIError("offline")), FakeLLM("not json"), FakeLLM('{"other": 1}')])
def test_provider_errors_and_bad_json_never_raise(llm):
    res = direct_scenes(llm, [sc(0), sc(1)])
    assert res.directions == {} and res.info["scenes_directed"] == 0 and res.info["notes"]


def test_missing_scene_is_reported():
    ans = json.dumps({"scenes": [{"scene": 0, "beats": [{"from_word": 0, "action": "nod"}]}]})
    res = direct_scenes(FakeLLM(ans), [sc(0), sc(1)])
    assert list(res.directions) == [0] and "[1]" in res.info["notes"][0]


# ------------------------------------------------------------------ beats from directions
def test_beats_follow_the_spoken_words_and_cover_the_scene():
    beats = beats_from_directions([("surprised", 0), ("idea", 4)], NARR, 7.0, 8.0, 300)
    assert [b.action for b in beats] == ["walk", "surprised", "idea"]
    assert beats[0].t0 == 0.0 and beats[0].x_to == 300 and beats[-1].t1 == pytest.approx(8.0)
    assert all(a.t1 == pytest.approx(b.t0) for a, b in zip(beats, beats[1:]))
    assert 1.8 < beats[2].t0 < 2.6                      # word 4 is spoken about 2.3 s into 7 s of audio


def test_a_late_first_gesture_is_preceded_by_talking_and_close_beats_are_dropped():
    beats = beats_from_directions([("idea", 4), ("nod", 5), ("walk", 6), ("shrug", 99)], NARR, 7.0, 8.0, 300)
    assert [b.action for b in beats] == ["walk", "talk", "idea"]
    assert all(b.t1 - b.t0 >= 0.05 for b in beats) and beats[2].t1 - beats[2].t0 >= MIN_BEAT_S


def test_nothing_usable_gives_walk_in_then_talk():
    beats = beats_from_directions([("dance", 0)], NARR, 7.0, 8.0, 300)
    assert [b.action for b in beats] == ["walk", "talk"] and beats[-1].t1 == pytest.approx(8.0)


def test_layer_with_directions_uses_them_and_script_still_wins():
    stage = Stage(fx=300, cx=840, s=1, gy=GROUND_Y, accent=(1, 2, 3), accent2=(4, 5, 6), energy=1.0)
    lay = stickman_layer(stage, "point", narration=NARR, audio_s=7.0, directions=[("surprised", 0), ("idea", 4)])
    assert [b.action for b in lay.beats(8.0)] == ["walk", "surprised", "idea"]
    pose, x = lay.pose_at(1.5, 8.0)
    assert pose.expr == "surprised" and x == pytest.approx(300)
    plain = stickman_layer(stage, "point", narration=NARR, audio_s=7.0)
    assert lay.beats(8.0) != plain.beats(8.0)


# ------------------------------------------------------------------ wiring
def test_topic_scene_passes_the_directions_to_its_figure():
    prof = analyse_topic("sleep", ["Sleep helps the brain."])
    ts = compose_topic_scene(sc(0), NARR, prof, ST, 1, 6, directions=[("surprised", 0), ("idea", 4)])
    fig = next(l for l in ts.build_layers(8.0, 7.0, ST) if l.name == "stickman")
    assert [b.action for b in fig.beats(8.0)] == ["walk", "surprised", "idea"]


def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


REQUEST = "Make a 90-second animated video about sleep"


def test_make_video_directs_every_scene_and_still_passes_the_checks():
    voice, engine = _engine()
    llm = FakeLLM(default_answer)
    res = make_video(REQUEST, get_sample_claims("sleep"), "unused.mp4", engine=engine, voice=voice, render=False, director=llm)
    assert res.ok, res.error
    rep = res.report
    assert rep["director"]["scenes_directed"] == rep["scenes"] and rep["director"]["provider"] == "fake-director"
    assert all(rep["criteria"][k]["pass"] for k in ("S11", "S12", "S13", "S15")), rep["criteria"]
    assert len(llm.calls) == 1                                       # one call for the whole video


def test_a_failing_director_changes_nothing_but_adds_a_note():
    voice, engine = _engine()
    res = make_video(REQUEST, get_sample_claims("sleep"), "unused.mp4", engine=engine, voice=voice, render=False,
                     director=FakeLLM(exc=AIError("offline")))
    assert res.ok and res.report["director"]["scenes_directed"] == 0 and res.report["director"]["notes"]


def test_without_a_director_nothing_changes_and_infographic_ignores_it():
    voice, engine = _engine()
    plain = make_video(REQUEST, get_sample_claims("sleep"), "u.mp4", engine=engine, voice=voice, render=False)
    assert plain.ok and "director" not in plain.report
    llm = FakeLLM(default_answer)
    info = make_video("Make a 90-second infographic video about sleep", get_sample_claims("sleep"), "u.mp4", engine=engine,
                      voice=voice, render=False, director=llm)
    assert info.ok and llm.calls == [] and "director" not in info.report
