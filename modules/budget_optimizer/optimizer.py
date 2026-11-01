"""Budget Optimizer: choose a render mode per scene (group knapsack, report 5.3 / 5.9.3).

Three algorithm versions, kept side by side so the benchmark can show Before/After:

  v0  greedy_upgrade   (C4) cheapest mode first, then upgrade important scenes.
  v1  dp_post_check    (C1 as written in the report) plain DP, motion ratio is
                       checked only AFTER the DP finishes -> can report INFEASIBLE
                       although a valid plan exists.
  v2  dp_motion_state  (C1 fixed) DP with an extra state dimension k = number of
                       motion scenes (capped at the required number), so the
                       ratio constraint is part of the optimisation.

Quality of scene i with mode m:  v(i, m) = importance_i * MODE_QUALITY[m].
"""
from __future__ import annotations

import math
from typing import Callable, Sequence

from core.config import MODE_COST, MODE_QUALITY
from core.models import (
    MOTION_MODES, FormatProfile, OptimizeResult, RenderMode, Scene,
)

NEG = float("-inf")


# ----------------------------------------------------------------- helpers
def _cost(m: RenderMode) -> int:
    return MODE_COST[m]


def _value(s: Scene, m: RenderMode) -> float:
    return s.importance * MODE_QUALITY[m]


def required_motion_scenes(n: int, ratio: float) -> int:
    return math.ceil(ratio * n - 1e-9)


def min_cost_total(scenes: Sequence[Scene], modes: Sequence[RenderMode]) -> int:
    return sum(min(_cost(m) for m in modes) for _ in scenes)


def min_cost_with_motion(scenes: Sequence[Scene], profile: FormatProfile) -> int | None:
    """Exact minimum cost of ANY plan satisfying the motion ratio (feasibility oracle).

    Each scene has a cheapest mode overall and a cheapest motion mode; we need at
    least `need` scenes on a motion mode, so upgrade the `need` scenes with the
    smallest extra cost. Returns None if no motion mode is allowed but needed.
    """
    modes = profile.allowed_modes
    need = required_motion_scenes(len(scenes), profile.min_motion_ratio)
    base = min(_cost(m) for m in modes)
    motion_costs = [_cost(m) for m in modes if m in MOTION_MODES]
    if need > 0 and not motion_costs:
        return None
    if need == 0:
        return base * len(scenes)
    best_motion = min(motion_costs)
    extra = max(0, best_motion - base)
    # identical scenes in cost terms: either every scene is already motion-cheap
    # (extra == 0) or `need` scenes each pay `extra`.
    return base * len(scenes) + extra * need


def _finish(scenes, profile, plan_modes, algorithm) -> OptimizeResult:
    plan = {s.scene_id: m for s, m in zip(scenes, plan_modes)}
    total_cost = sum(_cost(m) for m in plan_modes)
    total_value = sum(_value(s, m) for s, m in zip(scenes, plan_modes))
    ratio = sum(m in MOTION_MODES for m in plan_modes) / max(1, len(scenes))
    return OptimizeResult(True, plan, total_cost, total_value, ratio, algorithm=algorithm)


def _infeasible(reason: str, suggestion: str, algorithm: str) -> OptimizeResult:
    return OptimizeResult(False, reason=reason, suggestion=suggestion, algorithm=algorithm)


def _precheck(scenes, budget, profile, algorithm) -> OptimizeResult | None:
    if not scenes:
        return _infeasible("no scenes", "provide at least one scene", algorithm)
    lo = min_cost_total(scenes, profile.allowed_modes)
    if lo > budget:
        return _infeasible(
            f"minimum cost {lo} > budget {budget}",
            "downgrade to INFOGRAPHIC/HYBRID, shorten T_target, or raise the budget",
            algorithm,
        )
    return None


# ------------------------------------------------------------ v0 greedy (C4)
def greedy_upgrade(scenes: Sequence[Scene], budget: int, profile: FormatProfile) -> OptimizeResult:
    algo = "v0_greedy_upgrade"
    if (r := _precheck(scenes, budget, profile, algo)) is not None:
        return r
    modes = sorted(profile.allowed_modes, key=_cost)
    cheapest = modes[0]
    chosen = {s.scene_id: cheapest for s in scenes}
    remaining = budget - _cost(cheapest) * len(scenes)
    for s in sorted(scenes, key=lambda x: -x.importance):
        best = chosen[s.scene_id]
        for m in modes:
            extra = _cost(m) - _cost(chosen[s.scene_id])
            if extra <= remaining and _value(s, m) > _value(s, best):
                best = m
        remaining -= _cost(best) - _cost(chosen[s.scene_id])
        chosen[s.scene_id] = best
    res = _finish(scenes, profile, [chosen[s.scene_id] for s in scenes], algo)
    return _check_ratio(res, profile, algo)


def _check_ratio(res: OptimizeResult, profile: FormatProfile, algo: str) -> OptimizeResult:
    if res.motion_ratio + 1e-9 < profile.min_motion_ratio:
        return _infeasible(
            f"motion ratio {res.motion_ratio:.2f} < required {profile.min_motion_ratio:.2f}",
            "raise the budget or lower min_motion_ratio",
            algo,
        )
    return res


# ------------------------------------------------------- v1 / v2 dynamic prog.
def _dp(scenes, budget, profile, algo, track_motion: bool) -> OptimizeResult:
    modes = list(profile.allowed_modes)
    n = len(scenes)
    need = required_motion_scenes(n, profile.min_motion_ratio) if track_motion else 0
    K = need + 1
    # dp[i][b][k] = best value using the first i scenes, total cost <= b,
    #               with min(need, #motion scenes) == k
    dp = [[[NEG] * K for _ in range(budget + 1)] for _ in range(n + 1)]
    ch: list = [[[None] * K for _ in range(budget + 1)] for _ in range(n + 1)]
    for b in range(budget + 1):
        dp[0][b][0] = 0.0
    for i in range(1, n + 1):
        s = scenes[i - 1]
        for b in range(budget + 1):
            for pk in range(K):
                for m in modes:
                    c = _cost(m)
                    if c > b:
                        continue
                    prev = dp[i - 1][b - c][pk]
                    if prev == NEG:
                        continue
                    nk = min(need, pk + (1 if (track_motion and m in MOTION_MODES) else 0))
                    val = prev + _value(s, m)
                    if val > dp[i][b][nk] + 1e-12:
                        dp[i][b][nk] = val
                        ch[i][b][nk] = (m, pk)
    if dp[n][budget][need] == NEG:
        return _infeasible("no plan satisfies the budget", "raise the budget or change format", algo)
    # backtrack
    out: list[RenderMode] = [None] * n  # type: ignore[list-item]
    b, k = budget, need
    for i in range(n, 0, -1):
        m, pk = ch[i][b][k]
        out[i - 1] = m
        b -= _cost(m)
        k = pk
    res = _finish(scenes, profile, out, algo)
    return res if track_motion else _check_ratio(res, profile, algo)


def dp_post_check(scenes, budget, profile) -> OptimizeResult:
    """v1: DP exactly as in the report (ratio checked after the DP)."""
    algo = "v1_dp_post_check"
    if (r := _precheck(scenes, budget, profile, algo)) is not None:
        return r
    return _dp(scenes, budget, profile, algo, track_motion=False)


def dp_motion_state(scenes, budget, profile) -> OptimizeResult:
    """v2: DP with the motion-count state dimension. Optimal and ratio-aware."""
    algo = "v2_dp_motion_state"
    if (r := _precheck(scenes, budget, profile, algo)) is not None:
        return r
    return _dp(scenes, budget, profile, algo, track_motion=True)


ALGORITHMS: dict[str, Callable[..., OptimizeResult]] = {
    "v0_greedy_upgrade": greedy_upgrade,
    "v1_dp_post_check": dp_post_check,
    "v2_dp_motion_state": dp_motion_state,
}


def optimize(scenes, budget, profile, algorithm: str = "v2_dp_motion_state") -> OptimizeResult:
    """Public entry point used by the pipeline; also writes the plan back into scenes."""
    res = ALGORITHMS[algorithm](scenes, budget, profile)
    if res.feasible:
        for s in scenes:
            s.render_mode = res.plan[s.scene_id]
            s.cost_credit = _cost(s.render_mode)
    return res
