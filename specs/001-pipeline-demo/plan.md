# Plan 001 – Pipeline demo

Phase 2 of 4 (plan). Says HOW. Diagrams are in `design.md`.

## Structure
```
modules/pipeline/
  pipeline.py       run_pipeline(), PipelineResult, Stage, PipelineStatus, voice_band_share()
  sample_claims.py  2 fixture packs (sleep, inflation), 16 claims each
  cli.py            python -m modules.pipeline.cli "<request>" --topic sleep
app.py              Streamlit page (calls run_pipeline only)
tests/test_pipeline.py
```
No existing module is changed. The pipeline only imports their public functions
(`route`, `select_claims`, `build_scenes`, `optimize`, `segment_voices`, `scene_audio_durations`, `assemble`).

## Decisions
| # | Decision | Why | Trade-off |
|---|---|---|---|
| D1 | Orchestrate, do not re-implement | The modules already have tests and benchmarks | The pipeline inherits their gaps (see report) |
| D2 | Stop at the first failing stage, keep earlier results | The user must see where and why; results are evidence | A later problem is not seen until earlier ones are fixed |
| D3 | Return a result object instead of raising | Failures are normal outcomes of a request | Callers must check `status` |
| D4 | Resolve the budget in the pipeline: request field → `parse_intent_v3(text).budget` → auto | `RouteDecision` does not expose the parsed budget | The text is parsed twice (Router and pipeline) |
| D5 | Fixtures stand in for REASON; `MockTTS` stands in for TTS | Both are unbuilt; no tokens or API keys needed | Numbers are simulated and labelled so |
| D6 | The voice stage reports the estimated S19 only | Voice units and scenes do not align yet | Informational, not a gate |
| D7 | Streamlit holds no logic | UI can be replaced; logic stays testable | Two entry points (page, CLI) to keep in sync |

## Interfaces
`run_pipeline(request: Request, claims: Sequence[Claim], *, router_algorithm, selection_algorithm,
optimizer_algorithm, voice_algorithm, tts, pad_s) -> PipelineResult`

`PipelineResult`: `status`, `stopped_at`, `stages[]` (stage, ok, summary), `decision`, `selection`,
`scenes`, `scene_report`, `budget`, `budget_source`, `optimize`, `voice`, `voice_in_band_share`,
`timeline`, `messages`.

## Test strategy
Expected values come from the rules in the report (S12, S13, S14, 6–30 scenes) and from module
contracts, not from copying the pipeline's output. The Streamlit page is smoke-tested headlessly with
`streamlit.testing.v1.AppTest` (no exception, expected banner for success, router stop, budget stop).
