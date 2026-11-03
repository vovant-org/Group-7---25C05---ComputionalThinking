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
| Vũ Thành Nam | Replaced the Router files with v3 (request/topic split, more units, compound durations, thousands separators, negation), re-ran the tests (152 passed in 2.69 s) and pushed Router v3. | Commit `4be6a28` "Router v3: request/topic split, adversarial exact 0/5 -> 5/5" |
| Vũ Thành Nam | **[conditional]** Ran `py -m evaluation.router_benchmark`: v3 exact match 55/55, adversarial 5/5 (v2: 48/55 and 0/5). | Terminal output |
| Vũ Thành Nam | Updated the team logbook with the Router v3 run and commit hash. | Commit `e554b3c` "Update team logbook" |
| Vũ Thành Nam | Pulled the Voice Segmenter (F1 greedy, F2/F3/F4 DP, post-TTS repair, simulated TTS), ran `py -m pytest -q` (177 passed in 2.85 s) and `py -m evaluation.voice_benchmark`. Tables A, B and C matched the reference run (e.g. F1/no calibration S19 25.3%, F4/wpm+pause 37.7%). Pushed it. | Terminal output; commit `8cde9df` |
| Vũ Thành Nam | Integrated the TTS measurement tools (`measure_tts.py`, `fit_tts_model.py`) and the team brief (180 tests passed); pushed them. | Commit `f313f8d` "Add team brief and TTS measurement tools" |
| Vũ Thành Nam | **[conditional, after you send it]** Shared the next-step brief (`docs/team-brief-next-steps.md`) with the team and assigned tasks. | Group chat message / issue link `<link>` |

## Contribution summary (update every week)

| Member | Analysis | Design | Implementation | Evaluation | Communication / docs |
|---|---|---|---|---|---|
| Võ Văn Thiện | TODO | TODO | TODO | TODO | TODO |
| Vũ Thành Nam | Reviewed the Router labels against the report; checked that the Voice Segmenter and Router results reproduce on a second machine | Documented 3 Router design decisions | Ran, integrated and pushed the Budget Optimizer, Router (v0–v3) and Voice Segmenter; integrated the TTS measurement tools | Wrote 5 adversarial Router cases that broke v2; reproduced all benchmarks on his machine | Updated `iteration-log-router.md` and the team logbook; shared the next-step brief with the team |
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
| 2026-11-03 | Claude | Router v3 and 4 new `v3_*` cases; updated `test_router.py` and the Router iteration log | Nam ran `py -m pytest -q` (152 passed). Known caveat (written in the log): v3 was written after the adversarial cases were known, so 5/5 is a regression fix, not generalization; new unseen cases are needed. |
| 2026-11-03 | Claude | Voice Segmenter (F1–F4, post-TTS repair, simulated TTS), benchmark, tests and iteration log; TTS measurement tools; team brief | Nam ran `py -m pytest -q` (177 passed) and `py -m evaluation.voice_benchmark`; numbers matched the reference run. The TTS is simulated and is labelled as such in the iteration log; it must be re-measured with a real TTS before S19 is quoted. |

Things the AI got wrong or overstated, found by the team (keep this honest list):
- It said Python 3.10+ was required; the code runs on Python 3.9 (confirmed on the team machine).
- `TODO`: add anything else found while reviewing.
- It first recommended objective F3 for the Voice Segmenter; a counter-example analysis ([3 s, 11 s, 3 s, 11 s]) showed F3 ties with the worse solution, so F4 was added.
- The report's own F1 pseudocode (not written by the AI) can emit a 3-sentence voice; the invariant test caught it and the iteration log documents it.

## Open items

- [ ] Fill `docs/requirements.md` (R1: use cases, non-goals, thresholds for S9–S19).
- [ ] Fill `docs/architecture.md` (context, component and sequence diagrams from the report).
- [ ] Replace the assumed `MODE_COST` / `MODE_QUALITY` with measured values (to-do item 11), then
      re-run both benchmarks.
- [ ] Next module: Voice Segmenter (F1 greedy → F2 DP, S19).