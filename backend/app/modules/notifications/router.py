from fastapi import APIRouter, Response

from app.core.deps import DB, ClockDep, CurrentUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of
from app.core.permissions import require_teacher
from app.modules.notifications import dashboard, service
from app.modules.notifications.models import Notification
from app.modules.notifications.schemas import (
    MarkedRead,
    NotificationOut,
    NotificationUpdate,
    PreferenceOut,
    PreferencesIn,
    RuleOut,
    RulesIn,
    StudentDashboard,
    TeacherDashboard,
    UnreadCount,
)

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications",
    response_model=Page[NotificationOut],
    summary="List my notifications, newest first",
    responses=errors(401),
)
def list_notifications(db: DB, user: CurrentUser, page: Pagination, unread_only: bool = False):
    return service.list_notifications(db, user, page, unread_only)


@router.patch(
    "/notifications",
    response_model=MarkedRead,
    summary="Mark all my notifications as read",
    responses=errors(401),
)
def mark_all_notifications(body: NotificationUpdate, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"read": true}."""
    return {"marked": service.mark_all_read(db, user, clock)}


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCount,
    summary="Number for the bell",
    responses=errors(401),
)
def get_unread_count(db: DB, user: CurrentUser):
    """The frontend polls this every 30 seconds."""
    return {"unread": service.unread_count(db, user)}


@router.patch(
    "/notifications/{notification_id}",
    response_model=NotificationOut,
    summary="Mark one notification as read",
    responses=errors(401, 404),
)
def update_notification(notification_id: int, body: NotificationUpdate, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"read": true}."""
    service.mark_read(db, user, notification_id, clock)
    return service.notification_item(db.get(Notification, notification_id))


@router.get(
    "/users/me/notification-preferences",
    response_model=Page[PreferenceOut],
    summary="List my email switches",
    responses=errors(401),
)
def list_preferences(db: DB, user: CurrentUser, page: Pagination):
    """In-app notifications are always on. Verification, password reset and invitation emails always go."""
    return page_of(service.get_preferences(db, user), page)


@router.put(
    "/users/me/notification-preferences",
    status_code=204,
    summary="Turn email types on or off",
    responses=errors(400, 401),
)
def set_preferences(body: PreferencesIn, db: DB, user: CurrentUser):
    service.set_preferences(db, user, [i.model_dump() for i in body.items])
    return Response(status_code=204)


@router.get(
    "/courses/{course_id}/notification-rules",
    response_model=Page[RuleOut],
    summary="List the course's email rules",
    responses=errors(401, 403, 404),
)
def list_rules(course_id: int, db: DB, user: CurrentUser, page: Pagination):
    require_teacher(db, user, course_id, writable=False)
    return page_of(service.get_course_rules(db, course_id), page)


@router.put(
    "/courses/{course_id}/notification-rules",
    status_code=204,
    summary="Choose which events email members and teachers",
    responses=errors(400, 401, 403, 404, 409),
)
def set_rules(course_id: int, body: RulesIn, db: DB, user: CurrentUser):
    """Each user's own email switches still apply on top."""
    require_teacher(db, user, course_id)
    service.set_course_rules(db, course_id, [i.model_dump() for i in body.items])
    return Response(status_code=204)


@router.get(
    "/dashboards/student",
    response_model=StudentDashboard,
    summary="Get the student dashboard",
    responses=errors(401),
)
def get_student_dashboard(db: DB, clock: ClockDep, user: CurrentUser):
    return dashboard.student(db, user, clock)


@router.get(
    "/dashboards/teacher",
    response_model=TeacherDashboard,
    summary="Get the teacher dashboard",
    responses=errors(401, 403),
)
def get_teacher_dashboard(db: DB, clock: ClockDep, user: CurrentUser):
    return dashboard.teacher(db, user, clock)
