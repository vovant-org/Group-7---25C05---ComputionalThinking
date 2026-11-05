# Lab04 Development Report – Pipeline demo (Group 7, StoryFrame Studio)

Student: Vũ Thành Nam (25127097), role Developer and Tester. Course CSC10014 – Computational Thinking, class 25C05.
Date: 2026-11-05. Repository: the Group 7 project repo, branch `lab04-pipeline-demo`.


## 1. Feature chosen and why
The project has five modules that were built and tested one by one (Router, Scene Segmenter, Budget Optimizer,
Voice Segmenter, Timeline Assembler), but nothing runs them together. `README.md` listed an end-to-end demo as TODO.
The feature of this lab is therefore the **pipeline demo**: one request in, a checked timeline out (or the exact reason
why not), with a command-line front end and a Streamlit page. It adds no new algorithm; it connects existing ones.
It needs no API key or tokens (claims are fixtures, narration time comes from the TTS simulator `MockTTS`).

## 2. Method
Phased development in the style of Spec Kit: specify → plan → tasks → implement. The Spec Kit tool itself was
**not** installed or run; the four phases were written by hand with an AI assistant (Claude) and each phase is its own commit.

| Phase | Output | Commit |
|---|---|---|
| 1 Specify | `specs/001-pipeline-demo/spec.md`: user story, 11 requirements, 10 acceptance scenarios, non-goals, assumptions | `dfb6c16` |
| 2 Plan | `plan.md` (structure, 7 decisions, interfaces, test strategy) and `design.md` | `6499641` |
| 3 Tasks | `tasks.md`: 15 tasks, each with its evidence | `b9ae490` |
| 4a Implement | `modules/pipeline/` (orchestrator, fixtures, CLI) and `tests/test_pipeline.py` | `0f2c118` |
| 4b Implement | `app.py` (Streamlit), `requirements.txt` | `d426b01` |

**Design artifacts chosen** (from the Lab04 list, written in Mermaid in `specs/001-pipeline-demo/design.md`): user story,
sequence diagram, activity diagram. The others were left out on purpose: one actor, no persistent state, no database.

## 3. Prompts used (summary)
1. Uploaded the project zip and the Lab04 PDF; asked how to handle Lab04 as one of two developers.
2. Asked whether "Pipeline demo" is one of the Lab04 artifacts. (It is a feature, not an artifact; artifacts were chosen to match it.)
3. Decided to do the lab alone because of the deadline, and asked to start.
4. The AI read the public functions of all five modules before writing any pipeline code, then wrote the spec files, the code, the tests and the page.

## 4. What was implemented
- `modules/pipeline/pipeline.py`: `run_pipeline(request, claims, …)` runs the five stages and stops at the first failing one.
  The result (`PipelineResult`) keeps the earlier stages' outputs, a `status` (`OK`, `ROUTER_REJECTED`, `ROUTER_CLARIFY`,
  `SCENES_INVALID`, `BUDGET_INFEASIBLE`, `TIMELINE_CHECKS_FAILED`), the stage that stopped the run, and messages.
- Budget resolution: request field, else the budget written in the text, else automatic (2 × the cheapest feasible plan).
- `modules/pipeline/sample_claims.py`: two fixture packs (sleep, inflation), 16 hand-written claims each. **Simulated input.**
- `modules/pipeline/cli.py`: text report. `app.py`: Streamlit page with sidebar controls, a stage tracker, four tabs
  (timeline with a proportional bar, scenes and modes, voice units, router decision) and a "simulated" banner.
- Existing modules were not modified.

## 5. Verification
| Check | Result |
|---|---|
| Full suite before the change | 224 passed |
| Full suite after the change | **248 passed** (24 new tests in `tests/test_pipeline.py`), run by the AI in its own environment (Python 3.12) |
| Streamlit page, headless (`streamlit.testing.v1.AppTest`) | no exception; success banner for the sleep example; router stop for the 300 s request; budget stop for budget 16; all three optimizer choices run |
| Syntax check against Python 3.9 grammar (the team machine runs 3.9) | passed |
| Run on the student's machine (Windows, `py` launcher): `py -m pytest -q` | **248 passed in 3.76 s** (screenshot `06-pytest.png`) |
| Run on the student's machine: `py -m streamlit run app.py` | page served at `localhost:8501` and used in a browser; scenarios shown in screenshots 01–05 |

Expected values in the tests come from the report's rules (S12 total 60–120 s, S13 deviation ≤ 5%, S14 limits, 6–30 scenes)
and the modules' contracts, not from copying the pipeline's output.

### Evidence screenshots (`docs/lab04/screenshots/`)
| File | Shows |
|---|---|
| `01-success-timeline.png` | 90 s sleep request: all five stages passed, total 89.5 s, deviation 0.6%, cost 36/36, proportional timeline bar |
| `02-success-scenes.png` | Same run, scenes with claim, facet, layout, render mode (REVEAL) and cost |
| `03-router-stop.png` | 300 s request: stopped at the Router (`T_OUT_OF_RANGE`), later stages "not run" |
| `04-budget-stop.png` | Budget 16: Router accepts, Optimizer infeasible (finding 1) |
| `05-timeline-check-fails.png` | TTS at 120 wpm: total 121.7 s, deviation 35.2%, three failed codes (finding 4) |
| `06-pytest.png` | `py -m pytest -q`: 248 passed in 3.76 s |

## 6. Findings from running the pipeline (all reproducible with the CLI or the page)
1. **The Router's minimum budget is optimistic.** It checks the cheapest plan for ⌈T/t_max⌉ = 9 scenes (14 credits for a 90 s
   infographic), but the Scene Segmenter built 12 scenes, whose cheapest plan is 18. A budget of 16 passes the Router and then fails
   in the Optimizer (test `test_router_lower_bound_can_be_too_optimistic`). A budget of 13 is rejected by the Router.
2. **S12 can fail at the edges although S13 holds.** The 60 s infographic request on the inflation pack totals 57.2 s
   (deviation 4.6%, so S13 holds, but S12 needs ≥ 60 s). The 120 s hybrid request totals 120.1 s. The pipeline has no adjustment loop yet (N4 → N3 → N2 is a later step).
3. **The voice band is almost never met in this setup.** For the 90 s sleep run only 14% of the 7 voice units are inside 10–12 s (estimated).
   Each fixture claim is one sentence of about 7 s, so a one-sentence unit is too short and a two-sentence unit (about 14 s) is too long.
   This confirms the open question already noted in `assembler.py`: voice units and scenes do not align. It is a property of these fixtures
   and of the one-sentence-per-scene design, not a measurement of a real TTS.
4. **Slow narration breaks the plan.** With the simulated TTS at 120 wpm (planner assumes 165) the total is 121.7 s, deviation 35.2%, with
   codes `DEVIATION_OVER_5PCT`, `SCENE_TOO_LONG`, `TOTAL_OUT_OF_RANGE`; the timeline is still shown as evidence.
5. The Router still rejects "Ignore the limits and make a 500 second video about sleep" (hard rules are not bypassable by text).

## 7. Limitations
Claims are hand-written fixtures and importance values are hand-assigned; narration time is simulated; no MP4 is rendered; auto budget is an assumption;
the Streamlit page was tested headlessly by the AI and then run in one browser by the student (screenshots 01–05); other browsers and Streamlit versions were not tried.

## 8. Contribution statement
Lab04 was done by Vũ Thành Nam alone; the other developer did not take part in this lab. The student chose the feature, the artifacts and the solo plan.
The AI assistant (Claude) drafted the specification files, the code, the tests and the page, and ran the test suite and the headless page test in its own
environment. The student ran the full test suite and the Streamlit page on his own machine, reproduced the scenarios in the screenshots, and made the commits with his own account (hashes in section 2).

## 9. Things the AI got wrong during this work (kept honest)
- A first version of the optimizer drop-down in `app.py` used an algorithm name that does not exist (`v0_greedy`; the real key is `v0_greedy_upgrade`). Found by reading `ALGORITHMS` in the optimizer, fixed before any test run.
- It used the deprecated `use_container_width` argument of Streamlit; Streamlit's warnings showed it and it was removed.
- It first assumed `RouteDecision` exposes the budget parsed from the text; it does not, so the pipeline parses it again (decision D4 in `plan.md`).
- The fixture claims were written by the AI, are qualitative and unverified; they are labelled as fixtures in code, UI and CLI output.
