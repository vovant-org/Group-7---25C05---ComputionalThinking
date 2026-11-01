import itertools
import random

import pytest

from core.config import MODE_COST, PROFILES
from core.models import MOTION_MODES, FormatProfile, OutputFormat, RenderMode as M, Scene
from modules.budget_optimizer.optimizer import (
    dp_motion_state, dp_post_check, greedy_upgrade, min_cost_with_motion,
    optimize, required_motion_scenes,
)


def scenes_from(importances):
    return [Scene(scene_id=i, importance=v) for i, v in enumerate(importances)]


def brute_force(scenes, budget, profile):
    """Exhaustive optimum, only for tiny n (test oracle)."""
    need = required_motion_scenes(len(scenes), profile.min_motion_ratio)
    best = None
    for combo in itertools.product(profile.allowed_modes, repeat=len(scenes)):
        if sum(MODE_COST[m] for m in combo) > budget:
            continue
        if sum(m in MOTION_MODES for m in combo) < need:
            continue
        from core.config import MODE_QUALITY
        v = sum(s.importance * MODE_QUALITY[m] for s, m in zip(scenes, combo))
        best = v if best is None or v > best else best
    return best


def test_dp_v2_matches_brute_force_on_random_small_cases():
    rng = random.Random(1)
    for _ in range(60):
        fmt = rng.choice(list(OutputFormat))
        profile = PROFILES[fmt]
        scenes = scenes_from([round(rng.random(), 2) for _ in range(rng.randint(3, 5))])
        budget = rng.randint(3, 40)
        opt = brute_force(scenes, budget, profile)
        res = dp_motion_state(scenes, budget, profile)
        if opt is None:
            assert not res.feasible
        else:
            assert res.feasible
            assert res.total_value == pytest.approx(opt, abs=1e-9)


def test_never_exceeds_budget_and_respects_ratio():
    rng = random.Random(2)
    for _ in range(100):
        profile = PROFILES[rng.choice(list(OutputFormat))]
        scenes = scenes_from([rng.random() for _ in range(rng.randint(6, 30))])
        budget = rng.randint(10, 300)
        for fn in (greedy_upgrade, dp_post_check, dp_motion_state):
            res = fn(scenes, budget, profile)
            if res.feasible:
                assert res.total_cost <= budget
                assert res.motion_ratio + 1e-9 >= profile.min_motion_ratio


def test_v1_post_check_bug_is_fixed_by_v2():
    """Budget 8 can afford 3 PAN + 1 STATIC (cost 7) => 75% motion is feasible,
    but plain DP prefers 2 REVEAL + 2 STATIC (only 50% motion) and then fails."""
    profile = FormatProfile(OutputFormat.INFOGRAPHIC,
                            (M.STATIC, M.PAN, M.REVEAL), min_motion_ratio=0.75)
    scenes = scenes_from([0.9, 0.8, 0.1, 0.1])
    assert min_cost_with_motion(scenes, profile) == 7
    assert not dp_post_check(scenes, 8, profile).feasible
    res = dp_motion_state(scenes, 8, profile)
    assert res.feasible and res.motion_ratio >= 0.75 and res.total_cost <= 8


def test_infeasible_budget_gives_suggestion():
    res = dp_motion_state(scenes_from([0.5] * 10), 5, PROFILES[OutputFormat.ANIMATION])
    assert not res.feasible and "downgrade" in res.suggestion


def test_optimize_writes_plan_into_scenes():
    scenes = scenes_from([0.9, 0.5, 0.2, 0.7, 0.4, 0.6])
    res = optimize(scenes, 40, PROFILES[OutputFormat.INFOGRAPHIC])
    assert res.feasible and all(s.render_mode is not None for s in scenes)
    assert sum(s.cost_credit for s in scenes) == res.total_cost


def test_animation_has_only_motion_modes():
    scenes = scenes_from([0.9, 0.5, 0.2, 0.7, 0.4, 0.6])
    res = dp_motion_state(scenes, 100, PROFILES[OutputFormat.ANIMATION])
    assert res.feasible and res.motion_ratio == 1.0
