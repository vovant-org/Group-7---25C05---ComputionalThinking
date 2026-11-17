# AI usage declaration – Lab06 (Vũ Thành Nam, Group 7)

Policy reminder (from the team brief): AI output is not evidence by itself; every result below comes from code that was actually run.

| Date | Tool | What it produced | How it was verified |
|---|---|---|---|
| 2026-11-16 | Claude (Anthropic) | Motion Planner, cut-out animation module (`motion_planner.py`, `animation.py`), changes to `make_video.py`, `render.py`, `pipeline.py` | The AI ran the full suite in its own environment; I ran `py -m pytest` on my machine (431 passed), generated the 90 s demo video and checked S11, S12, S13, S15 on the finished MP4 |
| 2026-11-16 | Claude | `tests/test_animation.py` (56 tests) | Expected values come from the rules in the report; mutation checks showed each rule is caught by a test |
| 2026-11-17 | Claude | `pages/1_Make_video.py`, `modules/pipeline/ui_helpers.py`, subtitle line balancing, `tests/test_video_ui.py` (12 tests) | Headless Streamlit test and screenshots by the AI; I ran the suite (443 passed after merging main) and used the page in my browser |
| 2026-11-17 | Claude | `evaluation/animation_benchmark.py`, `tests/test_animation_benchmark.py`, `docs/iteration-log-animation.md` | I re-ran the benchmark on my machine and compared the numbers (only the draw-time column differs by machine) |
| 2026-11-17 | Claude | Git/PR guidance, logbook text, this file, `lab06-report.md`, `README.md` | Commit hashes and results were copied from my own terminal output |

Mistakes by the AI found during the work are listed in section 7 of `lab06-report.md`.
