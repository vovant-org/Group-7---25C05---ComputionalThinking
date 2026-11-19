"""StoryFrame Studio UI layer (Streamlit).

Only presentation lives here. Every number, stage and file shown comes from the existing backend
(`modules/`, `core/`); nothing in this package plans, scores or renders a video.

  theme.py       design tokens ("Dark Premium AI Studio") and the CSS
  components.py  reusable components that return HTML strings (no Streamlit import, unit-tested)
  adapters.py    pure functions that reshape backend results for the components (unit-tested)
  storage.py     reads and writes the project files that already live in outputs/videos/
  runner.py      the only module that calls the backend: cost estimate and video generation
  widgets.py     Streamlit wrappers (buttons, cards that need clicks, navigation)
  views/         one module per screen
"""
