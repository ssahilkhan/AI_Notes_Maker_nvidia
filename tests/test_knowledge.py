"""Tests for Phase 3: knowledge_nodes CRUD, grid positioning, and the chip→card flow.
Phase 4: canvas draft bridge (JS payload → persistent position/collapse/delete)."""

import json
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

import core.db as db
import ui.canvas as canvas

_TEST_DB = os.path.join(tempfile.mkdtemp(prefix="study_kn_test_"), "test.db")
os.environ["STUDY_DB_PATH"] = _TEST_DB
os.environ["NVIDIA_API_KEY"] = "nvapi-test-key-for-apptest"

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streamlit_app.py")


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


def _make_user(name="Kn User", email="kn@test.dev"):
    uid = db.create_user(name, email, "hash")
    db.set_current_user(uid)
    return uid


class TestKnowledgeNodeCrud:
    def test_create_and_get(self):
        uid = _make_user()
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "Backpropagation", summary="Chain rule", x=12, y=34)
        row = db.get_knowledge_node(nid)
        assert row["title"] == "Backpropagation"
        assert row["summary"] == "Chain rule"
        assert row["conversation_id"] == conv
        assert row["user_id"] == uid
        assert row["x"] == 12 and row["y"] == 34
        assert row["collapsed"] == 0

    def test_update_and_position(self):
        _make_user()
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "A")
        db.update_knowledge_node(nid, title="A2", collapsed=1)
        db.update_knowledge_node_position(nid, 300, 150)
        row = db.get_knowledge_node(nid)
        assert row["title"] == "A2"
        assert row["collapsed"] == 1
        assert row["x"] == 300 and row["y"] == 150

    def test_delete(self):
        _make_user()
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "A")
        db.delete_knowledge_node(nid)
        assert db.get_knowledge_node(nid) is None

    def test_linked_message_and_parent(self):
        _make_user()
        conv = db.create_conversation()
        mid = db.add_message(conv, "assistant", "x")
        parent = db.create_knowledge_node(conv, "P")
        child = db.create_knowledge_node(conv, "C", message_id=mid, parent_id=parent)
        row = db.get_knowledge_node(child)
        assert row["message_id"] == mid
        assert row["parent_id"] == parent

    def test_cascade_delete_conversation(self):
        _make_user()
        conv = db.create_conversation()
        db.create_knowledge_node(conv, "A")
        db.create_knowledge_node(conv, "B")
        db.delete_conversation(conv)
        assert db.get_conversation_nodes(conv) == []

    def test_user_isolation(self):
        conv_owner = _make_user("U1", "u1@test.dev")
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "secret")
        other = db.create_user("U2", "u2@test.dev", "hash")
        db.set_current_user(other)
        assert db.get_conversation_nodes(conv) == []
        assert db.get_knowledge_node(nid) is None
        with pytest.raises(PermissionError):
            db.create_knowledge_node(conv, "x")

    def test_next_node_position_grid(self):
        _make_user()
        conv = db.create_conversation()
        for i in range(5):
            x, y = db.next_node_position(conv)
            db.create_knowledge_node(conv, f"N{i}", x=x, y=y)
        x, y = db.next_node_position(conv)
        assert x == 80 + (5 % 4) * 220 and y == 60 + (5 // 4) * 150

    def test_conversation_count_in_list(self):
        _make_user()
        conv = db.create_conversation()
        db.create_knowledge_node(conv, "A")
        db.create_knowledge_node(conv, "B")
        rows = [c for c in db.list_conversations() if c["id"] == conv]
        assert rows and rows[0]["knowledge_count"] == 2


class TestChipCreatesCard:
    def test_click_chip_creates_knowledge_node(self):
        at = AppTest.from_file(APP_PATH, default_timeout=20)
        at.run()
        register_account(at, "Chip", "chip@test.dev", "password123")

        uid = db.find_user_by_email("chip@test.dev")["id"]
        db.set_current_user(uid)
        conv = db.create_conversation()
        db.add_message(conv, "user", "Explaining gradient descent.")
        db.add_message(conv, "assistant",
                       "## Update rule\nw -= lr * grad\n\n### Related Concepts\n- Gradient Descent\n- Loss Function")
        at.session_state["current_conv"] = conv
        at.session_state["viewing_doc"] = None
        at.run()

        chip = [b for b in at.button if b.label == "+ Gradient Descent"]
        assert chip, f"chip button missing (have: {[b.label for b in at.button]})"
        chip[0].click().run()

        db.set_current_user(uid)
        nodes = db.get_conversation_nodes(conv)
        assert [n["title"] for n in nodes] == ["Gradient Descent"]
        assert nodes[0]["message_id"] is not None
        assert nodes[0]["x"] > 0 and nodes[0]["y"] > 0


class TestCanvasDraftBridge:
    def test_draft_persists_moves_and_collapse(self):
        _make_user()
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "A", x=0, y=0)
        data = {"moves": {str(nid): [310, 205]}, "collapse": {str(nid): True}}
        canvas._apply_draft(conv, data)
        row = db.get_knowledge_node(nid)
        assert row["x"] == 310 and row["y"] == 205 and row["collapsed"] == 1

    def test_draft_expands_collapsed_node(self):
        _make_user()
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "A", x=0, y=0)
        canvas._apply_draft(conv, {"collapse": {str(nid): True}})
        canvas._apply_draft(conv, {"collapse": {str(nid): False}})
        assert db.get_knowledge_node(nid)["collapsed"] == 0

    def test_draft_deletes_nodes(self):
        _make_user()
        conv = db.create_conversation()
        a = db.create_knowledge_node(conv, "A")
        b = db.create_knowledge_node(conv, "B")
        canvas._apply_draft(conv, {"del": [str(a)]})
        assert db.get_knowledge_node(a) is None
        assert db.get_knowledge_node(b) is not None

    def test_draft_position_roundtrip_and_user_scoping(self):
        owner = _make_user("C1", "c1@test.dev")
        conv = db.create_conversation()
        nid = db.create_knowledge_node(conv, "P", x=10, y=10)
        other = db.create_user("C2", "c2@test.dev", "hash")
        db.set_current_user(other)
        canvas._apply_draft(conv, {"moves": {str(nid): [999, 999]}})
        db.set_current_user(owner)
        assert db.get_knowledge_node(nid)["x"] == 10  # other user's draft ignored

    def test_parse_draft_handles_bad_json(self):
        assert canvas._parse_draft("not json") is None
        assert canvas._parse_draft("") is None
        assert canvas._parse_draft(json.dumps({"moves": {"1": [5, 6]}}))["moves"] == {"1": [5, 6]}

    def test_canvas_header_add_creates_node(self):
        at = AppTest.from_file(APP_PATH, default_timeout=20)
        at.run()
        register_account(at, "Map", "map@test.dev", "password123")

        uid = db.find_user_by_email("map@test.dev")["id"]
        db.set_current_user(uid)
        conv = db.create_conversation()
        at.session_state["current_conv"] = conv
        at.session_state["viewing_doc"] = None
        at.session_state["canvas_mode"] = "split"
        at.run()

        at.text_input(key="kn_new").set_value("Attention Mechanism").run()
        at.button(key="kn_add").click().run()

        db.set_current_user(uid)
        nodes = db.get_conversation_nodes(conv)
        assert [n["title"] for n in nodes] == ["Attention Mechanism"]