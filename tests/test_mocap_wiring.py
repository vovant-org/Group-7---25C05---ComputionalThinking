"""Mocap wiring (stickman clips= and make_video mocap=). NOT run in the sandbox that wrote it: it needs the real repo."""
import json

import numpy as np

from core.models import Scene
from modules.ai.net import AIError
from modules.pipeline.sample_claims import get_sample_claims
from modules.video.animation import GROUND_Y, Stage
from modules.video.make_video import make_video
from modules.video.mocap import J, MocapService, clip_from_joints
from modules.video.stickman import Beat, stickman_layer
from modules.video.voice import make_engine
from modules.voice_library.library import builtin_library
from tests.test_mocap import Prov, skeleton


def arm_up_clip():
    return clip_from_joints("point", np.stack([skeleton(r_arm=(0, 1, 0))] * 6))


def test_a_beat_whose_action_has_a_clip_plays_the_clip():
    st = Stage(fx=300, cx=840, s=1, gy=GROUND_Y, accent=(1, 2, 3), accent2=(4, 5, 6), energy=1.0)
    script = [Beat("walk", 0.0, 1.0, x_to=300), Beat("point", 1.0, 4.0)]
    plain = stickman_layer(st, "point", script=script)
    clipped = stickman_layer(st, "point", script=script, clips={"point": arm_up_clip()})
    assert clipped.pose_at(2.5, 4.0)[0].sh_f > 150 > plain.pose_at(2.5, 4.0)[0].sh_f      # arm straight up vs pointing
    assert clipped.pose_at(0.5, 4.0)[0] == plain.pose_at(0.5, 4.0)[0]                       # walking is never replaced


class Director:
    name = "fake-director"
    def complete(self, system, user):
        items = json.loads(user.split("SCENES:\n", 1)[1])
        return json.dumps({"scenes": [{"scene": it["scene"], "beats": [{"from_word": 0, "action": "point"}, {"from_word": 5, "action": "idea"}]}
                                      for it in items]})


def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


def test_make_video_fetches_one_clip_per_distinct_action_and_reports_it(tmp_path):
    voice, engine = _engine()
    prov = Prov()
    res = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "unused.mp4", engine=engine,
                     voice=voice, render=False, director=Director(), mocap=MocapService(prov, tmp_path))
    assert res.ok, res.error
    assert sorted(k for k, _ in prov.calls) == ["idea", "point"]                              # not once per scene
    assert set(res.report["mocap"]["clips"]) == {"idea", "point"}
    assert all(res.report["criteria"][k]["pass"] for k in ("S11", "S12", "S13", "S15"))


def test_a_failing_mocap_provider_changes_nothing(tmp_path):
    voice, engine = _engine()
    res = make_video("Make a 90-second animated video about sleep", get_sample_claims("sleep"), "unused.mp4", engine=engine,
                     voice=voice, render=False, director=Director(), mocap=MocapService(Prov(fail=True), tmp_path))
    assert res.ok and res.report["mocap"]["clips"] == {} and res.report["mocap"]["errors"]
