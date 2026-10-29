from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP
from app.db import Base


class AuditLog(Base):
    """Every admin action and every role change. Rows are only ever added."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_audit_log_target_type_target_id", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    as_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int] = mapped_column(ID)
    course_id: Mapped[int | None] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    before_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class PlatformSetting(Base):
    """Key-value settings, for example the allowed email domain and the AI caps."""

    __tablename__ = "platform_settings"

    setting_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_by: Mapped[int | None] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
