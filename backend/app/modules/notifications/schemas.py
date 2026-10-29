from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime
from app.modules.assignments.schemas import SubmissionState


class NotificationOut(BaseModel):
    id: int
    event_type: str = Field(examples=["final_submitted"])
    title: str
    link: str = Field(description="Frontend path to open, e.g. /teams/12")
    course_id: int | None
    read: bool
    created_at: IstDateTime


class NotificationUpdate(BaseModel):
    read: Literal[True] = Field(description="Only true: mark as read.")


class UnreadCount(BaseModel):
    unread: int


class MarkedRead(BaseModel):
    marked: int


class PreferenceOut(BaseModel):
    event_type: str
    label: str
    email_enabled: bool


class PreferenceIn(BaseModel):
    event_type: str
    email_enabled: bool


class PreferencesIn(BaseModel):
    items: list[PreferenceIn] = Field(min_length=1)


class RuleOut(BaseModel):
    event_type: str
    label: str
    email_members: bool
    email_teachers: bool


class RuleIn(BaseModel):
    event_type: str
    email_members: bool
    email_teachers: bool


class RulesIn(BaseModel):
    items: list[RuleIn] = Field(min_length=1)


# ---------------------------------------------------------------- dashboards


class DashCourse(BaseModel):
    id: int
    code: str
    title: str
    term: str


class Deadline(BaseModel):
    assignment_id: int
    title: str
    course: DashCourse
    kind: Literal["individual", "group"]
    due_at: IstDateTime
    team_id: int | None
    state: SubmissionState


class DashInvitation(BaseModel):
    id: int
    kind: Literal["course", "team", "staff"]
    text: str
    expires_at: IstDateTime


class ReleasedMark(BaseModel):
    assignment_id: int
    title: str
    team_id: int
    my_mark: Decimal
    max_mark: Decimal
    released_at: IstDateTime


class StudentDashboard(BaseModel):
    unread_notifications: int
    notifications: list[NotificationOut]
    courses: list[DashCourse]
    upcoming_deadlines: list[Deadline]
    pending_invitations: list[DashInvitation]
    released_marks: list[ReleasedMark]


class TeacherCourse(DashCourse):
    students: int
    pending_join_requests: int


class TeacherAssignment(BaseModel):
    id: int
    title: str
    course: DashCourse
    due_at: IstDateTime
    status: Literal["draft", "published", "closed"]
    teams: int
    with_final: int
    without_final: int
    reviewed: int
    released: int


class TeacherDashboard(BaseModel):
    unread_notifications: int
    notifications: list[NotificationOut]
    courses: list[TeacherCourse]
    assignments: list[TeacherAssignment]
