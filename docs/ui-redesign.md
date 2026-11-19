# UI redesign: "Dark Premium AI Studio"

Goal: turn the Streamlit testing dashboard into a creative workspace **without touching the backend**.
`core/`, `modules/`, `evaluation/`, `docs/` (existing files) and all existing tests are byte-identical to before.

## Files
| File | Change |
|---|---|
| `app.py` | **Replaced**: now routes between the new screens. Its old content lives on as `pages/2_Pipeline_lab.py` |
| `pages/2_Pipeline_lab.py` | The original `app.py` (algorithm comparison, simulated TTS, benchmark evidence). Only the page title and 2 lines for the shared look changed |
| `pages/1_Make_video.py` | Original video page. 2 lines added (shared look + link back). Existing `AppTest` tests target it and are unaffected |
| `.streamlit/config.toml` | New: dark theme with the brief's palette |
| `ui/theme.py` | New: tokens, CSS, `inject_theme()` |
| `ui/components.py` | New: sidebar brand/profile, badges, metric card, format card, voice card, budget card, progress tracker, storyboard card, timeline tracks, properties panel, empty state, alert |
| `ui/adapters.py` | New: pure functions (stage states, cost estimate, validation, SRT parsing, storyboard and timeline data) |
| `ui/storage.py` | New: lists/loads projects from `outputs/videos/`; writes one optional `<id>.project.json` |
| `ui/runner.py` | New: the only module calling the backend (`run_pipeline` for the estimate, `make_video` for generation) |
| `ui/state.py`, `ui/widgets.py`, `ui/views/*` | New: session state, version-safe Streamlit wrappers, one module per screen |
| `tests/test_ui_layer.py` | New: 25 tests of the pure UI logic |
| `requirements.txt`, `README.md` | `streamlit>=1.31`; workspace section |

## How the brief maps to the backend
* **Seven progress stages** are read from the pipeline stage logs: Understanding = Router, Planning = claim selection, Organizing
  = Scene Segmenter, Optimizing = Budget Optimizer, Narration = Voice Segmenter + the engine's measured durations, Timeline =
  Timeline Assembler **and** the rendered MP4, Verifying = the S11/S12/S13/S15 checks of the finished file.
  A stage is never drawn as done without that confirmation (tested). The backend runs as one blocking call, so stages appear when
  it ends; only frame rendering has a live bar (its real `progress` callback).
* **Cost estimate** = a planning pass of the real pipeline (Router, Segmenter, Budget Optimizer, Voice Segmenter, Timeline) with the
  project's simulated TTS timing. No render, no audio.
* **Timeline tracks**: video = scene starts/lengths from the report; subtitles = cues of the `.srt` the renderer wrote; audio =
  per-scene narration length (saved in the project record, else the span of that scene's cues).
* **Scene title**: the backend has none, so the card shows the explanation pattern (e.g. "Cause → effect") or the layout name.

## Not implemented / simulated (shown as such in the UI)
* **Researching a topic** (REASON step): content comes from a demo claim pack or from sentences extracted from your own text. The four
  example prompts only fill the topic box and ask for reference text; no pack exists for them.
* **Hybrid**: card shown as "Coming soon" and disabled (the backend stops with a message).
* **AI clips (CLIP)**: unavailable; animation scenes are LAYERED cut-outs.
* **Credits** are assumed per-mode costs, not money. Speaking rates are assumed until measured.
* **Scene editing** and accounts/cloud projects do not exist: the properties panel is read-only; "Group 7 · Local workspace" is a label.
* **Voice preview** appears only when the existing preview works (edge-tts installed, or bundled samples).
* **Silent engine** produces a silent video; the UI says so. Default engine is the offline system voice when `pyttsx3` is installed.
* Projects made before this UI (e.g. `sleep.mp4`) have no claim-to-scene links; the properties panel says "not recorded".
* Algorithm selectors (router/optimizer/segmenter) are not passed through `make_video`, so they stay in the Pipeline lab instead of
  being offered where they would have no effect.

## Verification status
Run in the build environment (no network, no Streamlit): the pure logic tests (25 pass), the backend end to end (real 90 s MP4 via the new
runner), every screen executed against a recording stand-in for Streamlit (no Python errors), and the components/CSS rendered in Chromium.
**Not verified there:** `streamlit run app.py` itself, native widget styling, the tablet breakpoint and the existing `AppTest` tests. Run
`streamlit run app.py` and `python -m pytest -q` once on your machine.
