# Tasks 001 – Pipeline demo

Phase 3 of 4 (tasks). `[x]` = done; each task names its evidence.

## Setup
- [x] T1 Read the public functions of the five modules and the existing tests (224 passed before any change).
- [x] T2 Decide the Lab04 artifacts: user story, sequence diagram, activity diagram (`design.md`).

## Core
- [x] T3 `sample_claims.py`: 2 packs × 16 claims, 11–27 words each. Evidence: `test_fixture_claims_are_usable_for_scenes`.
- [x] T4 `pipeline.py`: stage chain with stop-at-first-failure (FR-1…FR-4). Evidence: happy-path and router tests.
- [x] T5 Budget resolution and optimizer stage (FR-5, FR-6). Evidence: budget tests (request / text / auto / 16 / 13).
- [x] T6 Voice stage with `voice_band_share` (S19 estimate). Evidence: two helper tests.
- [x] T7 Timeline stage and status mapping (FR-7). Evidence: slow-TTS, S12 and pad tests.
- [x] T8 Determinism and algorithm selection (FR-8, FR-9). Evidence: `test_pipeline_is_deterministic`.

## Front ends
- [x] T9 `cli.py` with a text report (FR-10, FR-11).
- [x] T10 `app.py` Streamlit page: sidebar controls, stage tracker, four tabs, proportional timeline bar.
- [x] T11 Headless smoke test of the page with `AppTest` (success, router reject, budget infeasible, optimizer choices).

## Evidence
- [x] T12 Full suite: 248 passed (224 + 24 new).
- [ ] T13 Run on the student's machine: `py -m pytest -q` and `py -m streamlit run app.py`.
- [ ] T14 Screenshots (list in `docs/lab04/README.md`).
- [ ] T15 Export the git commit log; fill the report's machine-run numbers.
