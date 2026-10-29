from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, TINY_UINT, enum
from app.db import Base


class Notification(Base):
    """An in-app notification. These are always on."""

    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_id_read_at_created_at", "user_id", "read_at", "created_at"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    course_id: Mapped[int | None] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    link: Mapped[str] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class NotificationPreference(Base):
    """A user's email switch for one event type. No row means email is on."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class NotificationRule(Base):
    """A course's email rule for one event type. No row means the default rule."""

    __tablename__ = "notification_rules"

    course_id: Mapped[int] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    email_members: Mapped[bool] = mapped_column(Boolean, default=True)
    email_teachers: Mapped[bool] = mapped_column(Boolean, default=True)


class EmailOutbox(Base):
    """Emails waiting to be sent. Rows are written in the same transaction as the
    change they describe; the worker sends them and retries after 1, 5, 15 and 60 minutes."""

    __tablename__ = "email_outbox"
    __table_args__ = (Index("ix_email_outbox_status_send_after", "status", "send_after"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    to_email: Mapped[str] = mapped_column(String(254))
    template: Mapped[str] = mapped_column(String(50))
    payload: Mapped[Any] = mapped_column(JSON)
    dedup_key: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(
        enum("email_outbox_status", "pending", "sending", "sent", "failed"), default="pending"
    )
    attempts: Mapped[int] = mapped_column(TINY_UINT, default=0)
    send_after: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    last_error: Mapped[str | None] = mapped_column(String(300))
