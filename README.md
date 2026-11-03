# StoryFrame Studio – Group 7 (CSC10014 Computational Thinking, 2026)

## Run
    pip install pytest
    python -m pytest -q                         # unit + regression tests
    python -m evaluation.budget_benchmark       # -> outputs/budget_benchmark.csv
    python -m evaluation.router_benchmark       # -> outputs/router_benchmark.csv
    python -m evaluation.voice_benchmark        # -> outputs/voice_benchmark.csv (simulated TTS)
    python -m evaluation.scene_benchmark        # -> outputs/scene_benchmark.csv
    python -m evaluation.measure_tts --make-manifest   # real TTS measurement workflow, see docs/team-brief-next-steps.md

## Status
| Module | State |
|---|---|
| core/models, core/config | done |
| modules/budget_optimizer | v0, v1, v2 + tests + benchmark (docs/iteration-log.md) |
| modules/router | v0, v1, v2 + 46 labeled cases (docs/iteration-log-router.md) |
| modules/voice_segmenter | F1-F4 + post-TTS repair + tests + benchmark on simulated TTS (docs/iteration-log-voice.md) |
| modules/scene_segmenter | D1 greedy, D2 MMR, D2f MMR + facet, scenes/layouts (docs/iteration-log-scene.md) |
| timeline_assembler, narration script generator, real providers | TODO |

## For team members
Read `docs/team-brief-next-steps.md`; if you use an AI assistant, start from `docs/ai-assistant-prompt.md`.
