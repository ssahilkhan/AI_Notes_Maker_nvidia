import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "study.db"
LOCAL_USER_EMAIL = "local@local.invalid"
LOCAL_USER_NAME = "Default Local User"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Study Session',
    subject TEXT DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS note_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'main',
    title TEXT DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS note_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES note_documents(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    heading TEXT DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'text',
    content TEXT NOT NULL DEFAULT '',
    message_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doubts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES note_sections(id) ON DELETE SET NULL,
    node_id TEXT,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES note_sections(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    thumbnail TEXT DEFAULT '',
    source TEXT DEFAULT '',
    caption TEXT DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'web',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES note_sections(id) ON DELETE SET NULL,
    message_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    content TEXT DEFAULT '',
    x REAL DEFAULT 0,
    y REAL DEFAULT 0,
    collapsed INTEGER DEFAULT 0,
    parent_id INTEGER REFERENCES knowledge_nodes(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_kn_conv ON knowledge_nodes(conversation_id);
CREATE INDEX IF NOT EXISTS idx_kn_user ON knowledge_nodes(user_id);
"""

_lock = threading.Lock()
_conn = None

_local = threading.local()


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _db_path():
    return Path(os.environ.get("STUDY_DB_PATH") or DEFAULT_DB_PATH)


def _migrate(conn):
    """Bring an older database up to the current schema safely."""
    table_cols = {}
    for tbl in ("conversations", "messages", "memories", "note_documents",
                "note_sections", "doubts", "images"):
        table_cols[tbl] = [r[1] for r in conn.execute(f"PRAGMA table_info({tbl})").fetchall()]

    for tbl in ("conversations", "messages", "memories", "note_documents",
                "note_sections", "doubts", "images"):
        if "user_id" not in table_cols[tbl]:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN user_id INTEGER")

    if "message_id" not in table_cols["note_sections"]:
        conn.execute("ALTER TABLE note_sections ADD COLUMN message_id INTEGER")

    # Safety net: existing pre-auth data should never be silently deleted.
    orphaned = conn.execute("SELECT COUNT(*) FROM conversations WHERE user_id IS NULL").fetchone()[0]
    if orphaned:
        local_id, _ = _ensure_local_user(conn)
        conn.execute("UPDATE conversations SET user_id = ? WHERE user_id IS NULL", (local_id,))
        for tbl in ("messages", "memories", "note_documents", "doubts", "images"):
            conn.execute(
                f"""UPDATE {tbl}
                    SET user_id = COALESCE(
                        (SELECT c.user_id FROM conversations c WHERE c.id = {tbl}.conversation_id),
                        ?)
                    WHERE user_id IS NULL""",
                (local_id,),
            )
        conn.execute(
            """UPDATE note_sections
               SET user_id = COALESCE(
                   (SELECT d.user_id FROM note_documents d WHERE d.id = note_sections.document_id),
                   ?)
               WHERE user_id IS NULL""",
            (local_id,),
        )
    elif conn.execute("SELECT COUNT(*) FROM users WHERE email = ?", (LOCAL_USER_EMAIL,)).fetchone()[0] == 0:
        _ensure_local_user(conn)

    # user-scoped + original foreign-key lookup indexes (after columns exist)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_conv ON memories(conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_conv ON note_documents(conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_user ON note_documents(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sections_doc ON note_sections(document_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sections_user ON note_sections(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doubts_conv ON doubts(conversation_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_doubts_user ON doubts(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_images_user ON images(user_id)")
    conn.commit()


def _ensure_local_user(conn):
    row = conn.execute("SELECT id FROM users WHERE email = ?", (LOCAL_USER_EMAIL,)).fetchone()
    if row:
        return row["id"], False
    from core import auth

    now = _now()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (LOCAL_USER_NAME, LOCAL_USER_EMAIL, auth.hash_password(os.urandom(32).hex()), now, now),
    )
    return cur.lastrowid, True


def get_conn():
    global _conn
    with _lock:
        if _conn is None:
            path = _db_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(path), check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys = ON")
            _conn.executescript(SCHEMA)
            _conn.commit()
            _migrate(_conn)
        return _conn


def reset():
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
    set_current_user(None)


# ----------------------------------------------------------------------------
# Authenticated user context (thread-local: one Streamlit session per thread)
# ----------------------------------------------------------------------------

def set_current_user(user_id):
    _local.user_id = user_id


def current_user_id():
    return getattr(_local, "user_id", None)


def _uid():
    uid = current_user_id()
    if not uid:
        raise PermissionError("No authenticated user in this context.")
    return uid


# ----------------------------------------------------------------------------
# Low-level helpers
# ----------------------------------------------------------------------------

def execute(sql, params=()):
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def query_all(sql, params=()):
    conn = get_conn()
    with _lock:
        return conn.execute(sql, params).fetchall()


def query_one(sql, params=()):
    conn = get_conn()
    with _lock:
        return conn.execute(sql, params).fetchone()


# ----------------------------------------------------------------------------
# Users
# ----------------------------------------------------------------------------

def create_user(name, email, password_hash):
    now = _now()
    cur = execute(
        "INSERT INTO users (name, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, email, password_hash, now, now),
    )
    return cur.lastrowid


def get_user(user_id):
    return query_one("SELECT * FROM users WHERE id = ?", (user_id,))


def find_user_by_email(email):
    return query_one("SELECT * FROM users WHERE email = ?", (email,))


def update_last_login(user_id):
    execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_now(), user_id))


# ----------------------------------------------------------------------------
# User settings
# ----------------------------------------------------------------------------

def get_user_settings(user_id):
    rows = query_all("SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,))
    out = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except (TypeError, ValueError):
            out[r["key"]] = r["value"]
    return out


def save_user_settings(user_id, settings):
    now = _now()
    for key, value in settings.items():
        execute(
            """INSERT INTO user_settings (user_id, key, value, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (user_id, key, json.dumps(value), now),
        )


# ----------------------------------------------------------------------------
# Conversations
# ----------------------------------------------------------------------------

def create_conversation(subject=""):
    uid = _uid()
    now = _now()
    cur = execute(
        "INSERT INTO conversations (user_id, subject, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (uid, subject, now, now),
    )
    return cur.lastrowid


def update_conversation(conv_id, title=None, subject=None, pinned=None):
    uid = _uid()
    sets = []
    params = []
    if title is not None:
        sets.append("title = ?")
        params.append(title)
    if subject is not None:
        sets.append("subject = ?")
        params.append(subject)
    if pinned is not None:
        sets.append("pinned = ?")
        params.append(int(pinned))
    if not sets:
        sets.append("updated_at = ?")
        params.append(_now())
    else:
        sets.append("updated_at = ?")
        params.append(_now())
    params.append(conv_id)
    params.append(uid)
    execute(f"UPDATE conversations SET {', '.join(sets)} WHERE id = ? AND user_id = ?", params)


def touch_conversation(conv_id):
    uid = _uid()
    execute("UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?", (_now(), conv_id, uid))


def delete_conversation(conv_id):
    uid = _uid()
    execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))


def duplicate_conversation(conv_id):
    uid = _uid()
    src = query_one("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))
    if not src:
        return None
    now = _now()
    cur = execute(
        "INSERT INTO conversations (user_id, title, subject, pinned, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (uid, src["title"] + " (copy)", src["subject"], 0, now, now),
    )
    new_id = cur.lastrowid
    for m in query_all("SELECT role, content FROM messages WHERE conversation_id = ? AND user_id = ? ORDER BY id", (conv_id, uid)):
        execute(
            "INSERT INTO messages (conversation_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id, uid, m["role"], m["content"], now),
        )
    for doc in query_all("SELECT * FROM note_documents WHERE conversation_id = ? AND user_id = ?", (conv_id, uid)):
        dcur = execute(
            "INSERT INTO note_documents (conversation_id, user_id, kind, title, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id, uid, doc["kind"], doc["title"], doc["version"], now, now),
        )
        new_doc = dcur.lastrowid
        for sec in query_all(
            "SELECT node_id, position, heading, kind, content, message_id FROM note_sections WHERE document_id = ? AND user_id = ? ORDER BY position",
            (doc["id"], uid),
        ):
            execute(
                "INSERT INTO note_sections (document_id, user_id, node_id, position, heading, kind, content, message_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (new_doc, uid, sec["node_id"], sec["position"], sec["heading"], sec["kind"], sec["content"], sec["message_id"], now, now),
            )
    return new_id


def list_conversations():
    uid = current_user_id()
    if not uid:
        return []
    return query_all(
        """
        SELECT c.*, COUNT(m.id) AS message_count,
               (SELECT COUNT(*) FROM note_sections s
                JOIN note_documents d ON s.document_id = d.id
                WHERE d.conversation_id = c.id AND d.user_id = c.user_id) AS section_count,
               (SELECT COUNT(*) FROM knowledge_nodes k
                WHERE k.conversation_id = c.id AND k.user_id = c.user_id) AS knowledge_count
        FROM conversations c
        LEFT JOIN messages m ON m.conversation_id = c.id AND m.user_id = c.user_id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.pinned DESC, c.updated_at DESC
        """,
        (uid,),
    )


def get_conversation(conv_id):
    uid = current_user_id()
    if not uid:
        return None
    return query_one("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))


# ----------------------------------------------------------------------------
# Messages
# ----------------------------------------------------------------------------

def add_message(conv_id, role, content):
    uid = _uid()
    owner = query_one("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))
    if not owner:
        raise PermissionError("Conversation belongs to another user.")
    cur = execute(
        "INSERT INTO messages (conversation_id, user_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, uid, role, content, _now()),
    )
    touch_conversation(conv_id)
    return cur.lastrowid


def get_messages(conv_id, limit=None):
    uid = current_user_id()
    if not uid:
        return []
    sql = "SELECT * FROM messages WHERE conversation_id = ? AND user_id = ? ORDER BY id"
    if limit:
        return query_all(sql + " LIMIT ?", (conv_id, uid, limit))
    return query_all(sql, (conv_id, uid))


# ----------------------------------------------------------------------------
# Memory
# ----------------------------------------------------------------------------

def set_memory(conv_id, kind, content):
    uid = _uid()
    row = query_one(
        "SELECT id FROM memories WHERE conversation_id = ? AND kind = ? AND user_id = ?",
        (conv_id, kind, uid),
    )
    if row:
        execute("UPDATE memories SET content = ?, updated_at = ? WHERE id = ?", (content, _now(), row["id"]))
    else:
        execute(
            "INSERT INTO memories (conversation_id, user_id, kind, content, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conv_id, uid, kind, content, _now()),
        )


def get_memory(conv_id, kind):
    uid = current_user_id()
    if not uid:
        return ""
    row = query_one(
        "SELECT content FROM memories WHERE conversation_id = ? AND kind = ? AND user_id = ?",
        (conv_id, kind, uid),
    )
    return row["content"] if row else ""


# ----------------------------------------------------------------------------
# Notes / documents / sections
# ----------------------------------------------------------------------------

def get_or_create_main_document(conv_id, title=""):
    uid = _uid()
    row = query_one(
        "SELECT * FROM note_documents WHERE conversation_id = ? AND kind = 'main' AND user_id = ? ORDER BY id DESC LIMIT 1",
        (conv_id, uid),
    )
    if row:
        return row
    owner = query_one("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))
    if not owner:
        raise PermissionError("Conversation belongs to another user.")
    now = _now()
    cur = execute(
        "INSERT INTO note_documents (conversation_id, user_id, kind, title, version, created_at, updated_at) VALUES (?, ?, 'main', ?, 1, ?, ?)",
        (conv_id, uid, title, now, now),
    )
    return query_one("SELECT * FROM note_documents WHERE id = ?", (cur.lastrowid,))


def create_document(conv_id, kind, title="", base_doc_id=None, copy_sections=True):
    uid = _uid()
    now = _now()
    version = 1
    if base_doc_id:
        row = query_one(
            "SELECT MAX(version) AS v FROM note_documents WHERE id = ? AND conversation_id = ? AND user_id = ?",
            (base_doc_id, conv_id, uid),
        )
        version = (row["v"] or 0) + 1
    cur = execute(
        "INSERT INTO note_documents (conversation_id, user_id, kind, title, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, uid, kind, title, version, now, now),
    )
    new_id = cur.lastrowid
    if base_doc_id and copy_sections:
        for sec in query_all(
            "SELECT node_id, position, heading, kind, content, message_id FROM note_sections WHERE document_id = ? AND user_id = ? ORDER BY position",
            (base_doc_id, uid),
        ):
            execute(
                "INSERT INTO note_sections (document_id, user_id, node_id, position, heading, kind, content, message_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (new_id, uid, sec["node_id"], sec["position"], sec["heading"], sec["kind"], sec["content"], sec["message_id"], now, now),
            )
    return new_id


def list_documents(conv_id):
    uid = current_user_id()
    if not uid:
        return []
    return query_all("SELECT * FROM note_documents WHERE conversation_id = ? AND user_id = ? ORDER BY id", (conv_id, uid))


def get_document(doc_id):
    uid = current_user_id()
    if not uid:
        return None
    return query_one("SELECT * FROM note_documents WHERE id = ? AND user_id = ?", (doc_id, uid))


def get_sections(doc_id):
    uid = current_user_id()
    if not uid:
        return []
    return query_all(
        """SELECT s.* FROM note_sections s
           JOIN note_documents d ON s.document_id = d.id
           WHERE s.document_id = ? AND s.user_id = ? AND d.user_id = ? ORDER BY s.position""",
        (doc_id, uid, uid),
    )


def get_section(section_id):
    uid = current_user_id()
    if not uid:
        return None
    return query_one("SELECT * FROM note_sections WHERE id = ? AND user_id = ?", (section_id, uid))


def upsert_section(doc_id, node_id, position, heading, kind, content, message_id=None):
    uid = _uid()
    now = _now()
    row = query_one(
        "SELECT id FROM note_sections WHERE document_id = ? AND node_id = ? AND user_id = ?",
        (doc_id, node_id, uid),
    )
    if row:
        execute(
            "UPDATE note_sections SET position = ?, heading = ?, kind = ?, content = ?, message_id = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (position, heading, kind, content, message_id, now, row["id"], uid),
        )
        return row["id"]
    cur = execute(
        "INSERT INTO note_sections (document_id, user_id, node_id, position, heading, kind, content, message_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, uid, node_id, position, heading, kind, content, message_id, now, now),
    )
    return cur.lastrowid


def update_section_content(section_id, content):
    uid = _uid()
    execute("UPDATE note_sections SET content = ?, updated_at = ? WHERE id = ? AND user_id = ?", (content, _now(), section_id, uid))


# ----------------------------------------------------------------------------
# Doubts
# ----------------------------------------------------------------------------

def add_doubt(conv_id, section_id, node_id, question, answer):
    uid = _uid()
    cur = execute(
        "INSERT INTO doubts (conversation_id, user_id, section_id, node_id, question, answer, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (conv_id, uid, section_id, node_id, question, answer, _now()),
    )
    return cur.lastrowid


def get_doubts(conv_id, section_id=None):
    uid = current_user_id()
    if not uid:
        return []
    if section_id is not None:
        return query_all(
            "SELECT * FROM doubts WHERE conversation_id = ? AND section_id = ? AND user_id = ? ORDER BY id",
            (conv_id, section_id, uid),
        )
    return query_all("SELECT * FROM doubts WHERE conversation_id = ? AND user_id = ? ORDER BY id", (conv_id, uid))


# ----------------------------------------------------------------------------
# Images
# ----------------------------------------------------------------------------

def add_image(conv_id, section_id, url, thumbnail="", source="", caption="", kind="web"):
    uid = _uid()
    cur = execute(
        "INSERT INTO images (conversation_id, user_id, section_id, url, thumbnail, source, caption, kind) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (conv_id, uid, section_id, url, thumbnail, source, caption, kind),
    )
    return cur.lastrowid


def get_images(conv_id, section_id=None):
    uid = current_user_id()
    if not uid:
        return []
    if section_id is not None:
        return query_all("SELECT * FROM images WHERE section_id = ? AND user_id = ? ORDER BY id", (section_id, uid))
    return query_all("SELECT * FROM images WHERE conversation_id = ? AND user_id = ? ORDER BY id", (conv_id, uid))


def delete_image(image_id):
    uid = _uid()
    execute("DELETE FROM images WHERE id = ? AND user_id = ?", (image_id, uid))


# ----------------------------------------------------------------------------
# Knowledge nodes
# ----------------------------------------------------------------------------

def create_knowledge_node(conv_id, title, summary="", content="", section_id=None,
                          message_id=None, parent_id=None, x=0.0, y=0.0):
    uid = _uid()
    owner = query_one("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conv_id, uid))
    if not owner:
        raise PermissionError("Conversation belongs to another user.")
    now = _now()
    cur = execute(
        """INSERT INTO knowledge_nodes
           (conversation_id, user_id, section_id, message_id, title, summary, content,
            x, y, collapsed, parent_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
        (conv_id, uid, section_id, message_id, title, summary, content, x, y, parent_id, now, now),
    )
    touch_conversation(conv_id)
    return cur.lastrowid


def get_knowledge_node(node_id):
    uid = current_user_id()
    if not uid:
        return None
    return query_one("SELECT * FROM knowledge_nodes WHERE id = ? AND user_id = ?", (node_id, uid))


def get_conversation_nodes(conv_id):
    uid = current_user_id()
    if not uid:
        return []
    return query_all(
        "SELECT * FROM knowledge_nodes WHERE conversation_id = ? AND user_id = ? ORDER BY id",
        (conv_id, uid),
    )


def update_knowledge_node(node_id, **kwargs):
    uid = _uid()
    allowed = {"title", "summary", "content", "x", "y", "collapsed", "parent_id",
               "section_id", "message_id"}
    sets = []
    params = []
    for key, value in kwargs.items():
        if key not in allowed:
            continue
        sets.append(f"{key} = ?")
        params.append(value)
    if not sets:
        return
    sets.append("updated_at = ?")
    params.append(_now())
    params.append(node_id)
    params.append(uid)
    execute(f"UPDATE knowledge_nodes SET {', '.join(sets)} WHERE id = ? AND user_id = ?", params)


def update_knowledge_node_position(node_id, x, y):
    update_knowledge_node(node_id, x=x, y=y)


def delete_knowledge_node(node_id):
    uid = _uid()
    execute("DELETE FROM knowledge_nodes WHERE id = ? AND user_id = ?", (node_id, uid))


def next_node_position(conv_id):
    """Auto-place the next knowledge card in a 4-wide grid (canvas coords)."""
    uid = current_user_id()
    if not uid:
        return (80.0, 60.0)
    count = query_one(
        "SELECT COUNT(*) AS n FROM knowledge_nodes WHERE conversation_id = ? AND user_id = ?",
        (conv_id, uid),
    )["n"]
    return (80 + (count % 4) * 220, 60 + (count // 4) * 150)


# ----------------------------------------------------------------------------
# Search
# ----------------------------------------------------------------------------

def search_conversation(conv_id, term):
    uid = current_user_id()
    if not uid:
        return {"messages": [], "sections": [], "doubts": []}
    like = f"%{term}%"
    messages = query_all(
        "SELECT id, role, content FROM messages WHERE conversation_id = ? AND user_id = ? AND content LIKE ? ORDER BY id DESC LIMIT 20",
        (conv_id, uid, like),
    )
    sections = query_all(
        """
        SELECT s.id, s.document_id, s.node_id, s.heading, s.content, s.message_id
        FROM note_sections s
        JOIN note_documents d ON s.document_id = d.id
        WHERE d.conversation_id = ? AND s.user_id = ? AND d.user_id = ?
          AND (s.heading LIKE ? OR s.content LIKE ?)
        ORDER BY s.id DESC LIMIT 20
        """,
        (conv_id, uid, uid, like, like),
    )
    doubts = query_all(
        """
        SELECT d.id, d.question, d.answer, d.node_id, s.heading AS section_heading
        FROM doubts d
        LEFT JOIN note_sections s ON d.section_id = s.id
        WHERE d.conversation_id = ? AND d.user_id = ? AND (d.question LIKE ? OR d.answer LIKE ?)
        ORDER BY d.id DESC LIMIT 20
        """,
        (conv_id, uid, like, like),
    )
    return {"messages": messages, "sections": sections, "doubts": doubts}


def search_user_contents(term):
    """Global search across all of the current user's conversations."""
    uid = current_user_id()
    if not uid:
        return []
    like = f"%{term}%"
    convs = query_all(
        """SELECT DISTINCT c.id, c.title, c.updated_at FROM conversations c
           WHERE c.user_id = ? AND (
             c.title LIKE ?
             OR EXISTS (SELECT 1 FROM messages m
                        WHERE m.conversation_id = c.id AND m.user_id = c.user_id
                          AND m.content LIKE ?)
             OR EXISTS (SELECT 1 FROM note_sections s JOIN note_documents d ON s.document_id = d.id
                        WHERE d.conversation_id = c.id AND d.user_id = c.user_id
                          AND (s.heading LIKE ? OR s.content LIKE ?))
             OR EXISTS (SELECT 1 FROM doubts d
                        WHERE d.conversation_id = c.id AND d.user_id = c.user_id
                          AND (d.question LIKE ? OR d.answer LIKE ?))
             OR EXISTS (SELECT 1 FROM knowledge_nodes k
                        WHERE k.conversation_id = c.id AND k.user_id = c.user_id
                          AND (k.title LIKE ? OR k.summary LIKE ? OR k.content LIKE ?))
           ) ORDER BY c.updated_at DESC LIMIT 8""",
        (uid, like, like, like, like, like, like, like, like, like),
    )
    out = []
    for c in convs:
        messages = query_all(
            "SELECT id, role, content FROM messages WHERE conversation_id = ? AND user_id = ? "
            "AND content LIKE ? ORDER BY id DESC LIMIT 3",
            (c["id"], uid, like),
        )
        sections = query_all(
            """SELECT s.id, s.node_id, s.heading, s.content
               FROM note_sections s JOIN note_documents d ON s.document_id = d.id
               WHERE d.conversation_id = ? AND s.user_id = ? AND d.user_id = ?
                 AND (s.heading LIKE ? OR s.content LIKE ?)
               ORDER BY s.id DESC LIMIT 3""",
            (c["id"], uid, uid, like, like),
        )
        doubts = query_all(
            "SELECT id, question, answer, node_id FROM doubts WHERE conversation_id = ? "
            "AND user_id = ? AND (question LIKE ? OR answer LIKE ?) ORDER BY id DESC LIMIT 3",
            (c["id"], uid, like, like),
        )
        nodes = query_all(
            "SELECT id, title, summary FROM knowledge_nodes WHERE conversation_id = ? "
            "AND user_id = ? AND (title LIKE ? OR summary LIKE ? OR content LIKE ?) "
            "ORDER BY id DESC LIMIT 3",
            (c["id"], uid, like, like, like),
        )
        out.append({"conversation": c, "messages": messages, "sections": sections,
                    "doubts": doubts, "nodes": nodes})
    return out


# ----------------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------------

def group_key(created_at):
    dt = datetime.fromisoformat(created_at)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if dt >= today:
        return "Today"
    if dt >= today - timedelta(days=1):
        return "Yesterday"
    if dt >= today - timedelta(days=7):
        return "Previous 7 Days"
    return "Older"