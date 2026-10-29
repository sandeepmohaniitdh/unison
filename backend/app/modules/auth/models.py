from datetime import datetime

from sqlalchemy import CHAR, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, IP_ADDRESS, TIMESTAMP, enum
from app.db import Base


class OAuthIdentity(Base):
    """A Google account linked to a user."""

    __tablename__ = "oauth_identities"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(enum("oauth_provider", "google"))
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class UserSession(Base):
    """A login. The browser holds the random token; only its SHA-256 is stored."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    last_seen_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class LoginAttempt(Base):
    """Login and sign-up attempts, used for rate limits. No foreign key on purpose:
    the typed email may not belong to anyone."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_email_ip_created_at", "email", "ip", "created_at"),
        Index("ix_login_attempts_ip_created_at", "ip", "created_at"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    kind: Mapped[str] = mapped_column(enum("login_attempt_kind", "login", "signup"))
    email: Mapped[str | None] = mapped_column(String(254))
    ip: Mapped[bytes] = mapped_column(IP_ADDRESS)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class EmailToken(Base):
    """Single-use links for email verification and password reset."""

    __tablename__ = "email_tokens"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    user_email_id: Mapped[int | None] = mapped_column(ID, ForeignKey("user_emails.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(enum("email_token_purpose", "verify_email", "reset_password"))
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
