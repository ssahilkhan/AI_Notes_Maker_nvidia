import sqlite3

import pytest

import core.db as db
from core import memory, notes, pdf, prompts, text  # noqa: F401  (existing functionality)
from tests.conftest import make_user


def conv_for(user, subject):
    """Create a conversation (with one message) as the given authenticated user."""
    db.set_current_user(user["id"])
    conv_id = db.create_conversation(subject)
    db.add_message(conv_id, "user", f"Tell me about {subject}")
    return conv_id


class TestProtectedWorkspace:
    def test_unauthenticated_reads_are_empty(self):
        db.set_current_user(None)
        assert db.list_conversations() == []
        assert db.get_conversation(123) is None
        assert db.get_messages(123) == []
        assert db.list_documents(123) == []
        assert db.get_doubts(123) == []
        assert db.get_images(123) == []
        assert db.search_conversation(123, "x") == {"messages": [], "sections": [], "doubts": []}

    def test_unauthenticated_writes_raise(self):
        db.set_current_user(None)
        with pytest.raises(PermissionError):
            db.create_conversation("Maths")

    def test_session_persistence(self):
        """Once authenticated, the thread-local session persists across calls."""
        user = make_user(email="persist@example.com")
        conv_id = conv_for(user, "Python")
        db.set_current_user(user["id"])  # same logged-in session continues
        assert [c["id"] for c in db.list_conversations()] == [conv_id]


class TestChatIsolation:
    def test_each_user_sees_own_chat(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")
        a_conv = conv_for(alice, "Deep Learning")
        b_conv = conv_for(bob, "DBMS")

        db.set_current_user(alice["id"])
        a_subjects = [c["subject"] for c in db.list_conversations()]
        assert "Deep Learning" in a_subjects and "DBMS" not in a_subjects

        db.set_current_user(bob["id"])
        b_subjects = [c["subject"] for c in db.list_conversations()]
        assert "DBMS" in b_subjects and "Deep Learning" not in b_subjects

        assert a_conv != b_conv

    def test_a_cannot_access_bs_conversation(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")
        b_conv = conv_for(bob, "Statistics")

        db.set_current_user(alice["id"])
        assert db.get_conversation(b_conv) is None
        assert db.get_messages(b_conv) == []
        with pytest.raises(PermissionError):
            db.add_message(b_conv, "user", "hacked")
        db.delete_conversation(b_conv)  # must be a no-op

        db.set_current_user(bob["id"])
        assert db.get_conversation(b_conv) is not None

    def test_two_user_security_scenario(self):
        """Spec 21: A creates 'Deep Learning', B must not see it; B creates 'DBMS', A must not see it."""
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")

        conv_for(alice, "Deep Learning")
        conv_for(bob, "DBMS")

        db.set_current_user(bob["id"])
        b_subjects = [c["subject"] for c in db.list_conversations()]
        assert "Deep Learning" not in b_subjects
        assert "DBMS" in b_subjects

        db.set_current_user(alice["id"])
        a_subjects = [c["subject"] for c in db.list_conversations()]
        assert "DBMS" not in a_subjects
        assert "Deep Learning" in a_subjects


class TestNotesIsolation:
    def test_notes_are_user_specific(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")

        a_doc_id = self.bootstrap_doc(alice, "Bayes Theorem")
        b_doc_id = self.bootstrap_doc(bob, "Linked Lists")

        db.set_current_user(bob["id"])
        assert db.get_document(a_doc_id) is None
        b_docs = db.list_documents(self._conv_of(b_doc_id))
        assert len(b_docs) == 1 and b_docs[0]["title"] == "Linked Lists"
        assert db.get_sections(a_doc_id) == []

        db.set_current_user(alice["id"])
        assert db.get_document(a_doc_id) is not None
        assert db.get_document(b_doc_id) is None

    def bootstrap_doc(self, user, title):
        conv = conv_for(user, title)
        db.set_current_user(user["id"])
        doc_id = db.create_document(conv, "main", title=title)
        db.upsert_section(doc_id, "nA1", 1, title, "text", "content about " + title)
        return doc_id

    def _conv_of(self, doc_id):
        return db.get_document(doc_id)["conversation_id"]


class TestDoubtsIsolation:
    def test_doubts_are_user_specific(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")

        db.set_current_user(alice["id"])
        a_conv = db.create_conversation("Maths")
        db.add_doubt(a_conv, None, "n1", "alice-doubt", "answer-a")

        db.set_current_user(bob["id"])
        b_conv = db.create_conversation("Maths")
        db.add_doubt(b_conv, None, "n2", "bob-doubt", "answer-b")

        assert db.get_doubts(a_conv) == []
        assert [d["question"] for d in db.get_doubts(b_conv)] == ["bob-doubt"]

        db.set_current_user(alice["id"])
        assert [d["question"] for d in db.get_doubts(a_conv)] == ["alice-doubt"]
        assert db.get_doubts(b_conv) == []


class TestMemoryIsolation:
    def test_memories_are_user_specific(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")

        db.set_current_user(alice["id"])
        a_conv = db.create_conversation("ML")
        db.set_memory(a_conv, "summary", "alice-summary")

        db.set_current_user(bob["id"])
        b_conv = db.create_conversation("ML")
        db.set_memory(b_conv, "summary", "bob-summary")

        assert db.get_memory(a_conv, "summary") == ""
        assert db.get_memory(b_conv, "summary") == "bob-summary"

        db.set_current_user(alice["id"])
        assert db.get_memory(a_conv, "summary") == "alice-summary"
        assert db.get_memory(b_conv, "summary") == ""


class TestSettingsIsolation:
    def test_settings_are_user_specific(self):
        alice = make_user("Alice", "alice@example.com")
        bob = make_user("Bob", "bob@example.com")

        db.save_user_settings(alice["id"], {"model": "nvidia/model-a", "temperature": 1.5})
        db.save_user_settings(bob["id"], {"model": "nvidia/model-b", "temperature": 0.2})

        a = db.get_user_settings(alice["id"])
        b = db.get_user_settings(bob["id"])
        assert a["model"] == "nvidia/model-a" and b["model"] == "nvidia/model-b"
        assert a["temperature"] != b["temperature"]

    def test_settings_update_in_place(self):
        user = make_user(email="settings@example.com")
        db.save_user_settings(user["id"], {"temperature": 0.5})
        db.save_user_settings(user["id"], {"temperature": 1.7})
        assert db.get_user_settings(user["id"])["temperature"] == 1.7


class TestMigration:
    def test_migration_preserves_existing_data(self, monkeypatch, tmp_path):
        old = tmp_path / "old.db"
        conn = sqlite3.connect(str(old))
        conn.executescript(
            """
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New Study Session',
                subject TEXT DEFAULT '',
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE note_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'main',
                title TEXT DEFAULT '',
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE note_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                node_id TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                heading TEXT DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE doubts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                section_id INTEGER,
                node_id TEXT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                section_id INTEGER,
                url TEXT NOT NULL,
                thumbnail TEXT DEFAULT '',
                source TEXT DEFAULT '',
                caption TEXT DEFAULT '',
                kind TEXT NOT NULL DEFAULT 'web',
                created_at TEXT NOT NULL
            );
            """
        )
        now = "2026-08-30T12:00:00"
        cur = conn.execute(
            "INSERT INTO conversations (title, subject, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("Deep Learning", "Deep Learning", now, now),
        )
        conv = cur.lastrowid
        conn.execute("INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                     (conv, "user", "Explain backprop", now))
        conn.execute("INSERT INTO memories (conversation_id, kind, content, updated_at) VALUES (?, ?, ?, ?)",
                     (conv, "summary", "old summary", now))
        conn.execute("INSERT INTO note_documents (conversation_id, kind, title, version, created_at, updated_at) VALUES (?, 'main', ?, 1, ?, ?)",
                     (conv, "DL notes", now, now))
        conn.execute("INSERT INTO note_sections (document_id, node_id, position, heading, kind, content, created_at, updated_at) VALUES (?, 'n1', 1, 'Backprop', 'text', ?, ?, ?)",
                     (conv, "backprop content", now, now))
        conn.execute("INSERT INTO doubts (conversation_id, section_id, node_id, question, answer, created_at) VALUES (?, NULL, 'n1', 'Why?', 'Because', ?)",
                     (conv, now))
        conn.execute("INSERT INTO images (conversation_id, section_id, url, created_at) VALUES (?, NULL, 'http://x/img.png', ?)",
                     (conv, now))
        conn.commit()
        conn.close()

        monkeypatch.setenv("STUDY_DB_PATH", str(old))
        db.reset()
        db.get_conn()

        local = db.find_user_by_email(db.LOCAL_USER_EMAIL)
        assert local is not None, "default local user must be created during migration"

        db.set_current_user(local["id"])
        convs = db.list_conversations()
        assert len(convs) == 1 and convs[0]["title"] == "Deep Learning"

        msgs = db.get_messages(conv)
        assert len(msgs) == 1 and msgs[0]["content"] == "Explain backprop"
        assert db.get_memory(conv, "summary") == "old summary"

        doc = db.list_documents(conv)[0]
        assert db.get_sections(doc["id"])[0]["heading"] == "Backprop"
        assert db.get_doubts(conv)[0]["question"] == "Why?"
        assert len(db.get_images(conv)) == 1

    def test_migrate_twice_is_idempotent(self, monkeypatch, tmp_path):
        old = tmp_path / "twice.db"
        sqlite3.connect(str(old)).close()
        monkeypatch.setenv("STUDY_DB_PATH", str(old))
        db.reset()
        db.get_conn()
        db.reset()
        db.get_conn()  # must not raise or duplicate columns
        assert True


class TestExistingFunctionality:
    def test_core_modules_import(self):
        assert prompts.ACADEMIC_SYSTEM_PROMPT
        assert text.render_md_text("$$x=1$$") == "$$x=1$$"
        assert notes.parse_response("## Definition\ncore concept")[0]["heading"] == "Definition"
        assert callable(pdf.export_document_pdf)