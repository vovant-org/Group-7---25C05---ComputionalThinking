# Team Logbook & Contribution Evidence – Group 7 (StoryFrame Studio)

Course: CSC10014 – Computational Thinking – Project 2026.

Rules for this file
- Write **only what actually happened**: one line per event, with date, person and evidence
  (commit / PR / file / command output).
- Each member records **only their own work**. Rows of other members stay `TODO` until they fill them in
  with their own evidence.
- Items marked **[conditional]** are kept only if the member really did them as described.
- Numbers come from commands the team ran itself. Results from simulated data are labelled "simulated".

## Team and roles

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
| Vũ Thành Nam | Set up Python on Windows (`py` launcher), installed pytest, ran `py -m pytest -q` and `py -m evaluation.budget_benchmark` on the team repo. Results matched the reference run: 6 tests passed; v0/v1/v2 solved 218/246, 218/246 and 246/246 feasible instances. | Terminal output |
| Vũ Thành Nam | Pushed the Budget Optimizer (v0 greedy, v1 DP as in the report, v2 DP with a motion-count state) with tests and benchmark. | Commit `741e639` "v2: DP motion-state optimizer, infographic feasibility 88.6% -> 100%" |
| Vũ Thành Nam | Ran the Router tests and benchmark: 83 passed; v0/v1/v2 exact match 27/46, 44/46 and 45/46. Pushed Router v0–v2. | Commit `b1a6ee4` "Router v2: hybrid rules + intent parser, free-text exact 1/20 -> 19/20" |
| Vũ Thành Nam | Reviewed the 46 hand-written Router labels against the report, documented three design decisions (structured field vs. free text, missing format, prompt injection) and wrote 5 adversarial cases (`150s`, `1,000 credits`, `1 minute 30 seconds`, `not animation`, a topic containing "convert"). All 5 broke Router v2. Updated the Router iteration log. | Commit `4418145` "5 adversarial router cases and update iteration log" |

### 2026-11-03 (Tue)

| Who | What | Evidence |
|---|---|---|
| Vũ Thành Nam | Replaced the Router files with v3 (request/topic split, more units, compound durations, thousands separators, negation), re-ran the tests (152 passed in 2.69 s) and pushed Router v3. | Commit `4be6a28` "Router v3: request/topic split, adversarial exact 0/5 -> 5/5" |
| Vũ Thành Nam | Ran `py -m evaluation.router_benchmark`: v3 exact match 55/55 and adversarial 5/5 (v2: 48/55 and 0/5). | Terminal output |
| Vũ Thành Nam | Updated this logbook with the Router v3 run and its commit hash. | Commit `e554b3c` "Update team logbook" |
| Vũ Thành Nam | Pulled the Voice Segmenter (F1 greedy, F2/F3/F4 DP, post-TTS repair, simulated TTS), ran `py -m pytest -q` (177 passed in 2.85 s) and `py -m evaluation.voice_benchmark`. Tables A, B and C matched the reference run (e.g. F1/no calibration S19 25.3%, F4/wpm+pause 37.7%). Pushed it. | Terminal output; commit `8cde9df` "Voice Segmenter F1-F4: S19 25.3% -> 35.0% (simulated TTS)" |
| Vũ Thành Nam | Integrated the TTS measurement tools (`measure_tts.py`, `fit_tts_model.py`) and the team brief (`docs/team-brief-next-steps.md`); ran `py -m pytest -q` (180 passed). | Commit `f313f8d` "Add team brief and TTS measurement tools" |
| Vũ Thành Nam | Updated this logbook with the Voice Segmenter run and the tools/brief entries. | Commit `8958d14` "update team contributions" |
| Vũ Thành Nam | Added the AI-assistant prompt (`docs/ai-assistant-prompt.md`) so that each member can be guided step by step by an AI mentor with rules against invented numbers. | Commit `3624ef0` "add ai-assistant to tell others what to do" |
| Vũ Thành Nam | Pulled the Scene Segmenter (D1 greedy, D2 MMR, D2f MMR + facet constraint, scenes and layouts) and pushed it. **[conditional]** Ran `py -m pytest -q` (203 passed) and `py -m evaluation.scene_benchmark`; tables matched the reference run (synthetic data: gold coverage D1 65.4% -> D2f 88.0% at skew 0). | Commit `09ad369` "Scene Segmenter: MMR + facet constraint, gold coverage 65% -> 88% (synthetic)" |
| Vũ Thành Nam | Shared the brief and the AI-assistant prompt with the team and assigned the next tasks (TTS measurement, cost measurement, requirements/architecture docs, issue board, 5 new Router cases per member). | Group chat message / issue link `<link>` |
| Vũ Thành Nam | Process decision: contributions are logged per person with evidence; work is not recorded under another member's name. Teammates' rows stay `TODO` until they fill them in. | This file |

### 2026-11-05 (Thus)
| Who | What | Evidence |
|---|---|---|
| Vũ Thành Nam | Wrote Timeline Assembler v0 (`assemble()`, `Timeline`, `TimelineEntry`): scenes placed by audio duration, S12/S13 checks, 21 tests. Ran `py -m pytest -q`: 224 passed. PR #1 merged by Võ Văn Thiện. | PR #1, commit `a33a6b3` "Timeline Assembler v0: S12/S13 checks, 21 tests (224 pass)", PR #1, merged as `4671254` |

### Tasks assigned to the team (to be filled in by each member)

| Who | Task | Evidence |
|---|---|---|
| Phan Minh Tiến | Measure a real TTS (wpm, pause per sentence, noise) and re-run the voice benchmark | `TODO` |
| Vũ Tiến Thắng | Measure real provider costs (with source and date), update `MODE_COST`, re-run the Budget Optimizer benchmark | `TODO` |
| Nguyễn Ngọc Hải | Write `requirements.md`, `architecture.md` and the failure catalogue | `TODO` |
| Võ Văn Thiện | Issue board, scope decision (ADR), `.env.example`, weekly meeting notes | `TODO` |
| Every member | Write 5 new Router cases to break v3 (tag `adversarial_<name>`), before reading the v3 code | `TODO` |
| Vũ Thành Nam | Prepare 3 hard cases for the Scene Segmenter and keep `main` green | `TODO` |

## Commit evidence index (from `git log --format="%h %ad %an | %s" --date=short`)

| Commit | Date | Author | Message |
|---|---|---|---|
| `741e639` | 2026-11-01 | namvuthanh15 | v2: DP motion-state optimizer, infographic feasibility 88.6% -> 100% |
| `b1a6ee4` | 2026-11-01 | namvuthanh15 | Router v2: hybrid rules + intent parser, free-text exact 1/20 -> 19/20 |
| `4418145` | 2026-11-01 | namvuthanh15 | 5 adversarial router cases and update iteration log |
| `4be6a28` | 2026-11-03 | namvuthanh15 | Router v3: request/topic split, adversarial exact 0/5 -> 5/5 |
| `e554b3c` | 2026-11-03 | namvuthanh15 | Update team logbook |
| `8cde9df` | 2026-11-03 | namvuthanh15 | Voice Segmenter F1-F4: S19 25.3% -> 35.0% (simulated TTS) |
| `f313f8d` | 2026-11-03 | namvuthanh15 | Add team brief and TTS measurement tools |
| `8958d14` | 2026-11-03 | namvuthanh15 | update team contributions |
| `3624ef0` | 2026-11-03 | namvuthanh15 | add ai-assistant to tell others what to do |
| `09ad369` | 2026-11-03 | namvuthanh15 | Scene Segmenter: MMR + facet constraint, gold coverage 65% -> 88% (synthetic) |
| `` |

Other members: add the commits / PRs you authored here (hash, date, your Git account, message).

## Contribution summary (update every week)

| Member | Analysis | Design | Implementation | Evaluation | Communication / docs |
|---|---|---|---|---|---|
| Võ Văn Thiện | TODO | TODO | TODO | TODO | TODO |
| Vũ Thành Nam | Reviewed the Router labels against the report | Documented 3 Router design decisions | Ran, integrated and pushed the Budget Optimizer, Router (v0–v3), Voice Segmenter and Scene Segmenter; integrated the TTS measurement tools | Wrote 5 adversarial Router cases that broke v2; reproduced all benchmarks on his machine | Updated `iteration-log-router.md` and this logbook; prepared the team brief and AI-assistant prompt for the other members |
| Vũ Tiến Thắng | TODO | TODO | TODO | TODO | TODO |
| Phan Minh Tiến | TODO | TODO | TODO | TODO | TODO |
| Nguyễn Ngọc Hải | TODO | TODO | TODO | TODO | TODO |

The course expects every member to contribute across analysis, design, implementation, evaluation and
communication, not one isolated role.

## Record of AI tool use and verification

Policy reminder: AI output is not evidence by itself; every result below comes from code the team ran itself.

| Date | Tool | What it produced | How the team verified it |
|---|---|---|---|
| 2026-11-01 | Claude | Repo plan; `core/models.py`, `core/config.py`; Budget Optimizer v0/v1/v2; `test_optimizer.py`; `budget_benchmark.py`; `iteration-log.md` | Ran `pytest` (6 passed) and the benchmark on a Windows machine; numbers matched the reference run (218/246, 218/246, 246/246). The DP test compares v2 with brute force on small cases. Mode costs and qualities are **assumptions** until measured. Commit `741e639`. |
| 2026-11-01 | Claude | Router v0/v1/v2; `intent_parser.py`; 46 labelled cases; `router_benchmark.py`; `test_router.py`; `iteration-log-router.md` | Ran `pytest` (83 passed) and the benchmark; numbers matched (27/46, 44/46, 45/46). Nam reviewed all labels against the report and added adversarial cases that exposed 5 real failures. Commits `b1a6ee4`, `4418145`. |
| 2026-11-03 | Claude | Router v3; 4 new `v3_*` cases; updated `test_router.py` and the Router iteration log | Nam ran `py -m pytest -q` (152 passed). Known caveat (written in the log): v3 was written after the adversarial cases were known, so 5/5 is a regression fix, not generalization. The 4 `v3_*` labels were written by the AI and need team review. Commit `4be6a28`. |
| 2026-11-03 | Claude | Voice Segmenter (F1–F4, post-TTS repair, simulated TTS), `voice_benchmark.py`, tests, `iteration-log-voice.md` | Nam ran `py -m pytest -q` (177 passed) and `py -m evaluation.voice_benchmark`; numbers matched the reference run. The TTS is **simulated** and labelled so in the log; it must be re-measured with a real TTS before S19 is quoted. Commit `8cde9df`. |
| 2026-11-03 | Claude | TTS measurement tools (`measure_tts.py`, `fit_tts_model.py`), parametrised `voice_benchmark.py`, `team-brief-next-steps.md` | Nam ran `py -m pytest -q` (180 passed); the default benchmark output is unchanged. The tools were only tested on generated audio and synthetic data; the member doing the measurement must verify them on real TTS audio. Commit `f313f8d`. |
| 2026-11-03 | Claude | `ai-assistant-prompt.md` (mentor prompt and per-member task blocks) | Nam read the rules and the file references; it will be validated when teammates use it. Commit `3624ef0`. |
| 2026-11-03 | Claude | Scene Segmenter (D1/D2/D2f, scenes and layouts), hand-written cases, `scene_benchmark.py`, tests, `iteration-log-scene.md` | **[conditional]** Nam ran `py -m pytest -q` (203 passed) and `py -m evaluation.scene_benchmark`; numbers matched. The benchmark data is synthetic (an assumption) and the two hand-written cases were labelled by the AI; the team must review them and add its own hard cases. Commit `09ad369`. |
| 2026-11-04 | Claude | Draft of `assembler.py`, `Timeline`/`TimelineEntry` in `core/models.py`, `test_timeline_assembler.py` | Nam ran `py -m pytest -q` (224 passed). Known caveats: `pad_s` = 0.0 is an assumption (TTS pause not measured); each scene is voiced separately, which may not match the 10-12 s voice units. No benchmark yet (single version, simulated audio). PR #1, commit `a33a6b3`. |

Things the AI got wrong or overstated, found during review (keep this list honest):
- It said Python 3.10+ was required; the code runs on Python 3.9 (confirmed on the team machine).
- It first recommended objective F3 for the Voice Segmenter; a counter-example analysis ([3 s, 11 s, 3 s, 11 s]) showed that F3 ties with the worse solution, so F4 was added.
- The report's own F1 pseudocode (not written by the AI) can emit a 3-sentence voice; the invariant test caught it and the iteration log documents it.
- Its first hand-written Scene Segmenter cases were too small (total claim words below the narration budget, so every algorithm selected everything); this was caught by running them and more claims were added.
- A first draft of the Scene Segmenter iteration log stated an average scene length of 5.2 s and no too-short scenes; the script output showed 4.6 s and 3 of 12 scenes below 4 s, and the log was corrected before use.
- `TODO`: add anything else found while reviewing.

## Open items

- [ ] Fill `docs/requirements.md` (R1: use cases, non-goals, thresholds for S9–S19).
- [ ] Fill `docs/architecture.md` (context, component and sequence diagrams from the report; ADRs).
- [ ] Replace the assumed `MODE_COST` / `MODE_QUALITY` with measured values (to-do item 11), then re-run both benchmarks.
- [ ] Measure the real TTS (to-do items 12 and 14) and re-run the voice benchmark; fix the S19 threshold.
- [ ] Team hard cases for the Scene Segmenter (3 per member) and 5 new Router cases per member.
- [ ] Next modules: Timeline Assembler, narration script generator, Cost Estimator (needs real token logs), end-to-end CLI demo.