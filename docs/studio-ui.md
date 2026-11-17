# StoryFrame Studio user interface

Run: `pip install -r requirements.txt -r requirements-video.txt`, then `streamlit run app.py`.

## Screens
| Screen | What it does |
|---|---|
| New Project | Prompt composer (idea, reference material, instructions) on the left; on the right the format cards, generation settings, voice cards with preview, and the **cost estimate** from the real Budget Optimizer. |
| Generating | Seven steps. They turn green only from the backend: planning is run first (`make_video(render=False)`) and its stage logs confirm steps 1-6; then the render runs and step 7 turns green when the finished MP4 was measured and its criteria computed. |
| Studio | Video preview, status, downloads (MP4, subtitles, report), properties of the selected scene, timeline with Video / Audio / Subtitles tracks, storyboard (cards or table), checks. Built from the `.report.json` of the video, so a video just made and an old one look the same. |
| My Projects, Recent | The videos in `outputs/videos/` (an `.mp4` with its `.report.json`). Empty state when there are none. |
| Templates | The demo claim packs (EN and VI) as one-click starting points. |
| Voice Library | Every voice with preview (when a sample or edge-tts is available) and "use for new projects". |
| Settings | What this computer has (FFmpeg, Pillow, edge-tts, pyttsx3) and the feature status. |

The old pages stay as tools in the sidebar: **Classic video maker** (`pages/1_Make_video.py`) and **Pipeline lab**
(`pages/2_Pipeline_lab.py`, the former `app.py`, with the Router, voice-unit and benchmark evidence tabs and the
algorithm choices).

## Code
`ui/theme.py` tokens and CSS · `ui/components.py` HTML components (escaped, pure) · `ui/studio_logic.py` request
composition, validation, estimate, step mapping, projects, tracks, storyboard (pure, tested in
`tests/test_ui_components.py`) · `ui/state.py` session state and navigation · `ui/sidebar.py`, `ui/view_*.py` the screens.
`.streamlit/config.toml` sets the dark theme colours.

## Honest limits
- **Simulated / assumed:** claims come from demo packs or an extractive heuristic over the user's text (the REASON step is
  not built; nothing is verified against sources); credit cost per render mode and the speaking rates are assumptions;
  the silent engine makes a video without sound.
- **Not built:** Hybrid format, AI clips (CLIP), editing scenes, PDF/Word reference files, accounts and cloud projects.
  The UI shows these as unavailable or read-only and does not pretend otherwise.
- The estimate is a plan made with the simulated TTS; the real run measures the narration and may adjust pauses, speed
  and the number of claims to land within 5 % of the target.
- Example idea cards have no built-in claims: they switch the content to "My reference material", which you must supply.
