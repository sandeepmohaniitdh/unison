from datetime import datetime

from sqlalchemy import CHAR, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.core.types import ID, TIMESTAMP, enum
from app.db import Base

INVITATION_STATUSES = ("pending", "accepted", "declined", "cancelled", "expired")


class Invitation(Base):
    """Course, team and staff invitations sent by email.

    The link carries a random token; only its hash is stored. A link works
    once, for 7 days, and only for an account with the invited address as a
    verified email.
    """

    __tablename__ = "invitations"
    __table_args__ = (
        Index("ix_invitations_team_id_status", "team_id", "status"),
        Index("ix_invitations_email_status", "email", "status"),
    )

    id: Mapped[int] = mapped_column(ID, primary_key=True)
    kind: Mapped[str] = mapped_column(enum("invitation_kind", "course", "team", "staff"))
    email: Mapped[str] = mapped_column(String(254))
    course_id: Mapped[int | None] = mapped_column(ID, ForeignKey("courses.id", ondelete="RESTRICT"), index=True)
    team_id: Mapped[int | None] = mapped_column(ID, ForeignKey("teams.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(enum("invitation_role", "student", "teacher", "admin"))
    invited_by: Mapped[int] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    status: Mapped[str] = mapped_column(enum("invitation_status", *INVITATION_STATUSES), default="pending")
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP)
    accepted_user_id: Mapped[int | None] = mapped_column(ID, ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    responded_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=utcnow)
