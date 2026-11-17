# Lab06 Report – Individual contribution to the group project: ANIMATION video format and video-maker UI

Student: Vũ Thành Nam (25127097), Group 7 "StoryFrame Studio". Course CSC10014 – Computational Thinking, class 25C05.
Date: 2026-11-17. Repository: the Group 7 project repo (branches `feat/...`, merged by pull request).

Lab06 allows submitting individual contributions to the group project instead of a separate website. This report
takes that option. **No OpenStreetMap or OpenWeather API is used**; the lecturer confirmed that no API is needed for this option.

## 1. What the project is
StoryFrame Studio turns a text request ("Make a 90-second animated video about sleep") into an MP4 with voice-over and
subtitles. The pipeline is Router → Scene Segmenter → Budget Optimizer → Voice Segmenter → Timeline Assembler → video
rendering. A teammate (Thiện) built the INFOGRAPHIC video format. My contribution adds the second format and improves the page.

## 2. My contribution (what I did, and what I did not)
| Part | What it is | Files |
|---|---|---|
| ANIMATION format | A cut-out character (body, head, two arms) with keyframe tracks acts out each claim next to a prop (cause→effect blocks, bars, stairs, chart, light bulb, speech bubble). Every frame is drawn by code (Pillow), no AI images. | `modules/video/animation.py` |
| Motion Planner | Fixed rules (no AI) choose pose, prop and energy of a scene from its position, `explain_pattern` and importance. Hook waves; important scenes move more; the character alternates sides. | `modules/video/motion_planner.py` |
| Integration | `make_video` builds the animation or infographic path from the requested format; the renderer picks a layered renderer per scene; `run_pipeline` can exclude render modes that cannot be produced (CLIP). The report is format-aware (S11 motion ratio for animation, S15 not applicable). | `modules/video/make_video.py`, `modules/video/render.py`, `modules/pipeline/pipeline.py` |
| Video page (UI) | Format choice (Auto / Infographic / Animation), example requests, headline metrics, tabs Video / Scenes / Checks / Report, per-scene pose/prop/energy table, download of MP4, subtitles and report. | `pages/1_Make_video.py`, `modules/pipeline/ui_helpers.py` |
| Subtitle fix | Line breaks are balanced so a subtitle never ends with a single orphan word. | `modules/video/subtitles.py` |
| Tests | 56 tests for animation, 12 for the UI, 1 for the benchmark. | `tests/test_animation.py`, `tests/test_video_ui.py`, `tests/test_animation_benchmark.py` |
| Benchmark and log | Before/after measurements of motion and of the duration loop. | `evaluation/animation_benchmark.py`, `docs/iteration-log-animation.md`, `outputs/animation_*.csv` |

Not mine: the INFOGRAPHIC format, the Router, Scene Segmenter, Budget Optimizer, Voice Segmenter and Timeline Assembler
logic that the animation reuses (the Router and Timeline Assembler were improved earlier by me in Lab04 work; see `docs/lab04/`).
**Not built by anyone yet:** the HYBRID format, and CLIP (AI image-to-video) clips, so every animation scene is a drawn cut-out ("LAYERED").

## 3. How it works (short)
1. The Router reads the request and decides the format (the UI choice overrides the words of the request).
2. For ANIMATION the Budget Optimizer may only use render modes that can be produced here; CLIP is excluded, so all scenes are LAYERED (motion ratio 100%, criterion S11).
3. For every scene the Motion Planner returns pose, prop, energy and side. `compose_animation_scene` builds layers with keyframe `Track`s
   (position, rotation, scale, alpha over the scene's fraction of time `u`), so the movement follows the scene length.
4. `LayerRenderer.frame(t)` draws each frame (2× supersampling). The subtitle band is kept free of drawing so subtitles stay readable.
5. FFmpeg joins the frames with the voice-over and subtitles. If the length misses the target, the existing loop (N0 → N4 → N3 → N2) adjusts pauses, speed and number of claims.

## 4. Verification
| Check | Result |
|---|---|
| Full test suite after the change | 444 passed (run on my machine) |
| Demo video, 90 s sleep request, animation | S11 100% of scenes move; S12 total 89.42 s (needs 60–120 s); S13 0.6% off target (needs ≤ 5%); S15 not applicable (no text drawn inside animation scenes) |
| Streamlit page | Opened in a browser, created an animation video with the silent engine, checked all four tabs (screenshots in `docs/lab06/screenshots/`) |
| Subtitle fix | Unit tests show the one-word last line disappears and no extra line is added |

### Benchmark (`docs/iteration-log-animation.md`, `python -m evaluation.animation_benchmark`)
| A. Motion on real frames (24 scenes per variant) | scenes that move | motion score |
|---|---|---|
| v0 still character | 0/24 | 0.000 |
| v1 keyframes, uniform energy | 24/24 | 2.671 |
| v2 planned energy (shipped) | 24/24 | 2.753 |

The real gain is v0 → v1. Planned energy makes the key scenes (hook, summary, importance ≥ 0.75) move about 7% more (2.618 → 2.796) and leaves the others unchanged; this is a small effect.

| B. Duration loop, animation format, 42 runs with a simulated voice | passes S12 and S13 |
|---|---|
| without the adjustment loop | 3/42 |
| with the loop | 35/42 |

The 7 failures are slow voices (120 wpm, and one 135 wpm run); the infographic format fails the same 7 runs, so this is a limit of the loop and of the small claim packs, not of the animation.

## 5. Limitations
- Animation is a drawn cut-out character (report option L2), not AI-generated video. CLIP and HYBRID are not built.
- The motion score counts pixel change; it does not judge whether the movement looks good. Quality was judged by watching the video.
- Claims are hand-written demo packs; narration speed in the benchmark is simulated. With the silent engine the demo video has no sound; the demo video uses the silent engine, so it has no sound.

## 6. Contribution statement
I (Vũ Thành Nam) built the ANIMATION format and the UI changes above and wrote their tests. My teammate Thiện built the INFOGRAPHIC format and merged my pull requests after review. I ran the full test suite and the Streamlit page on my own machine and made the commits with my own account (see `git-commit-log.txt`).
An AI assistant (Claude) drafted most of the code and tests; what it did, how I checked it, and its mistakes are in `ai-usage-declaration.md` and section 7.

## 7. Things the AI got wrong during this work
- A test expected the wiggle animation to peak at exactly 7.0; the sampled peak is 6.90 because a cycle has 10 keyframes. The test was relaxed to `6.8 < peak <= 7.0`.
- It advised running the video module with `python -I`, which fails because the project folder is not on the path; `PYTHONPATH=.` was used instead.
- The repository's `tests/test_video.py` is a copy of the Streamlit page, so pytest cannot collect it; the AI found this and the suite is run with `--ignore=tests/test_video.py` until the real tests are restored.
- It first advised not to commit the benchmark CSV files, then corrected itself after checking that `outputs/` already tracks the other benchmark CSVs.
- Deliberate bugs ("mutations": a wrong importance threshold, CLIP not excluded, the character's ground line inside the subtitle band) were each caught by a test, which is how we know those tests check something.
