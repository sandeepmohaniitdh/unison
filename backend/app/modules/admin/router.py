from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import DB, AdminUser, ClockDep
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of, paginate
from app.core.time import IstDateTimeIn
from app.modules.admin import service
from app.modules.admin.schemas import AuditEntry, SettingIn, SettingOut, Stats, UserDetail, UserRow, UserUpdate
from app.modules.courses import service as courses
from app.modules.courses.models import Course
from app.modules.courses.schemas import CourseSummary

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=Stats, summary="Get platform statistics", responses=errors(401, 403))
def get_stats(db: DB, _admin: AdminUser):
    return service.stats(db)


@router.get("/users", response_model=Page[UserRow], summary="Search users", responses=errors(401, 403))
def list_users(
    db: DB,
    _admin: AdminUser,
    page: Pagination,
    q: Annotated[str | None, Query(max_length=100, description="Name or email.")] = None,
    role: Literal["student", "teacher", "admin"] | None = None,
    status: Literal["active", "suspended", "deactivated", "deleted"] | None = None,
):
    return service.list_users(db, page, q=q, role=role, status=status)


@router.get(
    "/users/{user_id}",
    response_model=UserDetail,
    summary="Get one user with emails and courses",
    responses=errors(401, 403, 404),
)
def get_user(user_id: int, db: DB, _admin: AdminUser):
    return service.user_detail(db, user_id)


@router.patch(
    "/users/{user_id}",
    response_model=UserRow,
    summary="Change a user's role, or suspend or restore the account",
    responses=errors(401, 403, 404, 409),
)
def update_user(user_id: int, body: UserUpdate, db: DB, clock: ClockDep, admin: AdminUser):
    """{"role": "teacher"} changes the role; {"status": "suspended"} suspends (and logs the user out
    everywhere); {"status": "active"} restores. Every change is written to the audit log.
    A user promoted after joining courses as a student stays a student in those courses."""
    row = None
    if body.role is not None:
        row = service.change_role(db, admin, user_id, body.role)
    if body.status is not None:
        row = service.set_suspended(db, admin, user_id, body.status == "suspended", clock)
    return row or service.user_row(db, service.get_user(db, user_id))


@router.get(
    "/courses",
    response_model=Page[CourseSummary],
    summary="List all courses, or those without an active teacher",
    responses=errors(401, 403),
)
def list_courses(db: DB, admin: AdminUser, page: Pagination, without_teacher: bool = False):
    """Includes archived courses. without_teacher=true lists open courses whose teachers
    have all left or deleted their account."""
    if without_teacher:
        rows = [db.get(Course, i) for i in service.courses_without_teacher(db)]
        return page_of(courses.summaries(db, rows, admin), page)
    stmt = select(Course).order_by(Course.code, Course.term)
    result = paginate(db, stmt, page)
    result["items"] = courses.summaries(db, result["items"], admin)
    return result


@router.get(
    "/audit-entries",
    response_model=Page[AuditEntry],
    summary="List the audit log, newest first",
    responses=errors(401, 403),
)
def list_audit_entries(
    db: DB,
    _admin: AdminUser,
    page: Pagination,
    actor_id: int | None = None,
    action: Annotated[str | None, Query(max_length=60, examples=["role_changed"])] = None,
    target_type: Annotated[str | None, Query(max_length=40)] = None,
    course_id: int | None = None,
    since: IstDateTimeIn | None = None,
    until: IstDateTimeIn | None = None,
):
    return service.list_audit_log(
        db,
        page,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        course_id=course_id,
        since=since,
        until=until,
    )


@router.get("/settings", response_model=Page[SettingOut], summary="List platform settings", responses=errors(401, 403))
def list_settings(db: DB, _admin: AdminUser, page: Pagination):
    return page_of(service.list_settings(db), page)


@router.put(
    "/settings/{key}",
    response_model=SettingOut,
    summary="Change a platform setting",
    responses=errors(400, 401, 403, 404),
)
def update_setting(key: str, body: SettingIn, db: DB, clock: ClockDep, admin: AdminUser):
    return service.update_setting(db, admin, key, body.value, clock)
