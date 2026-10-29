from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime
from app.modules.users.schemas import UserBrief


class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=10, examples=["CSE"])
    name: str = Field(min_length=2, max_length=120, examples=["Computer Science and Engineering"])


class DepartmentUpdate(BaseModel):
    code: str | None = Field(None, min_length=2, max_length=10)
    name: str | None = Field(None, min_length=2, max_length=120)


class DepartmentOut(BaseModel):
    id: int
    code: str
    name: str


class CourseIn(BaseModel):
    department_id: int
    code: str = Field(min_length=2, max_length=12, examples=["CS301"])
    term: str = Field(min_length=2, max_length=20, examples=["Jul-Nov 2026"])
    title: str = Field(min_length=2, max_length=160, examples=["Software Engineering"])
    description: str | None = Field(None, max_length=5000)
    join_requests_open: bool = True
    teacher_ids: list[int] = Field(
        default_factory=list,
        description="Admins: teachers to assign. A teacher who creates a course always teaches it.",
    )


class CourseUpdate(BaseModel):
    """Only the fields sent are changed."""

    department_id: int | None = None
    title: str | None = Field(None, min_length=2, max_length=160)
    term: str | None = Field(None, min_length=2, max_length=20)
    description: str | None = Field(None, max_length=5000)
    join_requests_open: bool | None = None
    archived: bool | None = Field(None, description="true archives the course (read-only from then on).")


MyStatus = Literal["teacher", "student", "requested", "rejected", "removed", "left", "none"]


class CourseSummary(BaseModel):
    id: int
    code: str
    term: str
    title: str
    department: DepartmentOut
    teachers: list[UserBrief]
    join_requests_open: bool
    archived: bool
    my_status: MyStatus = Field(description="'none' when not logged in or not a member.")


class AssignmentTitle(BaseModel):
    id: int
    title: str
    kind: Literal["individual", "group"]
    due_at: IstDateTime


class CourseDetail(CourseSummary):
    description: str | None
    student_count: int
    assignments: list[AssignmentTitle] = Field(description="Published assignment titles (public).")
    created_at: IstDateTime


class MemberOut(BaseModel):
    user: UserBrief
    email: str | None
    role: Literal["student", "teacher"]
    status: str
    joined_at: IstDateTime | None


class MemberUpdate(BaseModel):
    status: Literal["active"] = Field(description="Only 'active' (re-enrol a removed student).")


class JoinRequestDecision(BaseModel):
    status: Literal["approved", "rejected"]


class TeacherAdd(BaseModel):
    user_id: int = Field(description="A user whose global role is teacher or admin.")


class JoinRequestOut(BaseModel):
    id: int
    user: UserBrief
    email: str | None
    requested_at: IstDateTime | None
    status: str


class EnrollmentOut(BaseModel):
    course_id: int
    status: str
    role: str
