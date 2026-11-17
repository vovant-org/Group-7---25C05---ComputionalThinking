# StoryFrame Studio – Group 7 (CSC10014 Computational Thinking, 2026)

## Run
    pip install -r requirements.txt             # use a virtual environment; do not commit env/
    python -m pytest -q                         # unit + regression tests
    python -m evaluation.budget_benchmark       # -> outputs/budget_benchmark.csv
    python -m evaluation.router_benchmark       # -> outputs/router_benchmark.csv
    python -m evaluation.voice_benchmark        # -> outputs/voice_benchmark.csv (simulated TTS)
    python -m evaluation.scene_benchmark        # -> outputs/scene_benchmark.csv
    python -m modules.pipeline.cli "Make a 90-second infographic video about sleep" --topic sleep
    python -m modules.pipeline.cli "Tạo video infographic 90 giây về giấc ngủ" --topic sleep_vi --voice vi-hoaimy
    python -m modules.voice_library.cli [--language vi] [--check]   # list voices / verify them on the TTS engine
    python -m evaluation.visual_engine_benchmark     # -> outputs/visual_engine_benchmark.csv (Topic-aware Visual Engine)
    pip install -r requirements-video.txt       # Pillow, numpy, FFmpeg: needed to make the MP4
    streamlit run app.py                        # StoryFrame Studio (see docs/studio-ui.md); tool pages in its sidebar
    python -m evaluation.measure_tts --make-manifest   # real TTS measurement workflow, see docs/team-brief-next-steps.md

## Status
| Module | State |
|---|---|
| core/models, core/config | done |
| modules/budget_optimizer | v0, v1, v2 + tests + benchmark (docs/iteration-log.md) |
| modules/router | v0, v1, v2 + 46 labeled cases (docs/iteration-log-router.md) |
| modules/voice_segmenter | F1-F4 + post-TTS repair + tests + benchmark on simulated TTS (docs/iteration-log-voice.md) |
| modules/scene_segmenter | D1 greedy, D2 MMR, D2f MMR + facet, scenes/layouts (docs/iteration-log-scene.md) |
| timeline_assembler | v0: S12/S13 checks (pure function) |
| modules/voice_library + providers/edge_tts_provider | 8 EN/VI voices, speaking-speed choice, language check, optional preview (docs/voice-library.md); speaking rates still ASSUMED |
| modules/pipeline | Lab04 feature: Router → Scene → Budget → Voice → Timeline, CLI (specs/001-pipeline-demo/); its dashboard is now `pages/2_Pipeline_lab.py` |
| ui/ + app.py | Studio front end ("Dark Premium AI Studio"): prompt composer, format/voice/cost panel, generation steps, video studio (docs/studio-ui.md) |
| modules/visual_engine | Topic-aware Visual Engine for ANIMATION: topic analysis, per-domain kits, content-aware motion, word-level sync, quality checks (docs/topic-aware-visual-engine.md) |
| narration script generator, real providers, REASON step | TODO |

## For team members
Read `docs/team-brief-next-steps.md`; if you use an AI assistant, start from `docs/ai-assistant-prompt.md`.
