import pytest

import core.auth as auth
import core.db as db
from tests.conftest import make_user


class TestRegistration:
    def test_create_account(self):
        user = make_user(name="Sahil", email="sahil@example.com", password="correct horse")
        assert user["id"] is not None
        assert user["name"] == "Sahil"
        assert user["email"] == "sahil@example.com"
        assert db.find_user_by_email("sahil@example.com") is not None

    def test_duplicate_account(self):
        make_user(email="dup@example.com")
        with pytest.raises(ValueError, match="already exists"):
            auth.create_user("Bob", "dup@example.com", "whatever123")

    def test_register_error_duplicate(self):
        make_user(email="dup2@example.com")
        assert auth.register_error("Bob", "dup2@example.com", "password123", "password123") == (
            "An account with this email already exists."
        )

    def test_weak_password_rejected(self):
        with pytest.raises(ValueError, match="at least 8 characters"):
            auth.create_user("Bob", "bob@example.com", "short")

    def test_password_mismatch_rejected(self):
        assert auth.register_error("Bob", "bob@example.com", "password123", "different!") == (
            "Passwords do not match."
        )

    def test_missing_name_rejected(self):
        with pytest.raises(ValueError, match="Name is required."):
            auth.create_user(" ", "bob@example.com", "password123")


class TestPasswordStorage:
    def test_never_stores_plaintext(self):
        user = make_user(email="hash@example.com", password="super-secret-1")
        stored = db.get_user(user["id"])["password_hash"]
        assert stored != "super-secret-1"
        assert "super-secret-1" not in stored

    def test_hash_looks_like_a_hash(self):
        stored = db.get_user(make_user(email="h2@example.com")["id"])["password_hash"]
        assert stored.startswith("$argon2") or stored.startswith("pbkdf2$")

    def test_verify_password(self):
        stored = auth.hash_password("hunter2-secret")
        assert auth.verify_password(stored, "hunter2-secret") is True
        assert auth.verify_password(stored, "wrong") is False


class TestLogin:
    def test_login_success(self):
        make_user(email="login@example.com", password="mypassword1")
        user = auth.login("login@example.com", "mypassword1")
        assert user is not None and user["email"] == "login@example.com"

    def test_login_case_insensitive_email(self):
        make_user(email="case@example.com", password="mypassword1")
        user = auth.login("  CASE@Example.COM ", "mypassword1")
        assert user is not None

    def test_login_wrong_password(self):
        make_user(email="bad@example.com", password="mypassword1")
        assert auth.login("bad@example.com", "wrongpass1") is None

    def test_login_unknown_account_gives_same_null(self):
        assert auth.login("nobody@example.com", "anything123") is None

    def test_login_updates_last_login(self):
        user = make_user(email="last@example.com", password="mypassword1")
        assert db.get_user(user["id"])["last_login_at"] is None
        auth.login("last@example.com", "mypassword1")
        assert db.get_user(user["id"])["last_login_at"] is not None