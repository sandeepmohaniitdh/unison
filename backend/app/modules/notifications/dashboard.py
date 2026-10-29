"""The student and teacher dashboards (pages 5 and 7), one request each."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import forbidden
from app.core.time import Clock
from app.modules.assignments.models import Assignment
from app.modules.courses.models import Course, Enrollment
from app.modules.notifications.models import Notification
from app.modules.notifications.service import notification_item, unread_count
from app.modules.reviews.models import Review
from app.modules.submissions.models import Submission
from app.modules.submissions.service import apply_deadline, my_team_state
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User


def _course(c: Course) -> dict:
    return {"id": c.id, "code": c.code, "title": c.title, "term": c.term}


def _latest(db: Session, user: User, n: int = 5) -> list[dict]:
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(n)
    )
    return [notification_item(r) for r in rows]


def _courses(db: Session, user: User, role: str) -> list[Course]:
    return list(
        db.scalars(
            select(Course)
            .join(Enrollment, Enrollment.course_id == Course.id)
            .where(
                Enrollment.user_id == user.id,
                Enrollment.status == "active",
                Enrollment.role == role,
                Course.archived_at.is_(None),
            )
            .order_by(Course.code)
        )
    )


def student(db: Session, user: User, clock: Clock) -> dict:
    from app.modules.invitations.service import my_invitations
    from app.modules.reviews.service import my_marks

    now = clock.now()
    courses = _courses(db, user, "student")
    by_id = {c.id: c for c in courses}
    deadlines = []
    for a in db.scalars(
        select(Assignment)
        .where(Assignment.course_id.in_(list(by_id) or [0]), Assignment.status != "draft")
        .order_by(Assignment.due_at)
    ):
        apply_deadline(db, a, now)
        if a.due_at > now:
            state = my_team_state(db, a, user.id, now)
            deadlines.append(
                {
                    "assignment_id": a.id,
                    "title": a.title,
                    "course": _course(by_id[a.course_id]),
                    "kind": a.kind,
                    "due_at": a.due_at,
                    **state,
                }
            )
    invitations = []
    for inv in my_invitations(db, user, clock):
        if inv["kind"] == "team":
            text = (
                f"Team {inv['team']['name']} for {inv['team']['assignment_title']} (from {inv['invited_by']['name']})"
            )
        elif inv["kind"] == "course":
            text = f"{inv['course']['code']} {inv['course']['title']} (from {inv['invited_by']['name']})"
        else:
            text = f"Join Unison as {inv['role']} (from {inv['invited_by']['name']})"
        invitations.append({"id": inv["id"], "kind": inv["kind"], "text": text, "expires_at": inv["expires_at"]})
    released = []
    rows = db.execute(
        select(TeamMember.team_id, Review.released_at)
        .join(Submission, Submission.team_id == TeamMember.team_id)
        .join(Review, Review.final_id == Submission.current_final_id)
        .where(TeamMember.user_id == user.id, TeamMember.status == "active", Review.status == "released")
        .order_by(Review.released_at.desc())
        .limit(5)
    ).all()
    for team_id, _released_at in rows:
        marks = my_marks(db, user, team_id)
        released.append(
            {
                "assignment_id": marks["assignment"]["id"],
                "title": marks["assignment"]["title"],
                "team_id": team_id,
                "my_mark": marks["my_mark"],
                "max_mark": marks["max_mark"],
                "released_at": marks["released_at"],
            }
        )
    return {
        "unread_notifications": unread_count(db, user),
        "notifications": _latest(db, user),
        "courses": [_course(c) for c in courses],
        "upcoming_deadlines": deadlines[:10],
        "pending_invitations": invitations,
        "released_marks": released,
    }


def teacher(db: Session, user: User, clock: Clock) -> dict:
    if user.role not in ("teacher", "admin"):
        raise forbidden("This dashboard is for teachers.", "TEACHERS_ONLY")
    now = clock.now()
    courses = _courses(db, user, "teacher")
    out_courses = []
    for c in courses:
        counts = dict(
            db.execute(
                select(Enrollment.status, func.count())
                .where(Enrollment.course_id == c.id, Enrollment.role == "student")
                .group_by(Enrollment.status)
            ).all()
        )
        out_courses.append(
            {**_course(c), "students": counts.get("active", 0), "pending_join_requests": counts.get("requested", 0)}
        )
    assignments = []
    by_id = {c.id: c for c in courses}
    for a in db.scalars(
        select(Assignment)
        .where(Assignment.course_id.in_(list(by_id) or [0]))
        .order_by(Assignment.due_at.desc())
        .limit(20)
    ):
        apply_deadline(db, a, now)
        teams = (
            db.execute(
                select(Submission.current_final_id)
                .join(Team, Team.id == Submission.team_id)
                .where(Team.assignment_id == a.id, Team.closed_at.is_(None))
            )
            .scalars()
            .all()
        )
        finals = [f for f in teams if f is not None]
        statuses = list(db.scalars(select(Review.status).where(Review.final_id.in_(finals or [0]))))
        assignments.append(
            {
                "id": a.id,
                "title": a.title,
                "course": _course(by_id[a.course_id]),
                "due_at": a.due_at,
                "status": a.status,
                "teams": len(teams),
                "with_final": len(finals),
                "without_final": len(teams) - len(finals),
                "reviewed": len(statuses),
                "released": statuses.count("released"),
            }
        )
    return {
        "unread_notifications": unread_count(db, user),
        "notifications": _latest(db, user),
        "courses": out_courses,
        "assignments": assignments,
    }
