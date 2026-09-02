"""Tests for Phase 5: unified global search (chat + notes + doubts)."""

import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import core.db as db
import core.text as txt

_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="study_gs_test_"), "test.db")
os.environ["STUDY_DB_PATH"] = _TEST_DB
os.environ["NVIDIA_API_KEY"] = "nvapi-test-key-for-apptest"

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


def btn_like(at, label):
    matches = [b for b in at.button if b.label == label]
    assert matches, f"button '{label}' not found"
    return matches[0]


def register_account(at, name, email, password):
    btn_like(at, "Create account").click().run()
    at.text_input[0].set_value(name)
    at.text_input[1].set_value(email)
    at.text_input[2].set_value(password)
    at.text_input[3].set_value(password)
    btn_like(at, "Create Account").click().run()


def _seed_conversation(title, term, kind):
    conv = db.create_conversation()
    db.update_conversation(conv, title=title)
    if kind == "message":
        db.add_message(conv, "user", f"Tell me about {term}.")
        db.add_message(conv, "assistant", f"Here is an answer about {term} in depth.")
    elif kind == "section":
        doc = db.get_or_create_main_document(conv)
        db.upsert_section(doc["id"], "n1", 1, f"Notes on {term}", "text", f"Content about {term}.")
    else:
        doc = db.get_or_create_main_document(conv)
        sec = db.upsert_section(doc["id"], "n1", 1, "Base", "text", "Base content.")
        db.add_doubt(conv, sec, "n1", f"What is {term}?", f"{term} is the answer.")
    return conv


class TestSearchDb:
    def test_finds_messages_across_sessions(self):
        db.create_user("A", "a@test.dev", "hash")
        db.set_current_user(db.find_user_by_email("a@test.dev")["id"])
        c1 = _seed_conversation("Alpha", "gradient descent", "message")
        c2 = _seed_conversation("Beta", "bayes theorem", "message")
        rows = db.search_user_contents("gradient descent")
        conv_ids = [r["conversation"]["id"] for r in rows]
        assert c1 in conv_ids and c2 not in conv_ids
        hit = next(r for r in rows if r["conversation"]["id"] == c1)
        assert any("gradient descent" in m["content"].lower() for m in hit["messages"])

    def test_finds_sections_and_doubts(self):
        db.create_user("B", "b@test.dev", "hash")
        db.set_current_user(db.find_user_by_email("b@test.dev")["id"])
        c1 = _seed_conversation("Docs", "attention", "section")
        c2 = _seed_conversation("Doubt", "attention", "doubt")
        rows = db.search_user_contents("attention")
        by_id = {r["conversation"]["id"]: r for r in rows}
        assert c1 in by_id and c2 in by_id
        assert by_id[c1]["sections"]
        assert by_id[c2]["doubts"]

    def test_respects_user_isolation(self):
        owner = db.create_user("C", "c@test.dev", "hash")
        db.set_current_user(owner)
        _seed_conversation("Mine", "secret phrase", "message")
        other = db.create_user("D", "d@test.dev", "hash")
        db.set_current_user(other)
        assert db.search_user_contents("secret phrase") == []

    def test_finds_by_conversation_title(self):
        db.create_user("E", "e@test.dev", "hash")
        db.set_current_user(db.find_user_by_email("e@test.dev")["id"])
        conv = db.create_conversation()
        db.update_conversation(conv, title="Deep Neural Networks")
        rows = db.search_user_contents("neural")
        assert [r["conversation"]["id"] for r in rows] == [conv]

    def test_finds_knowledge_nodes(self):
        db.create_user("F", "f@test.dev", "hash")
        db.set_current_user(db.find_user_by_email("f@test.dev")["id"])
        conv = db.create_conversation()
        db.create_knowledge_node(conv, "Backpropagation", summary="Chain rule for error gradients.")
        rows = db.search_user_contents("backpropagation")
        assert [r["conversation"]["id"] for r in rows] == [conv]
        hit = next(r for r in rows if r["conversation"]["id"] == conv)
        assert [n["title"] for n in hit["nodes"]] == ["Backpropagation"]

    def test_finds_knowledge_nodes_via_summary(self):
        db.create_user("G", "g@test.dev", "hash")
        db.set_current_user(db.find_user_by_email("g@test.dev")["id"])
        conv = db.create_conversation()
        db.create_knowledge_node(conv, "Activation", summary="ReLU and sigmoid functions.")
        rows = db.search_user_contents("sigmoid")
        assert any(n["title"] == "Activation"
                   for r in rows if r["conversation"]["id"] == conv
                   for n in r["nodes"])


class TestGlimpse:
    def test_snippet_wraps_term(self):
        s = txt.glimpse("the learning rate governs gradient descent updates", "gradient")
        assert "gradient descent" in s

    def test_snippet_short_text(self):
        assert txt.glimpse("hello world", "zzz", 40) == "hello world"


class TestGlobalSearchFlow:
    def test_search_result_jumps_to_conversation(self):
        at = AppTest.from_file(APP_PATH, default_timeout=30)
        at.run()
        register_account(at, "GS", "gs@test.dev", "password123")

        uid = db.find_user_by_email("gs@test.dev")["id"]
        db.set_current_user(uid)
        other_conv = _seed_conversation("Other Chat", "photosynthesis", "message")
        target_conv = _seed_conversation("Target Chat", "superscalar cpu", "message")
        at.session_state["current_conv"] = other_conv
        at.session_state["viewing_doc"] = None
        at.run()

        search_box = [t for t in at.text_input if t.key == "global_search_term"]
        assert search_box, "global search input present on the workspace"
        search_box[0].set_value("superscalar").run()

        result = [b for b in at.button if b.key.startswith("gsm_")]
        assert result, "result button appeared"
        result[0].click().run()

        assert at.session_state["current_conv"] == target_conv
        assert at.session_state["current_conv"] != other_conv