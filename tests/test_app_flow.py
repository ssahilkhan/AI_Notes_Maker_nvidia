import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

# Isolate the app under test to a throwaway database so tests never touch the
# real data/study.db.
_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="study_app_test_"), "test.db")
os.environ["STUDY_DB_PATH"] = _TEST_DB
os.environ["NVIDIA_API_KEY"] = "nvapi-test-key-for-apptest"

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


def load_app():
    return AppTest.from_file(APP_PATH, default_timeout=60)


def btn_like(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"button '{label}' not found (have: {[b.label for b in at.button]})"
    return matches[0]


def register_account(at, name, email, password):
    btn_like(at, "Create account").click().run()
    at.text_input[0].set_value(name)
    at.text_input[1].set_value(email)
    at.text_input[2].set_value(password)
    at.text_input[3].set_value(password)
    btn_like(at, "Create Account").click().run()


def is_logged_in(at):
    try:
        return bool(at.session_state["authenticated"])
    except (KeyError, AttributeError):
        return False


def login_form_labels(at):
    return [t.label for t in at.text_input]


class TestLoginFlow:
    def test_login_screen_when_unauthenticated(self):
        at = load_app()
        at.run()
        assert not is_logged_in(at)
        assert login_form_labels(at) == ["Email / Username", "Password"]

    def test_bad_login_shows_error(self):
        at = load_app()
        at.run()
        at.text_input[0].set_value("ghost@example.com")
        at.text_input[1].set_value("wrongpass123")
        btn_like(at, "Login").click().run()
        assert any("Incorrect email or password." in str(e.value) for e in at.error)

    def test_register_logs_in_and_opens_workspace(self):
        at = load_app()
        at.run()
        register_account(at, "Sahil", "sahil@example.com", "password123")
        assert is_logged_in(at)
        assert at.session_state["user_name"] == "Sahil"
        assert any("Study sessions" in str(h.value) for h in at.sidebar.header)

    def test_duplicate_registration_rejected(self):
        at1 = load_app()
        at1.run()
        register_account(at1, "Sahil", "dup@example.com", "password123")

        at2 = load_app()
        at2.run()
        btn_like(at2, "Create account").click().run()
        at2.text_input[0].set_value("Sahil")
        at2.text_input[1].set_value("dup@example.com")
        at2.text_input[2].set_value("password123")
        at2.text_input[3].set_value("password123")
        btn_like(at2, "Create Account").click().run()
        assert any("An account with this email already exists." in str(e.value) for e in at2.error)

    def test_login_success_after_registration(self):
        at1 = load_app()
        at1.run()
        register_account(at1, "Sahil", "relogin@example.com", "password123")
        assert is_logged_in(at1)

        at2 = load_app()
        at2.run()
        at2.text_input[0].set_value("relogin@example.com")
        at2.text_input[1].set_value("password123")
        btn_like(at2, "Login").click().run()
        assert is_logged_in(at2)
        assert at2.session_state["user_email"] == "relogin@example.com"


class TestSessionIsolation:
    def test_fresh_session_requires_login_and_hides_others_data(self):
        at_alice = load_app()
        at_alice.run()
        register_account(at_alice, "Alice", "alice@example.com", "password123")
        assert is_logged_in(at_alice)

        at_fresh = load_app()
        at_fresh.run()
        assert not is_logged_in(at_fresh)
        assert login_form_labels(at_fresh) == ["Email / Username", "Password"]

    def test_logout_clears_session(self):
        at = load_app()
        at.run()
        register_account(at, "Alice", "logout@example.com", "password123")
        assert is_logged_in(at)

        btn_like(at, "Logout").click().run()

        assert not is_logged_in(at)
        assert login_form_labels(at) == ["Email / Username", "Password"]


class TestSettingsPersistence:
    def test_workspace_settings_persist_per_user(self):
        at = load_app()
        at.run()
        register_account(at, "Alice", "settings@example.com", "password123")
        assert is_logged_in(at)

        slider = [s for s in at.slider if s.label == "Temperature"][0]
        assert slider.value == 1.0
        slider.set_value(1.7).run()
        assert at.session_state["set_temp"] == 1.7

        # Persistent across a fresh session (same user + DB)
        at2 = load_app()
        at2.run()
        at2.text_input[0].set_value("settings@example.com")
        at2.text_input[1].set_value("password123")
        btn_like(at2, "Login").click().run()
        assert is_logged_in(at2)
        slider2 = [s for s in at2.slider if s.label == "Temperature"][0]
        assert slider2.value == 1.7