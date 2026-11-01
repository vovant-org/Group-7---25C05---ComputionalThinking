"""Repeatable benchmark for the Budget Optimizer (report 5.9.15, S11/S18).

Usage:  python -m evaluation.budget_benchmark [--n 300] [--seed 7]
Writes outputs/budget_benchmark.csv and prints a Markdown summary table.
"""
from __future__ import annotations

import argparse
import csv
import random
import time

from core.config import OUTPUT_DIR, PROFILES
from core.models import OutputFormat, Scene
from modules.budget_optimizer.optimizer import (
    ALGORITHMS, min_cost_total, min_cost_with_motion,
)


def make_instance(rng: random.Random, fmt: OutputFormat):
    profile = PROFILES[fmt]
    n = rng.randint(6, 30)                      # n derived from duration limits (report 4c)
    scenes = [Scene(scene_id=i, importance=round(rng.random(), 3)) for i in range(n)]
    lo = min_cost_total(scenes, profile.allowed_modes)
    # budgets from slightly below the minimum to generous
    budget = max(1, int(lo * rng.uniform(0.9, 2.5)))
    return scenes, budget, profile


def run(n_instances: int, seed: int):
    rng = random.Random(seed)
    rows = []
    for idx in range(n_instances):
        fmt = rng.choice(list(OutputFormat))
        scenes, budget, profile = make_instance(rng, fmt)
        need_cost = min_cost_with_motion(scenes, profile)
        truly_feasible = need_cost is not None and need_cost <= budget
        results = {}
        for name, fn in ALGORITHMS.items():
            t0 = time.perf_counter()
            res = fn(scenes, budget, profile)
            ms = (time.perf_counter() - t0) * 1000
            results[name] = (res, ms)
        best = results["v2_dp_motion_state"][0]
        for name, (res, ms) in results.items():
            rows.append({
                "instance": idx, "format": fmt.value, "n": len(scenes), "budget": budget,
                "truly_feasible": int(truly_feasible), "algorithm": name,
                "found_plan": int(res.feasible),
                "over_budget": int(res.feasible and res.total_cost > budget),   # S18-style check
                "value": round(res.total_value, 4) if res.feasible else 0.0,
                "value_vs_v2": (round(res.total_value / best.total_value, 4)
                                if res.feasible and best.feasible and best.total_value else 0.0),
                "runtime_ms": round(ms, 2),
            })
    return rows


def summarize(rows):
    algos = list(ALGORITHMS)
    lines = ["| Algorithm | Feasible instances solved | Over-budget plans | Mean value / v2 (when both solve) | Mean runtime (ms) |",
             "|---|---|---|---|---|"]
    for a in algos:
        r = [x for x in rows if x["algorithm"] == a]
        feas = [x for x in r if x["truly_feasible"]]
        solved = sum(x["found_plan"] for x in feas)
        both = [x for x in r if x["found_plan"] and x["value_vs_v2"] > 0]
        mean_ratio = sum(x["value_vs_v2"] for x in both) / max(1, len(both))
        mean_ms = sum(x["runtime_ms"] for x in r) / len(r)
        lines.append(f"| {a} | {solved}/{len(feas)} ({100*solved/max(1,len(feas)):.1f}%) "
                     f"| {sum(x['over_budget'] for x in r)} | {mean_ratio:.4f} | {mean_ms:.1f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rows = run(a.n, a.seed)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "budget_benchmark.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"instances={a.n} seed={a.seed} -> {out}\n")
    print(summarize(rows))
