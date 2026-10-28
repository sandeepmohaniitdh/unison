"""Passwords and random tokens.

Passwords are hashed with Argon2 through pwdlib (salted, never reversible).
Tokens (session cookies, invitation links, email links) are random strings;
the database keeps only their SHA-256 hash, so a database leak does not leak
working links or sessions.
"""

import hashlib
import secrets

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

MIN_PASSWORD_LENGTH = 8


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Still spend the time, so response times don't reveal Google-only accounts.
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_token() -> tuple[str, str]:
    """A new random token and its hash: (raw for the link or cookie, hash for the database)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


_DUMMY_HASH = _hasher.hash("not-a-real-password")
