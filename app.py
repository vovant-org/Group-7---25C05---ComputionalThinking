"""StoryFrame Studio: AI video workspace.   Run:  streamlit run app.py

Screens: New Project (prompt composer + configuration), generation progress, Video Studio (preview, timeline,
storyboard, properties), My Projects, Templates, Voice Library, Settings.

This file only routes between screens. The UI lives in `ui/`; all planning, costing and rendering is done by the
existing backend (`modules/`, `core/`) through `ui/runner.py`. The original pipeline-demo page is kept as
`pages/2_Pipeline_lab.py` and the original video page as `pages/1_Make_video.py` (Settings -> Developer tools).
"""
import streamlit as st

st.set_page_config(page_title="StoryFrame Studio", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

from ui import runner, widgets                                   # noqa: E402  (after set_page_config)
from ui import state as S                                        # noqa: E402
from ui.theme import inject_theme                                # noqa: E402
from ui.views import create, generate, projects, settings, studio, templates, voices   # noqa: E402

VIEWS = {"create": create, "generate": generate, "studio": studio, "projects": projects,
         "templates": templates, "voices": voices, "settings": settings}

S.init(runner.default_engine())
inject_theme()          # after S.init: it reads the light/dark choice from the session
widgets.sidebar()
VIEWS.get(st.session_state["view"], create).render()
