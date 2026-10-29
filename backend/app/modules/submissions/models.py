from datetime import datetime

from sqlalchemy import CHAR, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, SMALL_UINT, TIMESTAMP, UINT, enum
from app.db import Base


class Submission(Base):
    """The single submission record of a team (created with the team).

    current_final_id points to the final the teacher sees. closed_at is set
    when the deadline has been applied. There is no stored status: it is
    worked out from these two columns and the drafts.
    """

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    team_id: Mapped[int] = mapped_column(ID, ForeignKey("teams.id", ondelete="RESTRICT"), unique=True)
    # use_alter: submissions and final_submissions point at each other, so this
    # foreign key is added after both tables exist.
    current_final_id: Mapped[int | None] = mapped_column(
        ID,
        ForeignKey("final_submissions.id", ondelete="RESTRICT", use_alter=True),
        index=True,
    )
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class SubmissionVersion(Base):
    """A team draft (v1, v2, ...). Visible only to the team."""

    __tablename__ = "submission_versions"
    __table_args__ = (
        UniqueConstraint("submission_id", "number"),
        UniqueConstraint("uploaded_by", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ID, ForeignKey("submissions.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column(SMALL_UINT)
    uploaded_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(CHAR(36))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class FinalSubmission(Base):
    """Every time a draft became the final, including finals that were replaced later."""

    __tablename__ = "final_submissions"
    __table_args__ = (UniqueConstraint("submitted_by", "idempotency_key"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    version_id: Mapped[int] = mapped_column(ID, ForeignKey("submission_versions.id", ondelete="RESTRICT"), index=True)
    submitted_by: Mapped[int | None] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(enum("final_kind", "manual", "at_deadline"))
    below_min_size: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(CHAR(36))
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    replaced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)


class SubmissionFile(Base):
    """A file of a draft: PDF or ZIP. ZIPs are never extracted."""

    __tablename__ = "submission_files"
    __table_args__ = (Index("ix_submission_files_version_id", "version_id"),)

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    version_id: Mapped[int] = mapped_column(ID, ForeignKey("submission_versions.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(CHAR(32), unique=True)
    mime_type: Mapped[str] = mapped_column(enum("submission_file_mime", "application/pdf", "application/zip"))
    size_bytes: Mapped[int] = mapped_column(UINT)
    sha256: Mapped[str] = mapped_column(CHAR(64))
