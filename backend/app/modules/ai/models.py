from datetime import datetime
from typing import Any

from sqlalchemy import CHAR, JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, UINT, enum
from app.db import Base


class AiFeedback(Base):
    """An AI feedback draft for one final. Rows in 'queued' are also the AI job queue."""

    __tablename__ = "ai_feedback"
    __table_args__ = (
        Index("ix_ai_feedback_cache_key_status", "cache_key", "status"),
        Index("ix_ai_feedback_final_id_created_at", "final_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    final_id: Mapped[int] = mapped_column(ID, ForeignKey("final_submissions.id", ondelete="RESTRICT"))
    file_id: Mapped[int] = mapped_column(ID, ForeignKey("submission_files.id", ondelete="RESTRICT"), index=True)
    requested_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    status: Mapped[str] = mapped_column(enum("ai_feedback_status", "queued", "running", "ready", "failed"))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(20))
    cache_key: Mapped[str] = mapped_column(CHAR(64))
    chars_read: Mapped[int | None] = mapped_column(UINT)
    chars_total: Mapped[int | None] = mapped_column(UINT)
    output: Mapped[Any] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
