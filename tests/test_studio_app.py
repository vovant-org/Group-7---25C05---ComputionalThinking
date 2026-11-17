"""The Studio front end, run headless with Streamlit's AppTest (like tests/test_video_ui.py). The logic behind it is
tested without Streamlit in tests/test_ui_components.py; these tests only check that the screens start and navigate."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _text(at):
    return " ".join(m.value for m in at.markdown)


def test_studio_starts_on_the_prompt_screen_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert "What would you like to create today?" in _text(at)
    assert at.button(key="create").disabled                    # no idea typed yet


def test_typing_an_idea_with_a_demo_pack_enables_create_and_shows_the_estimate():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_area(key="cfg_idea").set_value("How sleep works").run()
    assert not at.exception and not at.button(key="create").disabled
    assert "Estimated cost" in _text(at)


@pytest.mark.parametrize("nav, title", [("templates", "Templates"), ("voices", "Voice Library"),
                                        ("settings", "Settings"), ("projects", "My Projects")])
def test_sidebar_navigation_opens_each_screen(nav, title):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.button(key=f"nav_{nav}").click().run()
    assert not at.exception and title in _text(at)
