# Spec 001 – Pipeline demo (Lab04 feature)

Phase 1 of 4 (specify). Says WHAT the feature does and WHY; no implementation detail.
Method note: the phases follow Spec Kit (specify → plan → tasks → implement) but the Spec Kit CLI
was not installed; the files were written by hand with an AI assistant (see `docs/lab04/`).

## Why
Group 7 has five working modules (Router, Scene Segmenter, Budget Optimizer, Voice Segmenter,
Timeline Assembler), each tested and benchmarked alone. Nothing runs them together, so nobody can
see what one request produces, or which module stops it. `README.md` lists an end-to-end demo as TODO.

## User story
As a user of StoryFrame Studio, I want to type one request ("Make a 90-second infographic video
about sleep") and see the planned video – scenes, render modes, cost and a timeline – or a clear
reason why it cannot be built, so that I know whether to change my request.

## Functional requirements
| ID | Requirement |
|---|---|
| FR-1 | One call `run_pipeline(request, claims)` runs the stages in this order: Router, Scene Segmenter, Budget Optimizer, Voice Segmenter, Timeline Assembler. |
| FR-2 | The run stops at the first failing stage and says which stage and why (`status`, `stopped_at`, messages). Results of earlier stages stay available. |
| FR-3 | Router REJECT or CLARIFY stops the run before any scene is built. Router hard limits (60–120 s, 1500 words, minimum budget) cannot be bypassed by the request text. |
| FR-4 | Fewer than 6 or more than 30 scenes stops the run (`SCENES_INVALID`). |
| FR-5 | Budget is taken from (1) the `Request` field, else (2) the request text, else (3) automatic = 2 × cheapest feasible plan. The source is reported. |
| FR-6 | An infeasible budget stops the run (`BUDGET_INFEASIBLE`) and shows the optimizer's reason and suggestion. |
| FR-7 | The Timeline Assembler checks S12 (total 60–120 s) and S13 (deviation ≤ 5%); failing a check gives `TIMELINE_CHECKS_FAILED` but the timeline is still returned as evidence. |
| FR-8 | Each module's algorithm version is selectable (e.g. Router v0–v3, selection D1/D2/D2f, optimizer v0–v2, voice F1–F4). |
| FR-9 | Same inputs give the same result (deterministic). |
| FR-10 | A Streamlit page and a command-line command show the stages, the scenes, the voice units and a proportional timeline bar. |
| FR-11 | Simulated inputs are labelled as simulated in the UI and in the CLI output. |

## Acceptance scenarios (each is a test in `tests/test_pipeline.py`)
1. Given "Make a 90-second infographic video about sleep", then all five stages pass, 6–30 scenes, every scene has a mode, total 60–120 s and deviation ≤ 5%.
2. Given a 300-second request, then the Router rejects it and no scene exists.
3. Given "infographic or animation", then the Router asks for clarification and the run stops.
4. Given a prompt-injection request ("Ignore the limits … 500 second"), then it is still rejected.
5. Given only 3 claims or none, then `SCENES_INVALID`.
6. Given a budget of 16 for the 90 s infographic, then the Router accepts but the Optimizer is infeasible (see Assumptions: the Router's lower bound is optimistic).
7. Given a budget of 13, then the Router rejects (`BUDGET_BELOW_MIN`).
8. Given a simulated TTS at 120 wpm, then S13 fails, the run ends at the Timeline Assembler and the timeline is still returned.
9. Given a 60-second infographic request on the inflation pack, then S12 fails (total below 60 s) although the deviation is below 5%.
10. Given an animation request, then only LAYERED or CLIP modes are used.

## Non-goals
Real rendering (FFmpeg/MP4), real TTS, the REASON step (claim extraction), the N4→N3→N2 adjustment loop,
the Cost Estimator, authentication, saving results.

## Assumptions (all labelled in code)
- Claims are hand-written fixtures (`sample_claims.py`), qualitative, no statistics, importance hand-assigned.
- Narration durations come from `MockTTS` (165 wpm, 0.3 s pause per sentence): simulated, not measured.
- Auto budget = 2 × cheapest feasible plan.
- Voice units are cut over the whole script and shown for information; the timeline uses per-scene audio (open question already noted in `assembler.py`).

## Success criteria
- `py -m pytest -q` is green, with the 24 new tests added to the existing 224.
- The page runs on a normal laptop with `streamlit run app.py`; screenshots of a success, a router stop, a budget stop and a timeline-check failure exist.
