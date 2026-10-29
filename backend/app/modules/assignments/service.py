"""Assignments, rubrics, deadlines and team locking.

Deadlines are entered and shown in IST and stored in UTC. A deadline of
23:59 means 23:59:59 IST.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found
from app.core.pagination import PageParams, paginate
from app.core.permissions import CourseAccess, require_member, require_teacher, student_ids
from app.core.time import Clock, ist_text, to_ist
from app.modules.admin.service import audit
from app.modules.assignments.models import Assignment, RubricCriterion
from app.modules.notifications.service import notify
from app.modules.users.models import User

DRAFT_ONLY_FIELDS = {"kind", "min_team", "max_team", "max_files", "requires_pdf", "rubric"}


def get_assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise not_found("Assignment")
    return assignment


def rubric(db: Session, assignment_id: int) -> list[RubricCriterion]:
    return list(
        db.scalars(
            select(RubricCriterion)
            .where(RubricCriterion.assignment_id == assignment_id)
            .order_by(RubricCriterion.position)
        )
    )


def total_points(db: Session, assignment_id: int) -> Decimal:
    return db.scalar(
        select(func.coalesce(func.sum(RubricCriterion.max_points), 0)).where(
            RubricCriterion.assignment_id == assignment_id
        )
    ) or Decimal("0")


def normalise_deadline(due_at: datetime) -> datetime:
    """23:59 IST means the end of that minute: 23:59:59 IST."""
    local = to_ist(due_at)
    if local.hour == 23 and local.minute == 59 and local.second == 0:
        return due_at + timedelta(seconds=59)
    return due_at


def access_for_assignment(db: Session, user: User, assignment: Assignment) -> CourseAccess:
    """Members see published assignments; drafts are only for the course's teachers (404 for others)."""
    access = require_member(db, user, assignment.course_id)
    if assignment.status == "draft" and not access.is_teacher:
        raise not_found("Assignment")
    return access


def summary(db: Session, a: Assignment, user: User | None, access: CourseAccess | None, now: datetime) -> dict:
    from app.modules.submissions.service import my_team_state

    out = {
        "id": a.id,
        "course_id": a.course_id,
        "title": a.title,
        "kind": a.kind,
        "min_team": a.min_team,
        "max_team": a.max_team,
        "due_at": a.due_at,
        "status": a.status,
        "teams_locked": a.teams_locked,
        "total_points": total_points(db, a.id),
        "my_team": None,
    }
    if user is not None and access is not None and access.role == "student" and a.status != "draft":
        out["my_team"] = my_team_state(db, a, user.id, now)
    return out


def detail(db: Session, a: Assignment, user: User, access: CourseAccess, now: datetime) -> dict:
    out = summary(db, a, user, access, now)
    out.update(
        description=a.description,
        max_files=a.max_files,
        requires_pdf=a.requires_pdf,
        published_at=a.published_at,
        rubric=[
            {"id": c.id, "position": c.position, "title": c.title, "max_points": c.max_points} for c in rubric(db, a.id)
        ],
    )
    return out


def list_for_course(db: Session, user: User, course_id: int, params: PageParams, clock: Clock) -> dict:
    from app.modules.submissions.service import apply_deadlines_for_course

    access = require_member(db, user, course_id)
    apply_deadlines_for_course(db, course_id, clock.now())
    stmt = select(Assignment).where(Assignment.course_id == course_id)
    if not access.is_teacher:
        stmt = stmt.where(Assignment.status != "draft")
    stmt = stmt.order_by(Assignment.due_at, Assignment.id)
    now = clock.now()
    return paginate(db, stmt, params, lambda a: summary(db, a, user, access, now))


def get_detail(db: Session, user: User, assignment_id: int, clock: Clock) -> dict:
    from app.modules.submissions.service import apply_deadline

    assignment = get_assignment(db, assignment_id)
    access = access_for_assignment(db, user, assignment)
    apply_deadline(db, assignment, clock.now())
    return detail(db, assignment, user, access, clock.now())


def _set_rubric(db: Session, assignment_id: int, items: list[dict]) -> None:
    db.execute(delete(RubricCriterion).where(RubricCriterion.assignment_id == assignment_id))
    db.flush()
    for position, item in enumerate(items, start=1):
        db.add(
            RubricCriterion(
                assignment_id=assignment_id,
                position=position,
                title=item["title"].strip(),
                max_points=item["max_points"],
            )
        )


def create(db: Session, user: User, course_id: int, data: dict, clock: Clock) -> dict:
    access = require_teacher(db, user, course_id)
    now = clock.now()
    due_at = normalise_deadline(data["due_at"])
    if due_at <= now:
        raise bad_request("DEADLINE_IN_PAST", "The deadline must be in the future.")
    assignment = Assignment(
        course_id=course_id,
        title=data["title"].strip(),
        description=data.get("description"),
        kind=data["kind"],
        min_team=data["min_team"],
        max_team=data["max_team"],
        max_files=data["max_files"],
        requires_pdf=data["requires_pdf"],
        due_at=due_at,
        status="draft",
        teams_locked=False,
        created_by=user.id,
    )
    db.add(assignment)
    db.flush()
    _set_rubric(db, assignment.id, data["rubric"])
    if access.as_admin:
        audit(db, user, "assignment_created", "assignments", assignment.id, course_id=course_id, as_admin=True)
    db.commit()
    return detail(db, assignment, user, access, now)


def update(db: Session, user: User, assignment_id: int, data: dict, clock: Clock) -> dict:
    """PATCH /assignments/{id}: one endpoint for every change.

    - title, description: any time
    - kind, team sizes, file limit, PDF rule, rubric: only while a draft
    - due_at: any future time while a draft; once published, only later than now
      (an extension, which notifies the class)
    - teams_locked: lock or unlock the teams of a group assignment
    - status "published": publish the draft (notifies the class)
    """
    publish_now = data.pop("status", None) == "published"
    lock = data.pop("teams_locked", None)
    assignment = get_assignment(db, assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    now = clock.now()
    if assignment.status != "draft":
        locked_fields = set(data) & DRAFT_ONLY_FIELDS
        if locked_fields:
            raise conflict(
                "ASSIGNMENT_PUBLISHED",
                "Only the title, description, deadline and team lock can change after publishing.",
                {"fields": sorted(locked_fields)},
            )
        if publish_now:
            raise conflict("ALREADY_PUBLISHED", "This assignment is already published.")
        if "due_at" in data:
            extend(db, user, assignment_id, data.pop("due_at"), clock)
    if lock is not None:
        set_lock(db, user, assignment_id, lock, clock)
    if "rubric" in data:
        _set_rubric(db, assignment.id, data.pop("rubric"))
    if "due_at" in data:
        data["due_at"] = normalise_deadline(data["due_at"])
        if data["due_at"] <= now:
            raise bad_request("DEADLINE_IN_PAST", "The deadline must be in the future.")
    for key, value in data.items():
        setattr(assignment, key, value)
    if assignment.kind == "individual":
        assignment.min_team = assignment.max_team = 1
    if assignment.max_team < assignment.min_team:
        raise bad_request("TEAM_SIZE", "max_team must be at least min_team.")
    if access.as_admin and data:
        audit(
            db, user, "assignment_updated", "assignments", assignment.id, course_id=assignment.course_id, as_admin=True
        )
    db.commit()
    if publish_now:
        return publish(db, user, assignment_id, clock)
    return detail(db, assignment, user, access, now)


def remove(db: Session, user: User, assignment_id: int) -> None:
    assignment = get_assignment(db, assignment_id)
    require_teacher(db, user, assignment.course_id)
    if assignment.status != "draft":
        raise conflict("ASSIGNMENT_PUBLISHED", "Published assignments cannot be deleted.")
    db.delete(assignment)  # rubric rows go with it (ON DELETE CASCADE)
    db.commit()


def publish(db: Session, user: User, assignment_id: int, clock: Clock) -> dict:
    assignment = get_assignment(db, assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    now = clock.now()
    if assignment.status != "draft":
        raise conflict("ALREADY_PUBLISHED", "This assignment is already published.")
    if assignment.due_at <= now:
        raise bad_request("DEADLINE_IN_PAST", "Move the deadline into the future before publishing.")
    assignment.status = "published"
    assignment.published_at = now
    course = access.course
    notify(
        db,
        "assignment_published",
        student_ids(db, course.id),
        f"New assignment in {course.code}: {assignment.title} (due {ist_text(assignment.due_at)})",
        f"/assignments/{assignment.id}",
        now,
        course_id=course.id,
    )
    if access.as_admin:
        audit(db, user, "assignment_published", "assignments", assignment.id, course_id=course.id, as_admin=True)
    db.commit()
    return detail(db, assignment, user, access, now)


def extend(db: Session, user: User, assignment_id: int, due_at: datetime, clock: Clock) -> dict:
    assignment = get_assignment(db, assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    now = clock.now()
    due_at = normalise_deadline(due_at)
    if assignment.status != "published" or assignment.due_at <= now:
        raise conflict("DEADLINE_PASSED", "A deadline can only be extended before it passes.")
    if due_at <= assignment.due_at:
        raise bad_request("NOT_LATER", "The new deadline must be later than the current one.")
    before = assignment.due_at
    assignment.due_at = due_at
    course = access.course
    notify(
        db,
        "deadline_extended",
        student_ids(db, course.id),
        f"Deadline extended for {assignment.title}: now {ist_text(due_at)}",
        f"/assignments/{assignment.id}",
        now,
        course_id=course.id,
    )
    audit(
        db,
        user,
        "deadline_extended",
        "assignments",
        assignment.id,
        course_id=course.id,
        as_admin=access.as_admin,
        before={"due_at": before.isoformat()},
        after={"due_at": due_at.isoformat()},
    )
    db.commit()
    return detail(db, assignment, user, access, now)


def set_lock(db: Session, user: User, assignment_id: int, locked: bool, clock: Clock) -> dict:
    assignment = get_assignment(db, assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    if assignment.kind != "group":
        raise conflict("NOT_GROUP", "Only group assignments have teams to lock.")
    assignment.teams_locked = locked
    if access.as_admin:
        audit(
            db,
            user,
            "teams_locked" if locked else "teams_unlocked",
            "assignments",
            assignment.id,
            course_id=assignment.course_id,
            as_admin=True,
        )
    db.commit()
    return detail(db, assignment, user, access, clock.now())
