from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.types import ID, TIMESTAMP, TINY_UINT, enum
from app.db import Base


class Assignment(Base):
    """An individual or group assignment. An individual assignment is a team of one.

    due_at is UTC; the API shows it in IST.
    """

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("max_team >= min_team", name="team_size"),
        CheckConstraint("min_team >= 1", name="min_team_positive"),
        Index("ix_assignments_course_id_status_due_at", "course_id", "status", "due_at"),
        Index("ix_assignments_status_due_at", "status", "due_at"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    course_id: Mapped[int] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(enum("assignment_kind", "individual", "group"))
    min_team: Mapped[int] = mapped_column(TINY_UINT, default=1)
    max_team: Mapped[int] = mapped_column(TINY_UINT, default=1)
    max_files: Mapped[int] = mapped_column(TINY_UINT, default=5)
    requires_pdf: Mapped[bool] = mapped_column(Boolean, default=False)
    due_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    status: Mapped[str] = mapped_column(enum("assignment_status", "draft", "published", "closed"), default="draft")
    teams_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"
    __table_args__ = (
        UniqueConstraint("assignment_id", "position"),
        CheckConstraint("max_points > 0", name="max_points_positive"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ID, ForeignKey("assignments.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(TINY_UINT)
    title: Mapped[str] = mapped_column(String(160))
    max_points: Mapped[Decimal] = mapped_column(Numeric(5, 1))
