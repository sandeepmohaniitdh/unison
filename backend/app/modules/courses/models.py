from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, enum
from app.db import Base

ENROLLMENT_STATUSES = ("requested", "active", "rejected", "removed", "left")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)


class Course(Base):
    """A course offering in one term. Archived courses are read-only."""

    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("code", "term"),
        Index("ix_courses_code_title_fulltext", "code", "title", mysql_prefix="FULLTEXT"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    department_id: Mapped[int] = mapped_column(ID, ForeignKey("departments.id", ondelete="RESTRICT"), index=True)
    code: Mapped[str] = mapped_column(String(12))
    term: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    join_requests_open: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class Enrollment(Base):
    """Course membership, teachers included. A join request is a row in 'requested'."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id"),
        Index("ix_enrollments_user_id_status", "user_id", "status"),
        Index("ix_enrollments_course_id_status", "course_id", "status"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    course_id: Mapped[int] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"))
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(enum("enrollment_role", "student", "teacher"))
    status: Mapped[str] = mapped_column(enum("enrollment_status", *ENROLLMENT_STATUSES))
    requested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    decided_by: Mapped[int | None] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
