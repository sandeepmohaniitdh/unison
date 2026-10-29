from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.time import IstDateTime
from app.modules.users.schemas import UserBrief


class CourseInvitationIn(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=200, examples=[["cs26mt024@iitdh.ac.in"]])
    role: Literal["student", "teacher"] = Field("student", description="'teacher' invites a co-teacher.")


class StaffInvitationIn(BaseModel):
    email: EmailStr
    role: Literal["teacher", "admin"]


class InvitationOut(BaseModel):
    id: int
    kind: Literal["course", "team", "staff"]
    email: str
    role: Literal["student", "teacher", "admin"]
    status: Literal["pending", "accepted", "declined", "cancelled", "expired"]
    course_id: int | None
    team_id: int | None
    invited_by: UserBrief
    expires_at: IstDateTime
    created_at: IstDateTime


class SkippedEmail(BaseModel):
    email: str
    reason: str = Field(examples=["already a member"])


class CourseInvitationResult(BaseModel):
    created: list[InvitationOut]
    skipped: list[SkippedEmail]


class CourseRef(BaseModel):
    id: int
    code: str
    title: str
    term: str


class TeamRef(BaseModel):
    id: int
    name: str
    assignment_id: int
    assignment_title: str
    due_at: IstDateTime
    members: list[str]


InvitationProblem = Literal["expired", "used", "cancelled", "declined", "log_in", "wrong_account", "email_not_verified"]


class InvitationView(BaseModel):
    """What the invitation page shows, including why it cannot be accepted."""

    id: int
    kind: Literal["course", "team", "staff"]
    role: Literal["student", "teacher", "admin"]
    status: str
    email: str
    invited_by: UserBrief
    course: CourseRef | None
    team: TeamRef | None
    expires_at: IstDateTime
    can_accept: bool
    problem: InvitationProblem | None = Field(None, description="Why it cannot be accepted right now.")


class InvitationResponseIn(BaseModel):
    status: Literal["accepted", "declined"]


class InvitationResponseOut(BaseModel):
    status: Literal["accepted", "declined"]
    kind: Literal["course", "team", "staff"]
    course_id: int | None
    team_id: int | None
    role: str
