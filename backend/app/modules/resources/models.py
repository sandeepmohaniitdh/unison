from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, UINT, enum
from app.db import Base


class Resource(Base):
    """Notes, slides and links of a course. Drafts until published."""

    __tablename__ = "resources"
    __table_args__ = (Index("ix_resources_course_id_status_published_at", "course_id", "status", "published_at"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    course_id: Mapped[int] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(enum("resource_kind", "file", "link"))
    storage_key: Mapped[str | None] = mapped_column(CHAR(32), unique=True)
    file_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(UINT)
    url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(enum("resource_status", "draft", "published"), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
