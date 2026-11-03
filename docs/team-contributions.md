# Team Logbook & Contribution Evidence – Group 7 (StoryFrame Studio)

Course: CSC10014 – Computational Thinking – Project 2026.
Rule for this file: write **only what actually happened**, one line per event, with date,
person and evidence (commit / file / command). Items marked `TODO` are not filled in yet.

## Team and roles (from the report)

| No. | Student ID | Full name | Project role |
|---|---|---|---|
| 1 | 25127148 | Võ Văn Thiện | Team Leader |
| 2 | 25127097 | Vũ Thành Nam | Developer and Tester |
| 3 | 25127498 | Vũ Tiến Thắng | Tester |
| 4 | 25127156 | Phan Minh Tiến | Developer |
| 5 | 25127044 | Nguyễn Ngọc Hải | Documentation Writer |

## Weekly log

### 2026-11-01 (Sun)

| Who | What | Evidence |
|---|---|---|
| Vũ Thành Nam | Set up Python on Windows, installed pytest, ran `py -m pytest -q` and `evaluation.budget_benchmark` on the team repo. Results matched the reference run: 6 tests passed; v0/v1/v2 solved 218/246, 218/246, 246/246 feasible instances. | Terminal output |
| Vũ Thành Nam | Pushed the Budget Optimizer (v0 greedy, v1 DP as in the report, v2 DP with motion-count state) with tests and benchmark. | Commit `741e639` "v2: DP motion-state optimizer, infographic feasibility 88.6% -> 100%" |
| Vũ Thành Nam | Ran the Router tests and benchmark: 83 passed; v0/v1/v2 exact match 27/46, 44/46, 45/46. Pushed Router v0–v2. | Commit `b1a6ee4` "Router v2: hybrid rules + intent parser, free-text exact 1/20 -> 19/20" |
| Vũ Thành Nam | Wrote 5 adversarial Router cases (`150s`, `1,000 credits`, `1 minute 30 seconds`, `not animation`, topic containing "convert"). All 5 broke v2. Reviewed the 46 hand-written labels against the report and documented three design decisions (structured field vs. text, missing format, prompt injection). Updated the iteration log. | Commit `4418145` "5 adversarial router cases and update iteration log" |

### 2026-11-03 (Tue)

| Who | What | Evidence |
|---|---|---|
| Vũ Thành Nam | Replaced the Router files with the v3 version (request/topic split, more units, compound durations, thousands separators, negation) and re-ran tests and benchmark. | `py -m pytest -q`: 152 passed in 2.69s; router_benchmark: v3 exact match 55/55, adversarial 5/5; commit `4be6a28` |
| Whole team | `TODO`: review the 4 new `v3_*` cases in `evaluation/router_cases.py` (labels were written by the AI assistant from the report) | `TODO` |
| Whole team | `TODO`: each remaining member writes ≥ 5 new cases to break Router v3 (tag e.g. `adversarial_r2`), without reading the v3 code first | `TODO` |

## Contribution summary (update every week)

| Member | Analysis | Design | Implementation | Evaluation | Communication / docs |
|---|---|---|---|---|---|
| Võ Văn Thiện | TODO | TODO | TODO | TODO | TODO |
| Vũ Thành Nam | Reviewed Router labels against the report | Documented 3 Router design decisions | Ran, integrated and pushed Budget Optimizer and Router versions | Wrote 5 adversarial Router cases; reproduced benchmarks on his machine | Updated `iteration-log-router.md` |
| Vũ Tiến Thắng | TODO | TODO | TODO | TODO | TODO |
| Phan Minh Tiến | TODO | TODO | TODO | TODO | TODO |
| Nguyễn Ngọc Hải | TODO | TODO | TODO | TODO | TODO |

The course expects every member to contribute across analysis, design, implementation,
evaluation and communication, not one isolated role.

## Record of AI tool use and verification

Policy reminder: AI output is not evidence by itself; every result below comes from code the
team ran itself.

| Date | Tool | What it produced | How the team verified it |
|---|---|---|---|
| 2026-11-01 | Claude | Repo plan; `core/models.py`, `core/config.py`; Budget Optimizer v0/v1/v2; `test_optimizer.py`; `budget_benchmark.py`; `iteration-log.md` | Ran `pytest` (6 passed) and the benchmark on a Windows machine; numbers matched the reference run (218/246, 218/246, 246/246). Test compares DP v2 with brute force on small cases. |
| 2026-11-01 | Claude | Router v0/v1/v2; `intent_parser.py`; 46 labeled cases; `router_benchmark.py`; `test_router.py`; `iteration-log-router.md` | Ran `pytest` (83 passed) and the benchmark; numbers matched (27/46, 44/46, 45/46). Nam reviewed all labels against the report and added adversarial cases that exposed 5 real failures. |
| 2026-11-03 | Claude | Router v3; 4 new `v3_*` cases; updated `test_router.py` and iteration log | Nam ran `py -m pytest -q` (152 passed) and `evaluation.router_benchmark` (v3 55/55) on a Windows machine; numbers matched the reference run. Known caveat (written in the log): v3 was written after the adversarial cases were known, so 5/5 is a regression fix, not generalization. New unseen cases are needed. |

Things the AI got wrong or overstated, found by the team (keep this honest list):
- It said Python 3.10+ was required; the code runs on Python 3.9 (confirmed on the team machine).
- `TODO`: add anything else found while reviewing.

## Open items

- [ ] Fill `docs/requirements.md` (R1: use cases, non-goals, thresholds for S9–S19).
- [ ] Fill `docs/architecture.md` (context, component and sequence diagrams from the report).
- [ ] Replace the assumed `MODE_COST` / `MODE_QUALITY` with measured values (to-do item 11), then
      re-run both benchmarks.
- [ ] Next module: Voice Segmenter (F1 greedy → F2 DP, S19).