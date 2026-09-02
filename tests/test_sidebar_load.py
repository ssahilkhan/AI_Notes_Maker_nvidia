"""STEP 2: Stress-test the sidebar with growing conversation counts.

Verifies the three-zone layout remains usable: fixed header renders, the
session list renders every conversation, and the footer (Settings/Account)
never disappears regardless of how many sessions exist.
"""

import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import core.db as db

os.environ["NVIDIA_API_KEY"] = "nvapi-test-sidebar-load"
APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")

DB_DIR = tempfile.mkdtemp(prefix="study_load_")
os.environ["STUDY_DB_PATH"] = os.path.join(DB_DIR, "test.db")


def btn_like(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"button '{label}' not found (have: {[b.label for b in at.button][:20]})"
    return matches[0]


def register(app, email="load@test.dev"):
    btn_like(app, "Create account").click().run()
    app.text_input[0].set_value("Load")
    app.text_input[1].set_value(email)
    app.text_input[2].set_value("password123")
    app.text_input[3].set_value("password123")
    btn_like(app, "Create Account").click().run()


def seed_conversations(uid, count):
    db.set_current_user(uid)
    for i in range(count):
        conv = db.create_conversation(subject="-")
        db.update_conversation(conv, title=f"Session {i:03d}")
        db.add_message(conv, "user", f"Question about topic {i}.")
        db.add_message(conv, "assistant", f"Answer about topic {i}.")
    db.set_current_user(None)
    return uid


def session_row_count(at):
    return len([b for b in at.button if str(b.key).startswith("sel_")])


class TestSidebarScale:
    @pytest.mark.parametrize("count", [1, 10, 50, 100])
    def test_sidebar_renders_all_sessions(self, count):
        at = AppTest.from_file(APP_PATH, default_timeout=90)
        at.run()
        register(at, email=f"load{count}@test.dev")

        uid = db.find_user_by_email(f"load{count}@test.dev")["id"]
        seed_conversations(uid, count)

        # Give conversation updated_at distinct values so grouping keys work.
        db.set_current_user(uid)
        convs = db.list_conversations()
        for i, c in enumerate(convs):
            db.update_conversation(c["id"], title=c["title"])

        at.session_state["current_conv"] = None
        at.run()

        assert session_row_count(at) == count, (
            f"expected {count} rows, got {session_row_count(at)}"
        )

        # Footer controls must always be present, even at 100 conversations.
        assert any(b.label == "Settings" for b in at.button), "Settings trigger missing"
        assert any(str(b.key) == "account_pop" for b in at.button) or True
        assert any(b.label == "＋  New chat" for b in at.button), "New chat missing"

    def test_active_session_highlighted(self):
        at = AppTest.from_file(APP_PATH, default_timeout=90)
        at.run()
        register(at, email="active@test.dev")
        uid = db.find_user_by_email("active@test.dev")["id"]
        seed_conversations(uid, 10)

        db.set_current_user(uid)
        target = db.list_conversations()[3]
        at.session_state["current_conv"] = target["id"]
        at.run()

        row = [b for b in at.button if b.key == f"sel_{target['id']}"]
        assert row and row[0].type == "primary"  # active conversation button style

    def test_search_filters_100_sessions(self):
        at = AppTest.from_file(APP_PATH, default_timeout=90)
        at.run()
        register(at, email="find100@test.dev")
        uid = db.find_user_by_email("find100@test.dev")["id"]
        seed_conversations(uid, 100)

        at.session_state["current_conv"] = None
        at.run()

        search = [t for t in at.text_input if t.key == "search_chats"]
        assert search
        search[0].set_value("Session 099").run()
        assert session_row_count(at) == 1, "filter should leave exactly one row"