from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, enum
from app.db import Base


class Review(Base):
    """The teacher's review of one final. The total is computed, never stored."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    final_id: Mapped[int] = mapped_column(ID, ForeignKey("final_submissions.id", ondelete="RESTRICT"), unique=True)
    reviewer_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    overall_comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(enum("review_status", "draft", "released"), default="draft")
    released_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class ReviewScore(Base):
    __tablename__ = "review_scores"

    review_id: Mapped[int] = mapped_column(ID, ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True)
    criterion_id: Mapped[int] = mapped_column(
        ID, ForeignKey("rubric_criteria.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    points: Mapped[Decimal] = mapped_column(Numeric(5, 1))
    comment: Mapped[str | None] = mapped_column(Text)


class MemberAdjustment(Base):
    """A per-member change of the team mark, from -20% to +10%, with a reason."""

    __tablename__ = "member_adjustments"
    __table_args__ = (CheckConstraint("percent BETWEEN -20 AND 10", name="percent_range"),)

    review_id: Mapped[int] = mapped_column(ID, ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True)
    percent: Mapped[Decimal] = mapped_column(Numeric(4, 1))
    reason: Mapped[str] = mapped_column(Text)
    set_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    set_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
