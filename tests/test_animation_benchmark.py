"""Light checks that the animation benchmark measures what it claims (one scene, no full sweep)."""
from evaluation.animation_benchmark import MOVES_MIN, ST, _scenes, measure
from modules.video.animation import compose_animation_scene


def _cs():
    scenes = _scenes("sleep")
    return compose_animation_scene(scenes[2], scenes[2].narration, ST, 2, len(scenes))


def test_still_baseline_scores_zero_and_animation_scores_above_threshold():
    cs = _cs()
    still, moving = measure(cs, "v0 still"), measure(cs, "v2 planned (shipped)")
    assert still["motion"] == 0.0 and moving["motion"] > MOVES_MIN
    assert still["band_clean"] and moving["band_clean"]
