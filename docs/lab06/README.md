# Lab06 submission checklist (alternative option: individual contribution to the group project)

| # | Required item | Where |
|---|---|---|
| 1 | Explanation of my contribution (.md and .pdf) | `docs/lab06/lab06-report.md`, `docs/lab06/lab06-report.pdf` |
| 2 | Source code | `modules/video/animation.py`, `modules/video/motion_planner.py`, `modules/video/make_video.py`, `modules/video/render.py`, `modules/pipeline/pipeline.py`, `pages/1_Make_video.py`, `modules/pipeline/ui_helpers.py`, `modules/video/subtitles.py`, `evaluation/animation_benchmark.py`, `tests/` |
| 3 | Video demonstration | `<fill in: link or file name>` |
| 4 | AI usage declaration | `docs/lab06/ai-usage-declaration.md` |
| 5 | Git commit history | `docs/lab06/git-commit-log.txt` (command below) |

## Run
    pip install -r requirements.txt
    pip install -r requirements-video.txt
    py -m pytest -q --ignore=tests/test_video.py      # expect 444 passed
    py -m streamlit run app.py                        # page "Make video"
    py -m evaluation.animation_benchmark              # about 45 s

## Export the commit log (PowerShell), only my own commits from this lab's period
    git log --author="namvuthanh15" --since="2026-11-16" --format="%h %ad %an | %s" --date=short | Out-File -Encoding utf8 docs/lab06/git-commit-log.txt
Open the file afterwards: it must list your animation and UI commits. If it is empty, the author name differs; run `git log -5 --format="%an"` and use that name.

## Video demonstration (about 3–4 minutes) – what to show
Screen recording of the Make video page creating an animation video
https://drive.google.com/file/d/1dolIBqN64ZPXnzdCyuZFgEjcbtkWUOaK/view?usp=sharing

## Screenshots (save as PNG in docs/lab06/screenshots/)
| File | How to produce it |
|---|---|
| `01-page-idle.png` | Page "Make video" before running |
| `02-animation-video.png` | Animation run, tab Video |
| `03-scenes.png` | Same run, tab Scenes |
| `04-checks.png` | Same run, tab Checks |
| `05-pytest.png` | Terminal with `444 passed` |
| `06-benchmark.png` | Terminal with the benchmark output |

## Logbook line for `docs/team-contributions.md` (fill the hash yourself)
`| 2026-11-19 | Vũ Thành Nam | Lab06: documentation package for the animation format and UI contribution | Commit <hash> |`
