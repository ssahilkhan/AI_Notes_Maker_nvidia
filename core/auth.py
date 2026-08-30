import base64
import hashlib
import hmac
import os

import core.db as db

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerificationError  # noqa: F401  (used implicitly)

    _HASHER = PasswordHasher()
    ARGON2_AVAILABLE = True
except Exception:
    _HASHER = None
    ARGON2_AVAILABLE = False

_PBKDF2_ITERATIONS = 600_000
_MIN_PASSWORD_LEN = 8


def normalize_email(email):
    return (email or "").strip().lower()


def hash_password(password):
    if _HASHER is not None:
        return _HASHER.hash(password)
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return "pbkdf2$sha256${0}${1}${2}".format(
        _PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def verify_password(stored, password):
    if not stored:
        return False
    if stored.startswith("$argon2"):
        if _HASHER is None:
            return False
        try:
            return _HASHER.verify(stored, password or "")
        except Exception:
            return False
    if stored.startswith("pbkdf2$"):
        try:
            _, alg, iters, salt_b64, hash_b64 = stored.split("$")
            dk = hashlib.pbkdf2_hmac(alg, (password or "").encode("utf-8"),
                                     base64.b64decode(salt_b64), int(iters))
            return hmac.compare_digest(dk, base64.b64decode(hash_b64))
        except Exception:
            return False
    return False


def register_error(name, email, password, confirm):
    """Return a clean user-facing error message, or None when the fields pass."""
    if not (name or "").strip():
        return "Name is required."
    if normalize_email(email) and db.find_user_by_email(normalize_email(email)):
        return "An account with this email already exists."
    if not (password or ""):
        return "Password must contain at least 8 characters."
    if len(password) < _MIN_PASSWORD_LEN:
        return "Password must contain at least 8 characters."
    if password != (confirm or ""):
        return "Passwords do not match."
    return None


def create_user(name, email, password):
    """Register a new account. Raises ValueError for validation problems."""
    normalized_email = normalize_email(email)
    if not (name or "").strip():
        raise ValueError("Name is required.")
    if not normalized_email:
        raise ValueError("Email / username is required.")
    if db.find_user_by_email(normalized_email):
        raise ValueError("An account with this email already exists.")
    if not password or len(password) < _MIN_PASSWORD_LEN:
        raise ValueError("Password must contain at least 8 characters.")
    user_id = db.create_user(name, normalized_email, hash_password(password))
    return db.get_user(user_id)


def login(email, password):
    """Authenticate a user. Returns the user row, or None on bad credentials."""
    user = db.find_user_by_email(normalize_email(email))
    if not user or not verify_password(user["password_hash"], password):
        return None
    db.update_last_login(user["id"])
    return user