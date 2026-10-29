from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime
from app.modules.users.schemas import UserBrief


class UserRow(BaseModel):
    id: int
    name: str
    email: str | None
    role: Literal["student", "teacher", "admin"]
    status: Literal["active", "suspended", "deactivated", "deleted"]
    created_at: IstDateTime
    deletion_requested_at: IstDateTime | None


class AdminEmail(BaseModel):
    id: int
    email: str
    is_primary: bool
    verified: bool


class AdminEnrolment(BaseModel):
    course_id: int
    code: str
    title: str
    term: str
    role: str
    status: str


class UserDetail(UserRow):
    emails: list[AdminEmail]
    enrolments: list[AdminEnrolment]


class UserUpdate(BaseModel):
    """Send role, status or both."""

    role: Literal["student", "teacher", "admin"] | None = None
    status: Literal["active", "suspended"] | None = Field(None, description="'suspended' suspends, 'active' restores.")


class UserCounts(BaseModel):
    students: int
    teachers: int
    admins: int
    suspended: int
    pending_deletion: int


class Stats(BaseModel):
    users: UserCounts
    departments: int
    courses: int
    active_courses: int
    courses_without_teacher: int
    assignments: int
    teams: int
    drafts: int
    finals: int


class AuditEntry(BaseModel):
    id: int
    actor: UserBrief
    as_admin: bool = Field(description="An administrator acting with teacher powers in a course.")
    action: str = Field(examples=["role_changed"])
    target_type: str
    target_id: int
    course_id: int | None
    before: Any
    after: Any
    created_at: IstDateTime


class SettingOut(BaseModel):
    key: str
    value: Any
    default: Any
    description: str
    updated_at: IstDateTime | None


class SettingIn(BaseModel):
    value: Any = Field(examples=[5])
