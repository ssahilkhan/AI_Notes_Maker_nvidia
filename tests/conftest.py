import os
import tempfile

import pytest

# Must point core.db at a throwaway database BEFORE importing it.
os.environ["STUDY_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="study_test_"), "test.db")

import core.auth as auth  # noqa: E402
import core.db as db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    db.reset()
    db.set_current_user(None)
    path = db._db_path()
    if path.exists():
        path.unlink()
    yield
    db.reset()
    db.set_current_user(None)
    path = db._db_path()
    if path.exists():
        path.unlink()


def make_user(name="Alice", email="alice@example.com", password="password123"):
    return auth.create_user(name, email, password)