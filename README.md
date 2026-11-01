# StoryFrame Studio – Group 7 (CSC10014 Computational Thinking, 2026)

## Run
    pip install pytest
    python -m pytest -q                         # unit + regression tests
    python -m evaluation.budget_benchmark       # -> outputs/budget_benchmark.csv
    python -m evaluation.router_benchmark       # -> outputs/router_benchmark.csv

## Status
| Module | State |
|---|---|
| core/models, core/config | done |
| modules/budget_optimizer | v0, v1, v2 + tests + benchmark (docs/iteration-log.md) |
| modules/router | v0, v1, v2 + 46 labeled cases (docs/iteration-log-router.md) |
| scene_segmenter, timeline_assembler, providers | TODO |
