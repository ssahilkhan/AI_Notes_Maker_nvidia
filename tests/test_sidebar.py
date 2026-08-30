import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

os.environ["NVIDIA_API_KEY"] = "nvapi-test-sidebar"
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


@pytest.fixture
def app():
    # Each test gets a completely fresh database so AppTest subprocesses never
    # collide with users/sessions created by another test.
    db_dir = tempfile.mkdtemp(prefix="study_side_")
    os.environ["STUDY_DB_PATH"] = os.path.join(db_dir, "test.db")
    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    return at


def btn(at, label):
    m = [b for b in at.button if b.label == label]
    assert m, f"button '{label}' not found (have: {[b.label for b in at.button]})"
    return m[0]


def register(at, email="side@example.com", name="Side", pw="password123"):
    btn(at, "Create account").click().run()
    at.text_input[0].set_value(name)
    at.text_input[1].set_value(email)
    at.text_input[2].set_value(pw)
    at.text_input[3].set_value(pw)
    btn(at, "Create Account").click().run()


def session_labels(at):
    """Labels of the rendered session rows (title+meta HTML)."""
    return [b.label for b in at.button if "<span class=\"pr-title\">" in str(b.label)]


class TestSidebarRendering:
    def test_new_chat_creates_and_renders_session(self, app):
        register(app)
        assert app.session_state["authenticated"] is True
        assert btn(app, "＋  New chat") is not None
        btn(app, "＋  New chat").click().run()
        assert any("New Study Session" in lbl for lbl in session_labels(app))

    def test_clicking_session_row_opens_it(self, app):
        register(app)
        btn(app, "＋  New chat").click().run()
        candidates = [b for b in app.button if "New Study Session" in str(b.label)]
        assert candidates
        candidates[0].click().run()
        assert app.session_state["current_conv"] is not None

    def test_search_filters_sessions(self, app):
        register(app)
        btn(app, "＋  New chat").click().run()
        search = [t for t in app.text_input if t.key == "search_chats"]
        assert search, "search box present in sidebar"
        search[0].set_value("zzz-not-found").run()
        assert any("No sessions found" in str(c.value) for c in app.caption)

    def test_logout_from_account_menu(self, app):
        register(app, email="logout2@example.com")
        assert app.session_state["authenticated"] is True
        btn(app, "Logout").click().run()
        # cleared to the login form
        assert [t.label for t in app.text_input] == ["Email / Username", "Password"]
        assert not session_labels(app)  # no session rows while logged out