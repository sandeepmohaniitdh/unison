"""Admin console: audit log, platform settings, users and roles, statistics."""

from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found
from app.core.pagination import PageParams, paginate
from app.core.time import Clock
from app.modules.admin.models import AuditLog, PlatformSetting
from app.modules.users.models import User, UserEmail

# Setting key -> (default value, type, description). Admins can change these.
SETTINGS: dict[str, tuple[Any, type, str]] = {
    "allowed_email_domain": ("iitdh.ac.in", str, "Sign-up is open only to emails at this domain."),
    "signups_per_ip_per_hour": (5, int, "Sign-ups allowed from one IP address per hour."),
    "join_requests_per_day": (10, int, "Join requests one student can make per day."),
    "ai_requests_per_submission": (3, int, "AI drafts per final: the first and the regenerations."),
    "ai_daily_cap_per_final": (3, int, "AI drafts per course per day, per submitted final in the course."),
}


# ---------------------------------------------------------------- audit log


def audit(
    db: Session,
    actor: User,
    action: str,
    target_type: str,
    target_id: int,
    *,
    course_id: int | None = None,
    as_admin: bool = False,
    before: Any = None,
    after: Any = None,
) -> None:
    """Add an audit row in the same transaction as the change it records."""
    db.add(
        AuditLog(
            actor_id=actor.id,
            as_admin=as_admin,
            action=action,
            target_type=target_type,
            target_id=target_id,
            course_id=course_id,
            before_value=before,
            after_value=after,
        )
    )


def list_audit_log(
    db: Session,
    params: PageParams,
    *,
    actor_id: int | None,
    action: str | None,
    target_type: str | None,
    course_id: int | None,
    since: datetime | None,
    until: datetime | None,
) -> dict:
    stmt = select(AuditLog, User.name).join(User, User.id == AuditLog.actor_id)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if course_id:
        stmt = stmt.where(AuditLog.course_id == course_id)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at < until)
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())

    def item(row):
        log, actor_name = row
        return {
            "id": log.id,
            "actor": {"id": log.actor_id, "name": actor_name},
            "as_admin": log.as_admin,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "course_id": log.course_id,
            "before": log.before_value,
            "after": log.after_value,
            "created_at": log.created_at,
        }

    return paginate(db, stmt, params, item)


# ---------------------------------------------------------------- settings


def get_setting(db: Session, key: str) -> Any:
    row = db.get(PlatformSetting, key)
    return row.value if row is not None else SETTINGS[key][0]


def list_settings(db: Session) -> list[dict]:
    stored = {row.setting_key: row for row in db.scalars(select(PlatformSetting))}
    out = []
    for key, (default, _type, description) in SETTINGS.items():
        row = stored.get(key)
        out.append(
            {
                "key": key,
                "value": row.value if row else default,
                "default": default,
                "description": description,
                "updated_at": row.updated_at if row else None,
            }
        )
    return out


def ensure_default_settings(db: Session) -> None:
    for key, (default, _type, _description) in SETTINGS.items():
        if db.get(PlatformSetting, key) is None:
            db.add(PlatformSetting(setting_key=key, value=default))


def update_setting(db: Session, admin: User, key: str, value: Any, clock: Clock) -> dict:
    if key not in SETTINGS:
        raise not_found("Setting")
    default, kind, _description = SETTINGS[key]
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise bad_request("INVALID_SETTING", f"{key} must be a whole number of 0 or more.")
    elif kind is str:
        if not isinstance(value, str) or not value.strip():
            raise bad_request("INVALID_SETTING", f"{key} must be a non-empty text.")
        value = value.strip().lower().lstrip("@")
    row = db.get(PlatformSetting, key)
    before = row.value if row else default
    if row is None:
        row = PlatformSetting(setting_key=key, value=value)
        db.add(row)
    row.value = value
    row.updated_by = admin.id
    row.updated_at = clock.now()
    audit(db, admin, "setting_changed", "platform_settings", 0, before={key: before}, after={key: value})
    db.commit()
    return next(s for s in list_settings(db) if s["key"] == key)


# ---------------------------------------------------------------- users and roles


def _primary_emails(db: Session, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(
        select(UserEmail.user_id, UserEmail.email).where(UserEmail.user_id.in_(user_ids), UserEmail.is_primary)
    )
    return dict(rows.all())


def user_row(db: Session, user: User, email: str | None = None) -> dict:
    if email is None:
        email = _primary_emails(db, [user.id]).get(user.id)
    return {
        "id": user.id,
        "name": user.name,
        "email": email,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "deletion_requested_at": user.deletion_requested_at,
    }


def list_users(db: Session, params: PageParams, *, q: str | None, role: str | None, status: str | None) -> dict:
    stmt = select(User)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                User.name.ilike(like),
                User.id.in_(select(UserEmail.user_id).where(UserEmail.email.ilike(like))),
            )
        )
    if role:
        stmt = stmt.where(User.role == role)
    if status:
        stmt = stmt.where(User.status == status)
    stmt = stmt.order_by(User.name, User.id)
    page = paginate(db, stmt, params)
    emails = _primary_emails(db, [u.id for u in page["items"]])
    page["items"] = [user_row(db, u, emails.get(u.id)) for u in page["items"]]
    return page


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    return user


def _admin_count(db: Session) -> int:
    return db.scalar(select(func.count()).where(User.role == "admin", User.status == "active")) or 0


def change_role(db: Session, admin: User, user_id: int, role: str) -> dict:
    user = get_user(db, user_id)
    if user.status == "deleted":
        raise conflict("USER_DELETED", "This account has been deleted.")
    if user.role == role:
        return user_row(db, user)
    if user.role == "admin" and role != "admin" and _admin_count(db) <= 1:
        raise conflict("LAST_ADMIN", "The last administrator cannot lose the admin role.")
    before = user.role
    user.role = role
    audit(db, admin, "role_changed", "users", user.id, before={"role": before}, after={"role": role})
    db.commit()
    return user_row(db, user)


def set_suspended(db: Session, admin: User, user_id: int, suspended: bool, clock: Clock) -> dict:
    from app.modules.auth.service import revoke_all_sessions

    user = get_user(db, user_id)
    if user.id == admin.id:
        raise conflict("CANNOT_SUSPEND_SELF", "You cannot suspend your own account.")
    if suspended:
        if user.status != "active":
            raise conflict("USER_NOT_ACTIVE", "Only active accounts can be suspended.")
        if user.role == "admin" and _admin_count(db) <= 1:
            raise conflict("LAST_ADMIN", "The last administrator cannot be suspended.")
        user.status = "suspended"
        revoke_all_sessions(db, user.id, clock.now())
        audit(db, admin, "user_suspended", "users", user.id, before={"status": "active"}, after={"status": "suspended"})
    else:
        if user.status != "suspended":
            raise conflict("USER_NOT_SUSPENDED", "This account is not suspended.")
        user.status = "active"
        audit(db, admin, "user_restored", "users", user.id, before={"status": "suspended"}, after={"status": "active"})
    db.commit()
    return user_row(db, user)


def user_detail(db: Session, user_id: int) -> dict:
    from app.modules.courses.models import Course, Enrollment

    user = get_user(db, user_id)
    emails = db.scalars(select(UserEmail).where(UserEmail.user_id == user.id).order_by(UserEmail.id)).all()
    enrolments = db.execute(
        select(Enrollment, Course)
        .join(Course, Course.id == Enrollment.course_id)
        .where(Enrollment.user_id == user.id)
        .order_by(Course.code)
    ).all()
    row = user_row(db, user)
    row["emails"] = [
        {"id": e.id, "email": e.email, "is_primary": e.is_primary, "verified": e.verified_at is not None}
        for e in emails
    ]
    row["enrolments"] = [
        {"course_id": c.id, "code": c.code, "title": c.title, "term": c.term, "role": e.role, "status": e.status}
        for e, c in enrolments
    ]
    return row


# ---------------------------------------------------------------- statistics


def stats(db: Session) -> dict:
    from app.modules.assignments.models import Assignment
    from app.modules.courses.models import Course, Department
    from app.modules.submissions.models import FinalSubmission, SubmissionVersion
    from app.modules.teams.models import Team

    def count(stmt) -> int:
        return db.scalar(stmt) or 0

    users_by_role = dict(
        db.execute(select(User.role, func.count()).where(User.status != "deleted").group_by(User.role)).all()
    )
    return {
        "users": {
            "students": users_by_role.get("student", 0),
            "teachers": users_by_role.get("teacher", 0),
            "admins": users_by_role.get("admin", 0),
            "suspended": count(select(func.count()).where(User.status == "suspended")),
            "pending_deletion": count(select(func.count()).where(User.status == "deactivated")),
        },
        "departments": count(select(func.count()).select_from(Department)),
        "courses": count(select(func.count()).select_from(Course)),
        "active_courses": count(select(func.count()).where(Course.archived_at.is_(None))),
        "courses_without_teacher": len(courses_without_teacher(db)),
        "assignments": count(select(func.count()).select_from(Assignment)),
        "teams": count(select(func.count()).where(Team.closed_at.is_(None))),
        "drafts": count(select(func.count()).select_from(SubmissionVersion)),
        "finals": count(select(func.count()).where(FinalSubmission.replaced_at.is_(None))),
    }


def courses_without_teacher(db: Session) -> list[int]:
    """Courses that are not archived and have no active teacher with an active account."""
    from app.modules.courses.models import Course, Enrollment

    with_teacher = (
        select(Enrollment.course_id)
        .join(User, User.id == Enrollment.user_id)
        .where(Enrollment.role == "teacher", Enrollment.status == "active", User.status == "active")
    )
    return list(db.scalars(select(Course.id).where(Course.archived_at.is_(None), Course.id.not_in(with_teacher))))
