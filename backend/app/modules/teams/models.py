from datetime import datetime

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, enum
from app.db import Base

MEMBER_STATUSES = ("active", "left", "removed", "former")


class Team(Base):
    """A team for one assignment. The creator is recorded but has no extra rights."""

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("assignment_id", "name"),
        # Target of the composite foreign key from team_members.
        UniqueConstraint("id", "assignment_id"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ID, ForeignKey("assignments.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)


class TeamMember(Base):
    """A student's place in one assignment: one row per student per assignment.

    The primary key (assignment_id, user_id) makes "one team per student per
    assignment" a database rule. The composite foreign key (team_id,
    assignment_id) to teams makes sure the team really belongs to that assignment.
    A student who changes team keeps the same row with a new team_id.
    """

    __tablename__ = "team_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["team_id", "assignment_id"],
            ["teams.id", "teams.assignment_id"],
            ondelete="RESTRICT",
        ),
        Index("ix_team_members_team_id_status", "team_id", "status"),
    )

    assignment_id: Mapped[int] = mapped_column(ID, primary_key=True)
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ID)
    status: Mapped[str] = mapped_column(enum("team_member_status", *MEMBER_STATUSES), default="active")
    joined_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
    left_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
