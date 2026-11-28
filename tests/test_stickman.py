"""Tests of the jointed stick figure (modules/video/stickman.py): skeleton, actions, choreography, lip-sync, drawing."""
import math

import numpy as np
import pytest
from PIL import Image

from modules.video.animation import GROUND_Y, AnimatedScene, LayerRenderer, Stage, character_layers
from modules.video.composer import Style
from modules.video.motion_planner import POSES, MotionPlan
from modules.video.stickman import (ACTIONS, BLEND_S, MAIN_ACTION, WALK_IN_PX, Beat, Ctx, Pose, StickmanLayer, blend,
                                    blinking, choreograph, joints, mouth_open, speech_spans, stickman_layer, syllables,
                                    talking)

ST = Style()
NARR = "Sleep helps the brain clean itself, and adults need seven hours every night."


def stage(s=1, energy=1.0):
    return Stage(fx=300 if s == 1 else 980, cx=840, s=s, gy=GROUND_Y, accent=(80, 140, 255), accent2=(255, 170, 60),
                 energy=energy)


def renderer(layer, dur=8.0):
    base = Image.new("RGB", ST.size, (236, 240, 248))
    sc = AnimatedScene(scene_id=1, plan=MotionPlan(1, "body", "point", "x", 1.0, False), base=base, layers=[layer])
    return LayerRenderer(sc, dur, ST), base


# ------------------------------------------------------------------ skeleton
def test_lowest_foot_stands_on_the_ground_even_when_crouching():
    for p in (Pose(), Pose(kn_f=70, hip_f=50, kn_b=60, hip_b=20), Pose(hip_f=30, hip_b=-30)):
        j = joints(p, 300, GROUND_Y, 1)
        assert max(j["foot_f"][1], j["foot_b"][1]) == pytest.approx(GROUND_Y)
    crouch = joints(Pose(kn_f=70, hip_f=50, kn_b=60, hip_b=20), 300, GROUND_Y, 1)
    assert crouch["hip"][1] > joints(Pose(), 300, GROUND_Y, 1)["hip"][1]          # bent knees: the hip goes down


def test_jump_lifts_the_whole_figure():
    j = joints(Pose(dy=-50), 300, GROUND_Y, 1)
    assert max(j["foot_f"][1], j["foot_b"][1]) == pytest.approx(GROUND_Y - 50)


def test_angles_point_towards_the_facing_side_and_mirror():
    right = joints(Pose(sh_f=90, el_f=0), 300, GROUND_Y, 1)
    left = joints(Pose(sh_f=90, el_f=0), 300, GROUND_Y, -1)
    assert right["hand_f"][0] > right["shoulder"][0] + 90                         # horizontal arm, towards the right
    assert left["hand_f"][0] < left["shoulder"][0] - 90
    assert right["hand_f"][1] == pytest.approx(right["shoulder"][1], abs=0.5)
    up = joints(Pose(sh_f=180, el_f=0), 300, GROUND_Y, 1)
    assert up["hand_f"][1] < up["head"][1]                                        # straight up: above the head


def test_blend_reaches_both_ends():
    a, b = Pose(sh_f=0, expr="neutral"), Pose(sh_f=100, expr="happy")
    assert blend(a, b, 0).sh_f == 0 and blend(a, b, 1).sh_f == 100 and blend(a, b, 0.5).sh_f == 50
    assert blend(a, b, 0.4).expr == "neutral" and blend(a, b, 0.6).expr == "happy"


# ------------------------------------------------------------------ actions
@pytest.mark.parametrize("name", sorted(ACTIONS))
def test_every_action_gives_valid_poses_over_time(name):
    for i in range(40):
        p = ACTIONS[name](i * 0.1, 4.0, 1.2, Ctx(phase=i * 0.4, talking=0.5))
        assert isinstance(p, Pose)
        assert all(math.isfinite(getattr(p, n)) for n in ("lean", "sh_f", "el_f", "hip_f", "kn_f", "dy"))
        assert p.kn_f >= 0 and p.kn_b >= 0                                       # knees only bend one way
        j = joints(p, 640, GROUND_Y, 1)
        assert all(y < 600 for _, y in j.values())                               # never into the subtitle band


def test_named_actions_do_what_they_say():
    t = 1.0
    wave = joints(ACTIONS["wave"](t, 3, 1, Ctx()), 300, GROUND_Y, 1)
    assert wave["hand_f"][1] < wave["head"][1]                                    # waving hand above the head
    point = joints(ACTIONS["point"](t, 3, 1, Ctx()), 300, GROUND_Y, 1)
    assert point["hand_f"][0] - point["shoulder"][0] > 85                         # pointing arm reaches out
    cheer = joints(ACTIONS["cheer"](t, 3, 1, Ctx()), 300, GROUND_Y, 1)
    assert cheer["hand_f"][1] < cheer["head"][1] and cheer["hand_b"][1] < cheer["head"][1]
    assert cheer["hand_f"][0] > cheer["hand_b"][0] + 60                           # a V, not one arm over the other
    think = joints(ACTIONS["think"](t, 3, 1, Ctx()), 300, GROUND_Y, 1)
    assert math.dist(think["hand_f"], think["head"]) < 60                         # hand near the face
    assert ACTIONS["surprised"](t, 3, 1, Ctx()).expr == "surprised"
    air = min(joints(ACTIONS["jump"](i / 50, 3, 1, Ctx()), 300, GROUND_Y, 1)["hip"][1] for i in range(55))
    assert air < joints(Pose(), 300, GROUND_Y, 1)["hip"][1] - 40                  # the jump really leaves the ground


def test_walk_legs_alternate_with_the_phase():
    a = ACTIONS["walk"](0, 1, 1, Ctx(phase=math.pi / 2))
    b = ACTIONS["walk"](0, 1, 1, Ctx(phase=3 * math.pi / 2))
    assert a.hip_f > 10 and b.hip_f < -10 and a.hip_b == -a.hip_f
    assert a.sh_f < 0 < a.sh_b                                                    # arms swing against the legs


# ------------------------------------------------------------------ choreography
@pytest.mark.parametrize("pose", POSES)
@pytest.mark.parametrize("dur", [3.0, 6.0, 12.0])
@pytest.mark.parametrize("role", ["hook", "body", "summary"])
def test_choreography_covers_the_scene_without_gaps(pose, dur, role):
    beats = choreograph(pose, dur, 300, 1, role, 1.4)
    assert beats[0].t0 == 0.0 and beats[-1].t1 == pytest.approx(dur)
    assert all(a.t1 == pytest.approx(b.t0) for a, b in zip(beats, beats[1:]))
    assert beats[0].action == "walk" and beats[0].x_to == 300
    assert MAIN_ACTION[pose] in [b.action for b in beats]


def test_summary_ends_with_a_cheer_or_a_nod():
    assert choreograph("point", 9, 300, 1, "summary", 1.4)[-1].action == "cheer"
    assert choreograph("point", 9, 300, 1, "summary", 1.0)[-1].action == "nod"
    assert choreograph("point", 9, 300, 1, "body", 1.4)[-1].action == "talk"


def test_think_scene_gets_an_idea():
    assert [b.action for b in choreograph("think", 9, 300, 1)][:3] == ["walk", "think", "idea"]


def test_bad_beats_and_poses_are_rejected():
    with pytest.raises(ValueError):
        Beat("dance", 0, 1)
    with pytest.raises(ValueError):
        Beat("wave", 1, 1)
    with pytest.raises(ValueError):
        choreograph("dance", 5, 300, 1)
    with pytest.raises(ValueError):
        stickman_layer(stage(), "dance")


def test_figure_walks_in_and_stops_on_its_spot():
    lay = stickman_layer(stage(), "point", narration=NARR)
    _, x0 = lay.pose_at(0.0, 8.0)
    _, x_end = lay.pose_at(2.5, 8.0)
    assert x0 == pytest.approx(300 - WALK_IN_PX) and x_end == pytest.approx(300)
    mirrored = stickman_layer(stage(-1), "point")
    assert mirrored.pose_at(0.0, 8.0)[1] == pytest.approx(980 + WALK_IN_PX)


def test_script_overrides_the_choreography():
    script = [Beat("idle", 0, 1), Beat("jump", 1, 3), Beat("run", 3, 5, x_to=900)]
    lay = stickman_layer(stage(), "point", script=script)
    assert lay.beats(5.0) == script
    assert lay.pose_at(5.0, 5.0)[1] == pytest.approx(900)


def test_beats_are_blended_not_cut():
    lay = stickman_layer(stage(), "wave", script=[Beat("idle", 0, 1), Beat("wave", 1, 3)])
    before, _ = lay.pose_at(0.999, 3)
    after, _ = lay.pose_at(1.001, 3)
    assert abs(after.sh_f - before.sh_f) < 3                                      # no jump at the beat boundary
    assert lay.pose_at(1 + BLEND_S + 0.5, 3)[0].sh_f > 90


# ------------------------------------------------------------------ lip-sync and blinking
def test_syllables():
    assert syllables("brain") == 1 and syllables("every") >= 2 and syllables("người") == 1 and syllables("xyz") == 1


def test_mouth_moves_inside_words_and_closes_in_pauses():
    spans = speech_spans("Hello world. Sleep well.", 4.0)
    assert len(spans) == 4 and all(a < b for a, b, _ in spans)
    a, b, _ = spans[0]
    assert max(mouth_open(spans, a + (b - a) * i / 20) for i in range(20)) > 0.9
    gap = (spans[1][1] + spans[2][0]) / 2                                          # pause after "world."
    assert spans[1][1] < spans[2][0] and mouth_open(spans, gap) == 0.0
    assert mouth_open(spans, 3.99) == 0.0 and mouth_open([], 1.0) == 0.0
    assert talking(spans, a + 0.01) == 1.0 and talking(spans, 10.0) == 0.0


def test_blinks_are_short_and_deterministic():
    shut = [i / 100 for i in range(1000) if blinking(i / 100, 7)]
    assert 0 < len(shut) < 60 and shut == [i / 100 for i in range(1000) if blinking(i / 100, 7)]


# ------------------------------------------------------------------ drawing
def test_figure_is_drawn_moves_and_stays_out_of_the_subtitle_band():
    r, base = renderer(stickman_layer(stage(), "point", narration=NARR))
    band = np.asarray(base)[ST.size[1] - ST.sub_h:]
    frames = [r.frame(t) for t in (0.3, 1.0, 2.0, 3.0, 5.0, 7.5)]
    for f in frames:
        assert f.shape == (720, 1280, 3) and f.dtype == np.uint8
        assert np.array_equal(f[ST.size[1] - ST.sub_h:], band)
        assert (np.abs(f.astype(int) - np.asarray(base).astype(int)).max(axis=2) > 60).sum() > 500   # visible
    assert not np.array_equal(frames[1], frames[2])


def test_same_scene_gives_the_same_frames():
    a, _ = renderer(stickman_layer(stage(), "think", narration=NARR))
    b, _ = renderer(stickman_layer(stage(), "think", narration=NARR))
    assert np.array_equal(a.frame(2.3), b.frame(2.3))


def test_character_layers_default_to_the_jointed_figure():
    layers = character_layers(stage(), "wave", role="hook", narration=NARR, audio_s=6.0)
    assert len(layers) == 1 and isinstance(layers[0], StickmanLayer)
    assert layers[0].role == "hook" and layers[0].audio_s == 6.0
    with pytest.raises(ValueError):
        character_layers(stage(), "wave", rig="clay")
