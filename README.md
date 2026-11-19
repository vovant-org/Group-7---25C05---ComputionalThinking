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
    python -m streamlit run app.py              # StoryFrame Studio workspace (new UI, see "The workspace" below)
    python -m evaluation.measure_tts --make-manifest   # real TTS measurement workflow, see docs/team-brief-next-steps.md

## The workspace (`python -m streamlit run app.py`)
Requires Python 3.10+. Run these from the project root folder (so `.streamlit/config.toml`, the dark theme, is picked up):

    python -m venv .venv                                    # optional but recommended
    .venv\Scripts\activate                                  # Windows PowerShell  (macOS/Linux: source .venv/bin/activate)
    python -m pip install -r requirements.txt -r requirements-video.txt
    python -m streamlit run app.py

`requirements-video.txt` adds Pillow, numpy and `imageio-ffmpeg` (a bundled FFmpeg), which the video maker needs.
Optional voices: `python -m pip install pyttsx3` (offline system voice) or `edge-tts` (online, sends the narration text to Microsoft).

Always use the `python -m pip ...` / `python -m streamlit ...` form. With several Pythons installed (common on Windows),
a bare `pip` or `streamlit` can belong to a different Python than `python`, and packages then look "missing".

### Troubleshooting
| Message in the app | Cause and fix |
|---|---|
| **FFmpeg was not found** | FFmpeg is neither on PATH nor installed through `imageio-ffmpeg` *for the Python that runs Streamlit*. Run `python -m pip install imageio-ffmpeg`, check with `python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"`, then restart Streamlit (Ctrl+C, run again). Alternative: `winget install Gyan.FFmpeg`, then open a new terminal. |
| `ModuleNotFoundError` for a package you just installed | `pip` and `python` point to different Pythons. Compare `python -c "import sys; print(sys.executable)"` with the path shown by `pip --version`; install with `python -m pip install ...`. |
| Buttons or inputs look white / the theme is light | Streamlit was started outside the project folder, so `.streamlit/config.toml` was not read. `cd` into the project root and restart. |
| **Create Video** is greyed out | Read the red/amber messages above the button; each one names what to fix (empty topic, missing reference text, voice language mismatch, budget too low, FFmpeg). |
| Video has no sound | The *Silent* voice engine is selected (the default when `pyttsx3` is not installed). Install `pyttsx3` or choose the Edge voice in the Voice tab. |
| A topic like "Explain AI" cannot be generated | The REASON step is not built: use a demo template, or paste / upload your own reference text (full sentences of 8-24 words). |

Flow: **New Project → enter topic → configure video → see the cost estimate → Create Video → review the storyboard and timeline → download**.

| Screen | What it does |
|---|---|
| New Project | Prompt composer (topic, optional reference text or `.txt`/`.md` upload, instructions), format cards, duration / budget / language / voice / speed / subtitles, live cost estimate from the Budget Optimizer |
| Generation | Seven-stage tracker; a stage turns green only when the backend log confirms it; live render progress |
| Video Studio | Real MP4 player, timeline (video / audio / subtitles), storyboard (cards or table), read-only properties, quality checks, downloads (MP4, SRT, report JSON) |
| My Projects / Recent | The videos found in `outputs/videos/` |
| Templates | The demo claim packs (sleep, inflation; English and Vietnamese) as one-click starts |
| Voice Library | Voices from `data/voice_library.json`; preview only when `edge-tts` or bundled samples exist |
| Settings | Environment status, links to the original pages (Pipeline lab, Classic video maker), list of what is not built |

Code layout: `app.py` routes; `ui/theme.py` design tokens + CSS; `ui/components.py` reusable HTML components; `ui/adapters.py`
pure reshaping of backend results; `ui/runner.py` the only place that calls the backend; `ui/views/` one module per screen.
`.streamlit/config.toml` sets the dark theme. Tests: `tests/test_ui_layer.py`. Details and the list of simulated / unavailable
features: `docs/ui-redesign.md`.

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
| modules/pipeline + pages/2_Pipeline_lab.py | Lab04 feature: Router → Scene → Budget → Voice → Timeline, CLI + Streamlit lab page (specs/001-pipeline-demo/) |
| ui/ + app.py | "Dark Premium AI Studio" workspace: prompt composer, configuration panel, generation progress, Video Studio (docs/ui-redesign.md) |
| modules/visual_engine | Topic-aware Visual Engine for ANIMATION: topic analysis, per-domain kits, content-aware motion, word-level sync, quality checks (docs/topic-aware-visual-engine.md) |
| narration script generator, real providers, REASON step | TODO |

## For team members
Read `docs/team-brief-next-steps.md`; if you use an AI assistant, start from `docs/ai-assistant-prompt.md`.