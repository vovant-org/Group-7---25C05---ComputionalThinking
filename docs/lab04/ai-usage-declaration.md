# AI usage declaration – Lab04 (Vũ Thành Nam, Group 7)

Policy reminder (from the team brief): AI output is not evidence by itself; every result below comes from code that was actually run.

| Date | Tool | What it produced | How it was verified |
|---|---|---|---|
| 2026-11-05 | Claude (claude.ai chat) | Advice on the feature and artifacts; read the repo (README, logbook, brief, git log, module code) | Cross-checked against the repo files and the Lab04 PDF; the claim "Pipeline demo is not an artifact" was checked against the PDF's artifact table |
| 2026-11-05 | Claude | `specs/001-pipeline-demo/{spec,plan,tasks,design}.md` (incl. 2 Mermaid diagrams) | The two Mermaid blocks in `design.md` parse without error in the Mermaid v10 parser (checked by the AI; not rendered visually, so check the preview on GitHub) |
| 2026-11-05 | Claude | `modules/pipeline/{pipeline,sample_claims,cli}.py` | The AI ran the full suite in its own environment: 224 → 248 passed; ran the CLI on 11 scenarios; student ran `py -m pytest -q` on his machine: 248 passed in 3.76 s (screenshot 06) |
| 2026-11-05 | Claude | `tests/test_pipeline.py` (24 tests) | Expected values taken from the report's rules and module contracts; passed in the AI's environment and on the student's machine (248 passed in total, screenshot 06) |
| 2026-11-05 | Claude | `app.py` (Streamlit), `requirements.txt`, README lines | Headless `AppTest` run (no exception; success, router stop and budget stop banners as expected); the student ran `py -m streamlit run app.py` in a browser and took screenshots 01–05 |
| 2026-11-05 | Claude | `docs/lab04/lab04-report.md`, this file, `docs/lab04/README.md` | commit hashes and run results were taken from the student's own terminal output (`git log`, screenshot 06) |

Mistakes by the AI found during the work are listed in section 9 of `lab04-report.md`.

