# Iteration log – Budget Optimizer (report 5.3 / 5.9.3, criteria S11, S18)

> Cost/quality per render mode in `core/config.py` are **assumptions** (STATIC 1, PAN 2,
> REVEAL 3, LAYERED 4, CLIP 14 credits). Re-run the benchmark after to-do item 11
> (measuring the real provider cost) and update the numbers below.

Reproduce: `python -m evaluation.budget_benchmark --n 300 --seed 7` (CSV in `outputs/`).
Benchmark: 300 random instances (n = 6–30 scenes, 3 formats, budget 0.9x–2.5x of the
minimum cost); 246 of them are truly feasible (checked by an exact oracle).

| Version | Idea | Feasible instances solved | Mean value vs v2 | Over-budget plans |
|---|---|---|---|---|
| v0 | Greedy upgrade (C4, baseline) | 218/246 (88.6%) | 0.9632 | 0 |
| v1 | DP as in report, ratio checked after DP (C1) | 218/246 (88.6%) | 1.0000 | 0 |
| v2 | DP + motion-count state dimension | 246/246 (100%) | 1.0000 | 0 |

By format (feasible instances): ANIMATION and HYBRID 100% for all versions;
INFOGRAPHIC (min_motion_ratio = 0.5) v0/v1 solve only 35/63, v2 solves 63/63.

## Findings (CT process)
1. **v0 → v1 (decomposition into a knapsack):** greedy loses ~3.7% total quality on average
   because it spends the budget on one scene at a time; DP is optimal (verified against
   brute force in `tests/test_optimizer.py`).
2. **v1 → v2 (error analysis):** all 28 failures are INFOGRAPHIC cases. DP maximises quality,
   so it buys few expensive REVEAL scenes and leaves many STATIC ones, violating
   `min_motion_ratio`, although a valid plan existed. Minimal counter-example: importances
   [0.9, 0.8, 0.1, 0.1], ratio 0.75, budget 8 (`test_v1_post_check_bug_is_fixed_by_v2`).
   Fix: add state k = min(need, #motion scenes); complexity O(n·B·K·|M|).
3. **Trade-off:** v2 is ~5x slower than v1 (10.3 ms vs 2.0 ms average) but still negligible
   for n ≤ 30. ILP (C3) was not chosen: extra dependency for a problem this small.

## Next step
Replace assumed costs with measured ones, add C3/ILP only if budgets grow large.
