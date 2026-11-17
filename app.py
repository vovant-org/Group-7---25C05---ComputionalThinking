"""StoryFrame Studio.   Run:  streamlit run app.py

Three areas: left sidebar (navigation) | main workspace (prompt, then Studio) | right configuration panel
(on the New Project screen). The user interface lives in the `ui/` package; the backend modules are used
exactly as before. The earlier pages are kept as tools: "Classic video maker" (pages/1_Make_video.py)
and "Pipeline lab" (pages/2_Pipeline_lab.py, the full technical dashboard with the benchmark evidence).
"""
import streamlit as st

st.set_page_config(page_title="StoryFrame Studio", page_icon="🎬", layout="wide", initial_sidebar_state="expanded")

from ui import sidebar, state as S, view_generate, view_library, view_new, view_studio  # noqa: E402
from ui import studio_logic as L  # noqa: E402
from ui.theme import css  # noqa: E402

st.markdown(css(), unsafe_allow_html=True)
S.init()
LIB, LIB_ERROR = S.library()
PROJECTS = L.list_projects(S.VIDEOS_DIR)
sidebar.render(PROJECTS)

view = st.session_state["view"]
if view == "new":
    view_new.render(LIB, LIB_ERROR)
elif view == "generate":
    view_generate.render(LIB)
elif view == "studio":
    view_studio.render(PROJECTS)
elif view == "projects":
    view_library.projects(PROJECTS)
elif view == "templates":
    view_library.templates()
elif view == "voices":
    view_library.voices(LIB, LIB_ERROR)
else:
    view_library.settings()
