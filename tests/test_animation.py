"""Tests of the ANIMATION format: keyframe tracks, Motion Planner rules, cut-out frames, and the
end-to-end video (silent voice, so no TTS and no network are needed)."""
import numpy as np
import pytest

from core.models import MOTION_MODES, OutputFormat, RenderMode, Scene
from modules.pipeline.pipeline import PipelineStatus, run_pipeline
from modules.pipeline.sample_claims import get_sample_claims
from modules.router.router import Request
from modules.video.animation import (Layer, Track, arm_angle, check_animation, compose_animation_scene, fade, hold,
                                     join, make_sprite, pop, wiggle)
from modules.video.composer import Style
from modules.video.make_video import make_video
from modules.video.motion_planner import (DEFAULT_PROP, ENERGY_HIGH, ENERGY_NORMAL, PROP_BY_PATTERN, PROPS, POSES,
                                          plan_motion)
from modules.video.voice import FFmpegMissing, find_ffmpeg, make_engine
from modules.voice_library.library import builtin_library

ST = Style()
PATTERNS = ["cause_effect", "comparison", "step_by_step", "trend", "analogy", "something_else"]


def scene(pattern="cause_effect", importance=0.5, sid=0, facet="science"):
    return Scene(scene_id=sid, narration="Some narration.", explain_pattern=pattern, importance=importance,
                 facet=facet, claim_ids=[f"C{sid}"])


# ------------------------------------------------------------------ keyframe tracks
def test_track_hits_its_keys_and_clamps():
    t = Track(((0.2, 10.0), (0.6, 30.0), (1.0, 0.0)))
    assert t(0.0) == 10.0 and t(0.2) == 10.0            # before the first key: the first value
    assert t(0.6) == pytest.approx(30.0) and t(1.0) == 0.0
    assert t(5.0) == 0.0                                 # after the last key: the last value


def test_track_eases_but_linear_mode_does_not():
    eased, linear = Track(((0.0, 0.0), (1.0, 10.0))), Track(((0.0, 0.0), (1.0, 10.0)), ease=False)
    assert linear(0.25) == pytest.approx(2.5)
    assert eased(0.25) < linear(0.25) and eased(0.5) == pytest.approx(5.0)    # slow start, same midpoint


def test_track_rejects_bad_keys():
    with pytest.raises(ValueError):
        Track(())
    with pytest.raises(ValueError):
        Track(((0.5, 1.0), (0.5, 2.0)))                  # u must strictly increase
    with pytest.raises(ValueError):
        Track(((0.6, 1.0), (0.2, 2.0)))


def test_key_helpers():
    w = Track(wiggle(5.0, 2.0, 2, 0.2, 0.8), ease=False)
    assert w(0.2) == pytest.approx(5.0) and w(0.8) == pytest.approx(5.0)
    assert 6.8 < max(w(u / 100) for u in range(20, 81)) <= 7.0               # peak close to the amplitude (10 keys per cycle)
    p = Track(pop(0.2, 0.6, 1.2))
    assert p(0.0) == 0.0 and p(0.6) == pytest.approx(1.0) and max(p(u / 100) for u in range(100)) > 1.1
    f = Track(fade(0.3, 0.5))
    assert f(0.2) == 0.0 and f(0.5) == 1.0
    assert dict(join(((0.0, 1.0),), ((0.0, 2.0), (1.0, 3.0))))[0.0] == 2.0   # later parts win


# ------------------------------------------------------------------ poses
def test_poses_move_the_arm_as_named():
    assert arm_angle("wave", 0.0) == 0.0                                   # arm down at the start
    assert min(arm_angle("wave", u / 100) for u in range(30, 78)) > 120    # raised while waving
    assert 70 < arm_angle("point", 0.6) < 100                              # roughly horizontal
    assert arm_angle("think", 0.9) > 140
    assert arm_angle("shrug", 0.6) > 20 and arm_angle("shrug", 0.6, back=True) < -20   # both arms go out
    with pytest.raises(ValueError):
        arm_angle("dance", 0.5)


def test_energy_makes_the_wave_bigger():
    swing = lambda e: (max(arm_angle("wave", u / 200, e) for u in range(60, 150))
                       - min(arm_angle("wave", u / 200, e) for u in range(60, 150)))
    assert swing(1.4) > swing(1.0)


# ------------------------------------------------------------------ Motion Planner rules
def test_hook_waves_and_is_lively():
    p = plan_motion(scene("comparison", 0.1), 0, 12)
    assert (p.role, p.pose, p.energy) == ("hook", "wave", ENERGY_HIGH)


def test_summary_is_lively_but_keeps_the_pattern_pose():
    p = plan_motion(scene("comparison", 0.1), 11, 12)
    assert (p.role, p.pose, p.energy) == ("summary", "shrug", ENERGY_HIGH)


@pytest.mark.parametrize("pattern", PATTERNS)
def test_body_scene_follows_its_pattern(pattern):
    p = plan_motion(scene(pattern, 0.5), 4, 12)
    assert p.role == "body" and p.energy == ENERGY_NORMAL
    assert p.prop == PROP_BY_PATTERN.get(pattern, DEFAULT_PROP) and p.prop in PROPS and p.pose in POSES


def test_importance_threshold():
    assert plan_motion(scene(importance=0.74), 3, 12).energy == ENERGY_NORMAL
    assert plan_motion(scene(importance=0.75), 3, 12).energy == ENERGY_HIGH


def test_character_alternates_sides():
    assert [plan_motion(scene(), i, 6).mirror for i in range(6)] == [False, True, False, True, False, True]


def test_unknown_pattern_gets_the_default_prop():
    assert plan_motion(scene("something_else"), 2, 8).prop == DEFAULT_PROP == "bubble"


@pytest.mark.parametrize("index, total", [(-1, 5), (5, 5), (0, 0)])
def test_planner_rejects_positions_outside_the_video(index, total):
    with pytest.raises(ValueError):
        plan_motion(scene(), index, total)


def test_plan_is_deterministic():
    assert plan_motion(scene("trend", 0.9), 5, 10) == plan_motion(scene("trend", 0.9), 5, 10)


# ------------------------------------------------------------------ sprites and frames
def test_sprite_is_padded_so_the_pivot_is_the_centre():
    spr = make_sprite((40, 120), (20, 10), lambda d, k: d.rectangle((0, 0, 40 * k, 120 * k), fill=(0, 0, 0, 255)))
    assert spr.width == spr.height and spr.mode == "RGBA"
    # rotating a full turn about the pivot loses nothing: the padded canvas is big enough
    assert np.asarray(spr.rotate(90))[:, :, 3].sum() == pytest.approx(np.asarray(spr)[:, :, 3].sum(), rel=0.02)


@pytest.mark.parametrize("pattern", PATTERNS)
@pytest.mark.parametrize("index", [0, 1, 4, 11])
def test_every_scene_moves_and_leaves_the_subtitle_band_free(pattern, index):
    cs = compose_animation_scene(scene(pattern, 0.9 if index == 4 else 0.5), "claim", ST, index, 12)
    assert check_animation(cs, ST) == []


def test_frames_are_deterministic():
    a = compose_animation_scene(scene("trend"), "claim", ST, 2, 12)
    b = compose_animation_scene(scene("trend"), "claim", ST, 2, 12)
    ra, rb = a.make_renderer(7.0, 7.0, 2, ST), b.make_renderer(7.0, 7.0, 2, ST)
    for t in (0.0, 1.7, 3.5, 6.9):
        assert np.array_equal(ra.frame(t), rb.frame(t)) and np.array_equal(ra.frame(t), ra.frame(t))


def test_motion_follows_the_scene_length_not_the_clock():
    """Props follow the fraction u of the scene. The jointed figure is timed in seconds on purpose
    (walking speed, lip-sync and blinking must not stretch with the scene), so it is left out here."""
    cs = compose_animation_scene(scene("cause_effect"), "claim", ST, 2, 12)
    cs.layers = [l for l in cs.layers if l.name != "stickman"]
    short, long = cs.make_renderer(5.0, 5.0, 2, ST), cs.make_renderer(10.0, 10.0, 2, ST)
    assert np.array_equal(short.frame(2.5), long.frame(5.0))                 # same u = 0.5


def test_jointed_figure_walks_at_the_same_speed_in_short_and_long_scenes():
    cs = compose_animation_scene(scene("cause_effect"), "claim", ST, 2, 12)
    fig = next(l for l in cs.layers if l.name == "stickman")
    assert fig.pose_at(0.5, 6.0)[1] == fig.pose_at(0.5, 9.0)[1]             # same seconds, same place


def test_picture_shape_and_type():
    cs = compose_animation_scene(scene(), "claim", ST, 0, 6)
    fr = cs.make_renderer(6.0, 6.0, 0, ST).frame(3.0)
    assert fr.shape == (720, 1280, 3) and fr.dtype == np.uint8


def test_animated_scene_has_no_drawn_text_and_names_its_layout():
    cs = compose_animation_scene(scene("comparison"), "claim", ST, 1, 6)
    assert cs.labels == [] and cs.layout == "cutout:bars" and not cs.overflow
    assert cs.plan.mirror and "stickman" in {l.name for l in cs.layers}          # the jointed figure (stickman.py)
    old = compose_animation_scene(scene("comparison"), "claim", ST, 1, 6)
    from modules.video.animation import RIG, Stage, character_layers
    st = Stage(fx=300, cx=840, s=1, gy=540, accent=(1, 2, 3), accent2=(4, 5, 6), energy=1.0)
    assert {l.name for l in character_layers(st, "point", rig="cutout")} == {"body", "head", "arm_front", "arm_back"}
    assert RIG == "jointed" and old.layers


def test_hidden_layer_is_not_drawn():
    cs = compose_animation_scene(scene(), "claim", ST, 2, 6)
    cs.layers = [Layer("ghost", cs.layers[0].sprite, hold(640), hold(300), alpha=hold(0.0))]
    assert np.array_equal(cs.make_renderer(5.0, 5.0, 2, ST).frame(2.0), np.asarray(cs.base))


# ------------------------------------------------------------------ pipeline and video
CLAIMS = get_sample_claims("sleep")
REQUEST = "Make a 90-second animated video about sleep"


def test_cheap_mode_clip_is_excluded_when_unavailable():
    with_clip = run_pipeline(Request(REQUEST, budget=400), CLAIMS)
    no_clip = run_pipeline(Request(REQUEST, budget=400), CLAIMS, unavailable_modes=frozenset({RenderMode.CLIP}))
    assert with_clip.ok and no_clip.ok
    assert RenderMode.CLIP in with_clip.optimize.plan.values()               # a big budget buys AI clips ...
    assert set(no_clip.optimize.plan.values()) == {RenderMode.LAYERED}       # ... unless none can be made
    assert no_clip.optimize.motion_ratio == 1.0


def _engine():
    voice = builtin_library().default("en")
    return voice, make_engine("silent", voice, 1.0, False, voice.planning_wpm(1.0))


def test_animation_video_plan_passes_the_checks():
    voice, engine = _engine()
    res = make_video(REQUEST, CLAIMS, "unused.mp4", engine=engine, voice=voice, render=False)
    assert res.ok, res.error
    rep = res.report
    assert rep["format"] == "ANIMATION"
    assert {t["mode"] for t in rep["timeline"]} == {"LAYERED"} and all(t["layout"].startswith("cutout:") for t in rep["timeline"])
    assert all({"pose", "prop", "energy"} <= set(t) for t in rep["timeline"])
    for crit in ("S11", "S12", "S13", "S15"):
        assert rep["criteria"][crit]["pass"], rep["criteria"][crit]
    assert any("CLIP" in n for n in rep["notes"])                           # the limitation is stated, not hidden
    assert {m.value for m in MOTION_MODES} >= {t["mode"] for t in rep["timeline"]}


def test_hybrid_is_still_not_built():
    voice, engine = _engine()
    res = make_video("Make a 90-second video about sleep, animate only the opening and summary scenes, keep the rest "
                     "as infographic", CLAIMS, "unused.mp4", engine=engine, voice=voice, render=False)
    assert not res.ok and "HYBRID" in res.error


def test_infographic_still_works_after_the_change():
    voice, engine = _engine()
    res = make_video("Make a 90-second infographic video about sleep", CLAIMS, "unused.mp4", engine=engine,
                     voice=voice, render=False)
    assert res.ok and res.report["format"] == "INFOGRAPHIC" and res.report["criteria"]["S15"]["pass"]


def _ffmpeg_ok():
    try:
        find_ffmpeg()
        return True
    except FFmpegMissing:
        return False


@pytest.mark.skipif(not _ffmpeg_ok(), reason="FFmpeg is not installed")
def test_animation_mp4_is_written_and_measured(tmp_path):
    voice, engine = _engine()
    out = tmp_path / "anim.mp4"
    res = make_video(REQUEST, CLAIMS, out, engine=engine, voice=voice, fps=6, work_dir=tmp_path / "work")
    assert res.ok, res.error
    assert out.exists() and out.stat().st_size > 10_000 and out.with_suffix(".srt").exists()
    assert res.report["criteria"]["S12"]["pass"] and res.report["criteria"]["S13"]["pass"]
    assert res.report["format"] == "ANIMATION"
