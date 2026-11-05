# Lab04 submission checklist

| # | Required item | Where |
|---|---|---|
| 1 | Source code of the feature | `modules/pipeline/`, `app.py`, `tests/test_pipeline.py`, `requirements.txt` |
| 2 | Screenshots of the feature in action | `docs/lab04/screenshots/` (list below) |
| 3 | Development report | `docs/lab04/lab04-report.md` (+ `specs/001-pipeline-demo/`) |
| 4 | Git commit log files | `docs/lab04/git-commit-log.txt` (command below) |
| 5 | AI usage declaration | `docs/lab04/ai-usage-declaration.md` |

## Run
    pip install -r requirements.txt
    py -m pytest -q                     # expect 248 passed
    py -m streamlit run app.py
    py -m modules.pipeline.cli "Make a 90-second infographic video about sleep" --topic sleep

## Screenshot list (save as PNG in docs/lab04/screenshots/)
| File | How to produce it |
|---|---|
| `01-success-timeline.png` | Example 1 ("90-second infographic … sleep"), Run, tab **Timeline** |
| `02-success-scenes.png` | Same run, tab **Scenes & modes** |
| `03-router-stop.png` | Example "300-second video about sleep" |
| `04-budget-stop.png` | Example "… budget of 16 credits" |
| `05-timeline-check-fails.png` | Example 1, then set **True speed** to 120 wpm |
| `06-pytest.png` | Terminal with `248 passed` |
Optional: example 2 ("60-second … inflation") shows an S12 failure.

## Commit steps (one commit per Spec Kit phase)
Before starting: `git restore outputs modules/timeline_assembler/assembler.py` (those files only differ by line endings).
    git add docs/team-contributions.md && git commit -m "update logbook"
    git checkout -b lab04-pipeline-demo
    git add specs/001-pipeline-demo/spec.md && git commit -m "Lab04 phase 1 (specify): spec for the pipeline demo"
    git add specs/001-pipeline-demo/plan.md specs/001-pipeline-demo/design.md && git commit -m "Lab04 phase 2 (plan): plan, user story, sequence and activity diagrams"
    git add specs/001-pipeline-demo/tasks.md && git commit -m "Lab04 phase 3 (tasks): task breakdown"
    git add modules/pipeline tests/test_pipeline.py && git commit -m "Lab04 phase 4a (implement): pipeline orchestrator, fixtures, CLI, 24 tests (248 pass)"
    git add app.py requirements.txt README.md && git commit -m "Lab04 phase 4b (implement): Streamlit demo page"
After the screenshots and the filled report: `git add docs/lab04 && git commit -m "Lab04: report, AI declaration, screenshots, commit log"`.

## Export the commit log (PowerShell)
    git log --format="%h %ad %an | %s" --date=short | Out-File -Encoding utf8 docs/lab04/git-commit-log.txt
(run it before the last commit, or run it again and amend; it must list your own commits.)

## Logbook line for `docs/team-contributions.md` (fill the hash yourself)
`| 2026-11-05 | Vũ Thành Nam | Lab04: built the pipeline demo (Router → Scene → Budget → Voice → Timeline), 24 new tests (248 pass), Streamlit page | Commit <hash> |`
and one row in the AI table (see `ai-usage-declaration.md`).
