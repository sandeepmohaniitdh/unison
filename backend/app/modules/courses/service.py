"""Departments, courses, the public catalogue, enrolment and join requests."""

from datetime import timedelta

from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, forbidden, not_found, too_many
from app.core.pagination import PageParams, paginate
from app.core.permissions import get_course, require_teacher, student_ids, teacher_ids
from app.core.time import Clock
from app.modules.admin.service import audit, get_setting
from app.modules.courses.models import Course, Department, Enrollment
from app.modules.notifications.service import notify, primary_email
from app.modules.users.models import User

# ---------------------------------------------------------------- departments


def dept_item(d: Department) -> dict:
    return {"id": d.id, "code": d.code, "name": d.name}


def list_departments(db: Session) -> list[dict]:
    return [dept_item(d) for d in db.scalars(select(Department).order_by(Department.code))]


def create_department(db: Session, admin: User, code: str, name: str) -> dict:
    dept = Department(code=code.strip().upper(), name=name.strip())
    db.add(dept)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("DEPARTMENT_EXISTS", "A department with this code or name exists.") from exc
    audit(db, admin, "department_created", "departments", dept.id, after=dept_item(dept))
    db.commit()
    return dept_item(dept)


def update_department(db: Session, admin: User, dept_id: int, code: str | None, name: str | None) -> dict:
    dept = db.get(Department, dept_id)
    if dept is None:
        raise not_found("Department")
    before = dept_item(dept)
    if code:
        dept.code = code.strip().upper()
    if name:
        dept.name = name.strip()
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("DEPARTMENT_EXISTS", "A department with this code or name exists.") from exc
    audit(db, admin, "department_renamed", "departments", dept.id, before=before, after=dept_item(dept))
    db.commit()
    return dept_item(dept)


# ---------------------------------------------------------------- course views


def _teachers_by_course(db: Session, course_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {cid: [] for cid in course_ids}
    if not course_ids:
        return out
    rows = db.execute(
        select(Enrollment.course_id, User.id, User.name)
        .join(User, User.id == Enrollment.user_id)
        .where(Enrollment.course_id.in_(course_ids), Enrollment.role == "teacher", Enrollment.status == "active")
        .order_by(User.name)
    )
    for course_id, user_id, name in rows:
        out[course_id].append({"id": user_id, "name": name})
    return out


def _my_statuses(db: Session, user: User | None, course_ids: list[int]) -> dict[int, str]:
    if user is None or not course_ids:
        return {}
    rows = db.execute(
        select(Enrollment.course_id, Enrollment.role, Enrollment.status).where(
            Enrollment.user_id == user.id, Enrollment.course_id.in_(course_ids)
        )
    )
    out = {}
    for course_id, role, status in rows:
        out[course_id] = role if status == "active" else status
    return out


def summaries(db: Session, courses: list[Course], user: User | None) -> list[dict]:
    ids = [c.id for c in courses]
    depts = {
        d.id: d
        for d in db.scalars(select(Department).where(Department.id.in_({c.department_id for c in courses} or {0})))
    }
    teachers = _teachers_by_course(db, ids)
    mine = _my_statuses(db, user, ids)
    return [
        {
            "id": c.id,
            "code": c.code,
            "term": c.term,
            "title": c.title,
            "department": dept_item(depts[c.department_id]),
            "teachers": teachers.get(c.id, []),
            "join_requests_open": c.join_requests_open,
            "archived": c.archived_at is not None,
            "my_status": mine.get(c.id, "none"),
        }
        for c in courses
    ]


def catalogue(
    db: Session,
    user: User | None,
    params: PageParams,
    *,
    q: str | None,
    department_id: int | None,
    term: str | None,
    include_archived: bool,
) -> dict:
    stmt = select(Course)
    if not include_archived:
        stmt = stmt.where(Course.archived_at.is_(None))
    if department_id:
        stmt = stmt.where(Course.department_id == department_id)
    if term:
        stmt = stmt.where(Course.term == term)
    if q and q.strip():
        stmt = stmt.where(_search_condition(db, q.strip()))
    stmt = stmt.order_by(Course.code, Course.term)
    page = paginate(db, stmt, params)
    page["items"] = summaries(db, page["items"], user)
    return page


def _search_condition(db: Session, q: str):
    """Search by code, title or teacher name.

    LIKE finds any part of a code or title, such as "CS3". On MySQL the
    FULLTEXT index on (code, title) also matches words in any order, such as
    "engineering software".
    """
    like = f"%{q}%"
    teacher_match = Course.id.in_(
        select(Enrollment.course_id)
        .join(User, User.id == Enrollment.user_id)
        .where(Enrollment.role == "teacher", Enrollment.status == "active", User.name.ilike(like))
    )
    if db.get_bind().dialect.name == "mysql":
        words = " ".join(w + "*" for w in q.replace('"', " ").split() if w.isalnum())
        if words:
            fulltext = text("MATCH (courses.code, courses.title) AGAINST (:q IN BOOLEAN MODE)").bindparams(q=words)
            return or_(fulltext, Course.code.ilike(like), Course.title.ilike(like), teacher_match)
    return or_(Course.code.ilike(like), Course.title.ilike(like), teacher_match)


def my_courses(db: Session, user: User) -> list[dict]:
    courses = db.scalars(
        select(Course)
        .join(Enrollment, Enrollment.course_id == Course.id)
        .where(Enrollment.user_id == user.id, Enrollment.status == "active")
        .order_by(Course.archived_at.is_not(None), Course.code)
    ).all()
    return summaries(db, list(courses), user)


def course_detail(db: Session, user: User | None, course_id: int) -> dict:
    from app.modules.assignments.models import Assignment

    course = get_course(db, course_id)
    out = summaries(db, [course], user)[0]
    out["description"] = course.description
    out["created_at"] = course.created_at
    out["student_count"] = len(student_ids(db, course.id))
    out["assignments"] = [
        {"id": a.id, "title": a.title, "kind": a.kind, "due_at": a.due_at}
        for a in db.scalars(
            select(Assignment)
            .where(Assignment.course_id == course.id, Assignment.status != "draft")
            .order_by(Assignment.due_at)
        )
    ]
    return out


# ---------------------------------------------------------------- creating and editing


def _add_teacher(db: Session, course_id: int, user_id: int, now, decided_by: int) -> None:
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == user_id))
    if row is None:
        db.add(
            Enrollment(
                course_id=course_id,
                user_id=user_id,
                role="teacher",
                status="active",
                decided_by=decided_by,
                decided_at=now,
                created_at=now,
            )
        )
    else:
        row.role = "teacher"
        row.status = "active"
        row.decided_by = decided_by
        row.decided_at = now


def create_course(db: Session, user: User, data: dict, clock: Clock) -> dict:
    if user.role not in ("teacher", "admin"):
        raise forbidden("Only teachers and administrators can create courses.", "TEACHERS_ONLY")
    if db.get(Department, data["department_id"]) is None:
        raise bad_request("UNKNOWN_DEPARTMENT", "This department does not exist.")
    now = clock.now()
    course = Course(
        department_id=data["department_id"],
        code=data["code"].strip().upper(),
        term=data["term"].strip(),
        title=data["title"].strip(),
        description=data.get("description"),
        join_requests_open=data.get("join_requests_open", True),
        created_by=user.id,
        created_at=now,
    )
    db.add(course)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("COURSE_EXISTS", "A course with this code already exists in this term.") from exc

    teacher_list = list(dict.fromkeys(data.get("teacher_ids") or []))
    if user.role == "teacher":
        teacher_list = [user.id, *[t for t in teacher_list if t != user.id]]
    for teacher_id in teacher_list:
        teacher = db.get(User, teacher_id)
        if teacher is None or teacher.role not in ("teacher", "admin") or teacher.status != "active":
            db.rollback()
            raise bad_request("NOT_A_TEACHER", f"User {teacher_id} is not an active teacher.")
        _add_teacher(db, course.id, teacher_id, now, user.id)
    if user.role == "admin":
        audit(
            db,
            user,
            "course_created",
            "courses",
            course.id,
            course_id=course.id,
            after={"code": course.code, "term": course.term, "teachers": teacher_list},
        )
    db.commit()
    return course_detail(db, user, course.id)


def update_course(db: Session, user: User, course_id: int, data: dict, clock: Clock) -> dict:
    """Edit fields, or archive with {"archived": true} (read-only from then on)."""
    archive = data.pop("archived", None)
    if archive is False:
        raise bad_request("CANNOT_UNARCHIVE", "An archived course cannot be reopened.")
    if archive and not data:
        return archive_course(db, user, course_id, clock)
    access = require_teacher(db, user, course_id)
    course = access.course
    before = {k: getattr(course, k) for k in data}
    if "department_id" in data and db.get(Department, data["department_id"]) is None:
        raise bad_request("UNKNOWN_DEPARTMENT", "This department does not exist.")
    for key, value in data.items():
        setattr(course, key, value.strip() if isinstance(value, str) and key != "description" else value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("COURSE_EXISTS", "A course with this code already exists in this term.") from exc
    if access.as_admin:
        audit(
            db,
            user,
            "course_updated",
            "courses",
            course.id,
            course_id=course.id,
            as_admin=True,
            before=before,
            after=data,
        )
    db.commit()
    if archive:
        return archive_course(db, user, course_id, clock)
    return course_detail(db, user, course.id)


def archive_course(db: Session, user: User, course_id: int, clock: Clock) -> dict:
    access = require_teacher(db, user, course_id)
    access.course.archived_at = clock.now()
    if access.as_admin:
        audit(db, user, "course_archived", "courses", course_id, course_id=course_id, as_admin=True)
    db.commit()
    return course_detail(db, user, course_id)


def add_teacher(db: Session, admin: User, course_id: int, teacher_id: int, clock: Clock) -> dict:
    course = get_course(db, course_id)
    teacher = db.get(User, teacher_id)
    if teacher is None or teacher.role not in ("teacher", "admin") or teacher.status != "active":
        raise bad_request("NOT_A_TEACHER", "Only active teachers or admins can teach a course.")
    _add_teacher(db, course.id, teacher.id, clock.now(), admin.id)
    audit(db, admin, "teacher_assigned", "courses", course.id, course_id=course.id, after={"user_id": teacher.id})
    db.commit()
    return _member(db, course.id, teacher.id)


# ---------------------------------------------------------------- members


def list_members(db: Session, user: User, course_id: int, params: PageParams, role: str | None, status: str | None):
    require_teacher(db, user, course_id, writable=False)
    stmt = (
        select(Enrollment, User)
        .join(User, User.id == Enrollment.user_id)
        .where(Enrollment.course_id == course_id, Enrollment.status != "requested")
    )
    if role:
        stmt = stmt.where(Enrollment.role == role)
    if status:
        stmt = stmt.where(Enrollment.status == status)
    stmt = stmt.order_by(Enrollment.role.desc(), User.name)
    return paginate(db, stmt, params, lambda row: member_item(db, *row))


def member_item(db: Session, enrollment: Enrollment, member: User) -> dict:
    return {
        "user": {"id": member.id, "name": member.name},
        "email": primary_email(db, member.id),
        "role": enrollment.role,
        "status": enrollment.status,
        "joined_at": enrollment.decided_at or enrollment.created_at,
    }


def _member(db: Session, course_id: int, user_id: int) -> dict:
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == user_id))
    return member_item(db, row, db.get(User, user_id))


def remove_member(db: Session, user: User, course_id: int, member_id: int, clock: Clock) -> None:
    """Remove a student (teachers and admins) or a teacher (admins only).

    Access ends at once; their pending invitations in the course are cancelled;
    teams follow the rules in teams.service.on_removed_from_course.
    """
    from app.modules.invitations.service import cancel_for_member
    from app.modules.teams.service import on_removed_from_course

    access = require_teacher(db, user, course_id)
    now = clock.now()
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == member_id))
    if row is None or row.status != "active":
        raise not_found("Member")
    if row.role == "teacher":
        if user.role != "admin":
            raise forbidden("Only administrators can remove a teacher.", "ADMIN_ONLY")
        if len(teacher_ids(db, course_id)) <= 1:
            raise conflict("LAST_TEACHER", "A course needs at least one teacher. Assign another teacher first.")
    row.status = "removed"
    row.decided_by = user.id
    row.decided_at = now
    cancel_for_member(db, course_id, member_id, now)
    team_mates = on_removed_from_course(db, course_id, member_id, now) if row.role == "student" else set()
    course = access.course
    notify(
        db,
        "removed_from_course",
        [member_id],
        f"You were removed from {course.code} {course.title}",
        "/dashboard",
        now,
        course_id=course_id,
    )
    member = db.get(User, member_id)
    if team_mates:
        notify(
            db,
            "removed_from_course",
            team_mates,
            f"{member.name} was removed from {course.code}",
            f"/courses/{course_id}",
            now,
            course_id=course_id,
        )
    audit(
        db,
        user,
        "member_removed",
        "enrollments",
        row.id,
        course_id=course_id,
        as_admin=access.as_admin,
        after={"user_id": member_id, "role": row.role},
    )
    db.commit()


def reinstate_member(db: Session, user: User, course_id: int, member_id: int, clock: Clock) -> dict:
    """Re-enrol a removed student before the course is archived: access returns as it was."""
    from app.modules.teams.service import on_reinstated

    access = require_teacher(db, user, course_id)
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == member_id))
    if row is None or row.status != "removed":
        raise conflict("NOT_REMOVED", "Only removed members can be re-enrolled.")
    row.status = "active"
    row.decided_by = user.id
    row.decided_at = clock.now()
    on_reinstated(db, course_id, member_id)
    audit(db, user, "member_reinstated", "enrollments", row.id, course_id=course_id, as_admin=access.as_admin)
    db.commit()
    return _member(db, course_id, member_id)


# ---------------------------------------------------------------- join requests


def request_join(db: Session, user: User, course_id: int, clock: Clock) -> dict:
    now = clock.now()
    course = get_course(db, course_id)
    if course.archived_at is not None:
        raise conflict("COURSE_ARCHIVED", "This course is archived.")
    if not course.join_requests_open:
        raise conflict(
            "JOIN_REQUESTS_CLOSED", "This course does not take join requests. Ask the teacher for an invitation."
        )
    if user.role != "student":
        raise forbidden("Only students can request to join.", "STUDENTS_ONLY")
    limit = int(get_setting(db, "join_requests_per_day"))
    today = db.scalar(
        select(func.count()).where(Enrollment.user_id == user.id, Enrollment.requested_at >= now - timedelta(days=1))
    )
    if (today or 0) >= limit:
        raise too_many("JOIN_REQUEST_LIMIT", f"You can make at most {limit} join requests a day.", 3600)
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == user.id))
    if row is not None and row.status == "active":
        raise conflict("ALREADY_MEMBER", "You are already in this course.")
    if row is not None and row.status == "requested":
        raise conflict("ALREADY_REQUESTED", "Your request is waiting for the teacher.")
    if row is not None and row.status == "removed":
        raise conflict("REMOVED_FROM_COURSE", "You were removed from this course. Ask the teacher to re-enrol you.")
    if row is None:
        row = Enrollment(course_id=course_id, user_id=user.id, role="student", status="requested", created_at=now)
        db.add(row)
    row.status = "requested"
    row.requested_at = now
    row.decided_by = None
    row.decided_at = None
    db.flush()
    notify(
        db,
        "join_request_received",
        teacher_ids(db, course_id),
        f"{user.name} asked to join {course.code}",
        f"/courses/{course_id}/manage?tab=requests",
        now,
        course_id=course_id,
    )
    db.commit()
    return {"course_id": course_id, "status": row.status, "role": row.role}


def cancel_join_request(db: Session, user: User, course_id: int) -> None:
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == user.id))
    if row is None or row.status != "requested":
        raise not_found("Join request")
    db.delete(row)
    db.commit()


def list_join_requests(db: Session, user: User, course_id: int, params: PageParams) -> dict:
    require_teacher(db, user, course_id, writable=False)
    stmt = (
        select(Enrollment, User)
        .join(User, User.id == Enrollment.user_id)
        .where(Enrollment.course_id == course_id, Enrollment.status == "requested")
        .order_by(Enrollment.requested_at)
    )

    def item(row):
        enrollment, student = row
        return {
            "id": enrollment.id,
            "user": {"id": student.id, "name": student.name},
            "email": primary_email(db, student.id),
            "requested_at": enrollment.requested_at,
            "status": enrollment.status,
        }

    return paginate(db, stmt, params, item)


def decide_join_request(db: Session, user: User, course_id: int, request_id: int, approve: bool, clock: Clock) -> dict:
    access = require_teacher(db, user, course_id)
    now = clock.now()
    row = db.get(Enrollment, request_id)
    if row is None or row.course_id != course_id or row.status != "requested":
        raise not_found("Join request")
    row.status = "active" if approve else "rejected"
    row.decided_by = user.id
    row.decided_at = now
    course = access.course
    if approve:
        notify(
            db,
            "enrolment_approved",
            [row.user_id],
            f"You joined {course.code} {course.title}",
            f"/courses/{course_id}",
            now,
            course_id=course_id,
        )
    else:
        notify(
            db,
            "enrolment_rejected",
            [row.user_id],
            f"Your request to join {course.code} was not approved",
            "/courses",
            now,
            course_id=course_id,
        )
    if access.as_admin:
        audit(
            db,
            user,
            "join_request_decided",
            "enrollments",
            row.id,
            course_id=course_id,
            as_admin=True,
            after={"approved": approve},
        )
    db.commit()
    return {"course_id": course_id, "status": row.status, "role": row.role}


def enrol_student(db: Session, course_id: int, user_id: int, now) -> None:
    """Used when a course invitation is accepted."""
    row = db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.user_id == user_id))
    if row is None:
        db.add(
            Enrollment(
                course_id=course_id, user_id=user_id, role="student", status="active", decided_at=now, created_at=now
            )
        )
    elif row.status != "active":
        row.status = "active"
        row.decided_at = now
