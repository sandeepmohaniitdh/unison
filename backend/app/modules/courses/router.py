from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response

from app.core.deps import DB, AdminUser, ClockDep, CurrentUser, OptionalUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of
from app.modules.courses import service
from app.modules.courses.schemas import (
    CourseDetail,
    CourseIn,
    CourseSummary,
    CourseUpdate,
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    EnrollmentOut,
    JoinRequestDecision,
    JoinRequestOut,
    MemberOut,
    MemberUpdate,
    TeacherAdd,
)

router = APIRouter(tags=["courses"])


# ---------------------------------------------------------------- departments


@router.get("/departments", response_model=Page[DepartmentOut], summary="List departments (public)")
def list_departments(db: DB, page: Pagination):
    return page_of(service.list_departments(db), page)


@router.post(
    "/departments",
    response_model=DepartmentOut,
    status_code=201,
    summary="Create a department (admins)",
    responses=errors(401, 403, 409),
)
def create_department(body: DepartmentIn, db: DB, admin: AdminUser):
    return service.create_department(db, admin, body.code, body.name)


@router.patch(
    "/departments/{department_id}",
    response_model=DepartmentOut,
    summary="Rename a department (admins)",
    responses=errors(401, 403, 404, 409),
)
def update_department(department_id: int, body: DepartmentUpdate, db: DB, admin: AdminUser):
    return service.update_department(db, admin, department_id, body.code, body.name)


# ---------------------------------------------------------------- courses


@router.get("/courses", response_model=Page[CourseSummary], summary="Course catalogue (public)")
def list_courses(
    db: DB,
    user: OptionalUser,
    page: Pagination,
    q: Annotated[str | None, Query(max_length=100, description="Search code, title or teacher name.")] = None,
    department_id: Annotated[int | None, Query()] = None,
    term: Annotated[str | None, Query(max_length=20, examples=["Jul-Nov 2026"])] = None,
    include_archived: bool = False,
):
    """Ordered by course code. Logged-in users also see their own status in each course."""
    return service.catalogue(
        db, user, page, q=q, department_id=department_id, term=term, include_archived=include_archived
    )


@router.post(
    "/courses",
    response_model=CourseDetail,
    status_code=201,
    summary="Create a course",
    responses=errors(400, 401, 403, 409),
)
def create_course(body: CourseIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Teachers and admins. A teacher who creates a course teaches it; admins assign teachers."""
    return service.create_course(db, user, body.model_dump(), clock)


@router.get(
    "/users/me/courses",
    response_model=Page[CourseSummary],
    summary="My courses (taught or enrolled)",
    responses=errors(401),
)
def list_my_courses(db: DB, user: CurrentUser, page: Pagination):
    return page_of(service.my_courses(db, user), page)


@router.get(
    "/courses/{course_id}", response_model=CourseDetail, summary="Get one course (public)", responses=errors(404)
)
def get_course(course_id: int, db: DB, user: OptionalUser):
    return service.course_detail(db, user, course_id)


@router.patch(
    "/courses/{course_id}",
    response_model=CourseDetail,
    summary="Edit or archive a course",
    responses=errors(400, 401, 403, 404, 409),
)
def update_course(course_id: int, body: CourseUpdate, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"archived": true} to archive the course at the end of term; it becomes read-only."""
    return service.update_course(db, user, course_id, body.model_dump(exclude_unset=True), clock)


# ---------------------------------------------------------------- members


@router.get(
    "/courses/{course_id}/members",
    response_model=Page[MemberOut],
    summary="List course members",
    responses=errors(401, 403, 404),
)
def list_members(
    course_id: int,
    db: DB,
    user: CurrentUser,
    page: Pagination,
    role: Literal["student", "teacher"] | None = None,
    status: Literal["active", "removed", "left", "rejected"] | None = None,
):
    return service.list_members(db, user, course_id, page, role, status)


@router.post(
    "/courses/{course_id}/teachers",
    response_model=MemberOut,
    status_code=201,
    summary="Assign a teacher (admins)",
    responses=errors(400, 401, 403, 404),
)
def add_teacher(course_id: int, body: TeacherAdd, db: DB, clock: ClockDep, admin: AdminUser):
    return service.add_teacher(db, admin, course_id, body.user_id, clock)


@router.delete(
    "/courses/{course_id}/members/{user_id}",
    status_code=204,
    summary="Remove a member",
    responses=errors(401, 403, 404, 409),
)
def remove_member(course_id: int, user_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Students are removed by teachers or admins, teachers only by admins.
    Access ends at once and their pending invitations in the course are cancelled.
    Before their team's first final they leave the team; after it they show as Removed."""
    service.remove_member(db, user, course_id, user_id, clock)
    return Response(status_code=204)


@router.patch(
    "/courses/{course_id}/members/{user_id}",
    response_model=MemberOut,
    summary="Re-enrol a removed student",
    responses=errors(401, 403, 404, 409),
)
def update_member(course_id: int, user_id: int, body: MemberUpdate, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"status": "active"} before the course is archived; access returns as it was."""
    return service.reinstate_member(db, user, course_id, user_id, clock)


# ---------------------------------------------------------------- join requests


@router.post(
    "/courses/{course_id}/join-requests",
    response_model=EnrollmentOut,
    status_code=201,
    summary="Ask to join a course",
    responses=errors(401, 403, 404, 409, 429),
)
def create_join_request(course_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Students only, at most 10 a day. The course's teachers are notified."""
    return service.request_join(db, user, course_id, clock)


@router.delete(
    "/courses/{course_id}/join-requests/mine",
    status_code=204,
    summary="Cancel my join request",
    responses=errors(401, 404),
)
def delete_my_join_request(course_id: int, db: DB, user: CurrentUser):
    service.cancel_join_request(db, user, course_id)
    return Response(status_code=204)


@router.get(
    "/courses/{course_id}/join-requests",
    response_model=Page[JoinRequestOut],
    summary="List pending join requests",
    responses=errors(401, 403, 404),
)
def list_join_requests(course_id: int, db: DB, user: CurrentUser, page: Pagination):
    return service.list_join_requests(db, user, course_id, page)


@router.patch(
    "/courses/{course_id}/join-requests/{request_id}",
    response_model=EnrollmentOut,
    summary="Approve or reject a join request",
    responses=errors(401, 403, 404, 409),
)
def decide_join_request(
    course_id: int, request_id: int, body: JoinRequestDecision, db: DB, clock: ClockDep, user: CurrentUser
):
    """Send {"status": "approved"} or {"status": "rejected"}. The student is notified either way."""
    return service.decide_join_request(db, user, course_id, request_id, body.status == "approved", clock)
