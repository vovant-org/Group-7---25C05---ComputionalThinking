"""StoryFrame Studio user interface.

    theme.py          design tokens ("Dark Premium AI Studio") and the CSS
    components.py     pure HTML builders for cards, badges, progress, storyboard, timeline tracks (no Streamlit)
    studio_logic.py   pure logic behind the screens: request composition, validation, cost estimate,
                      pipeline stages, projects on disk, storyboard and track data (no Streamlit)
    state.py          Streamlit session state, navigation, voice library, voice preview
    sidebar.py, view_*.py   the screens

Everything that decides something lives in the pure modules and is unit-tested; the view modules only
draw it. The UI never changes what the pipeline computes: it calls `make_video`, `run_pipeline`
and the voice library exactly as the earlier pages did.
"""
