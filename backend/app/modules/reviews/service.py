"""Reviewing a team's final, marks and adjustments.

- One team mark: the sum of the rubric scores (computed, never stored).
- A teacher can adjust one member's mark by -20% to +10% of the team mark,
  with a reason the member sees. Member mark = team mark + adjustment, kept
  between 0 and the maximum.
- The review page shows a contribution summary from the draft history
  (drafts per member, last upload, who submitted), never the drafts.
- Reviews start after the deadline, when the final can no longer change.
- Releasing notifies every member; each sees only their own adjustment.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found, unprocessable
from app.core.pagination import PageParams, page_of
from app.core.permissions import require_teacher
from app.core.time import Clock
from app.modules.admin.service import audit
from app.modules.assignments.models import Assignment, RubricCriterion
from app.modules.assignments.service import get_assignment, rubric
from app.modules.notifications.service import notify
from app.modules.reviews.models import MemberAdjustment, Review, ReviewScore
from app.modules.submissions.models import FinalSubmission, Submission, SubmissionVersion
from app.modules.submissions.service import apply_deadline, final_item, team_state
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User

TENTH = Decimal("0.1")


def member_mark(team_mark: Decimal, percent: Decimal | None, max_mark: Decimal) -> Decimal:
    if percent is None:
        return team_mark.quantize(TENTH, ROUND_HALF_UP)
    adjusted = team_mark + team_mark * percent / Decimal(100)
    return min(max(adjusted, Decimal(0)), max_mark).quantize(TENTH, ROUND_HALF_UP)


def _team_mark(db: Session, review: Review | None, criteria: list[RubricCriterion]) -> Decimal | None:
    if review is None:
        return None
    scores = {
        s.criterion_id: s.points for s in db.scalars(select(ReviewScore).where(ReviewScore.review_id == review.id))
    }
    if any(c.id not in scores for c in criteria):
        return None
    return sum((scores[c.id] for c in criteria), Decimal(0))


def _max_mark(criteria: list[RubricCriterion]) -> Decimal:
    return sum((c.max_points for c in criteria), Decimal(0))


def _context(db: Session, user: User, team_id: int, clock: Clock):
    """Team, assignment, course access and the current final, for teachers."""
    team = db.get(Team, team_id)
    if team is None:
        raise not_found("Team")
    assignment = db.get(Assignment, team.assignment_id)
    access = require_teacher(db, user, assignment.course_id, writable=False)
    apply_deadline(db, assignment, clock.now())
    sub = db.scalar(select(Submission).where(Submission.team_id == team.id))
    if sub is None or sub.current_final_id is None:
        raise conflict("NO_FINAL", "This team has no submitted final.")
    final = db.get(FinalSubmission, sub.current_final_id)
    return team, assignment, access, sub, final


def _members(db: Session, team_id: int) -> list[tuple[TeamMember, User]]:
    return db.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team_id, TeamMember.status.in_(["active", "removed", "former"]))
        .order_by(User.name)
    ).all()


def contribution(db: Session, sub: Submission, final: FinalSubmission, members) -> list[dict]:
    counts = dict(
        db.execute(
            select(SubmissionVersion.uploaded_by, func.count())
            .where(SubmissionVersion.submission_id == sub.id)
            .group_by(SubmissionVersion.uploaded_by)
        ).all()
    )
    last = dict(
        db.execute(
            select(SubmissionVersion.uploaded_by, func.max(SubmissionVersion.created_at))
            .where(SubmissionVersion.submission_id == sub.id)
            .group_by(SubmissionVersion.uploaded_by)
        ).all()
    )
    return [
        {
            "user": {"id": u.id, "name": u.name},
            "status": m.status,
            "drafts_uploaded": counts.get(u.id, 0),
            "last_upload_at": last.get(u.id),
            "submitted_current_final": final.submitted_by == u.id,
        }
        for m, u in members
    ]


def sheet(db: Session, user: User, team_id: int, clock: Clock) -> dict:
    team, assignment, _access, sub, final = _context(db, user, team_id, clock)
    criteria = rubric(db, assignment.id)
    review = db.scalar(select(Review).where(Review.final_id == final.id))
    scores = {}
    if review is not None:
        scores = {s.criterion_id: s for s in db.scalars(select(ReviewScore).where(ReviewScore.review_id == review.id))}
    adjustments = {}
    if review is not None:
        adjustments = {
            a.user_id: a for a in db.scalars(select(MemberAdjustment).where(MemberAdjustment.review_id == review.id))
        }
    team_mark = _team_mark(db, review, criteria)
    max_mark = _max_mark(criteria)
    members = _members(db, team.id)
    finals_count = (
        db.scalar(
            select(func.count())
            .select_from(FinalSubmission)
            .join(SubmissionVersion, SubmissionVersion.id == FinalSubmission.version_id)
            .where(SubmissionVersion.submission_id == sub.id)
        )
        or 1
    )
    return {
        "team": {"id": team.id, "name": team.name},
        "assignment": {"id": assignment.id, "title": assignment.title, "course_id": assignment.course_id},
        "final": final_item(db, final),
        "replaced_finals": finals_count - 1,
        "contribution": contribution(db, sub, final, members),
        "rubric": [
            {
                "criterion_id": c.id,
                "position": c.position,
                "title": c.title,
                "max_points": c.max_points,
                "points": scores[c.id].points if c.id in scores else None,
                "comment": scores[c.id].comment if c.id in scores else None,
            }
            for c in criteria
        ],
        "overall_comment": review.overall_comment if review else None,
        "status": review.status if review else "none",
        "released_at": review.released_at if review else None,
        "team_mark": team_mark,
        "max_mark": max_mark,
        "members": [
            {
                "user": {"id": u.id, "name": u.name},
                "adjustment_percent": adjustments[u.id].percent if u.id in adjustments else None,
                "reason": adjustments[u.id].reason if u.id in adjustments else None,
                "mark": member_mark(team_mark, adjustments[u.id].percent if u.id in adjustments else None, max_mark)
                if team_mark is not None
                else None,
            }
            for _m, u in members
        ],
    }


def _editable_review(db: Session, user: User, team_id: int, clock: Clock):
    team, assignment, access, sub, final = _context(db, user, team_id, clock)
    if access.course.archived_at is not None:
        raise conflict("COURSE_ARCHIVED", "This course is archived and read-only.")
    if sub.closed_at is None:
        raise conflict("SUBMISSION_OPEN", "Reviews start after the deadline, when the final can no longer change.")
    review = db.scalar(select(Review).where(Review.final_id == final.id))
    if review is not None and review.status == "released":
        raise conflict("REVIEW_RELEASED", "Marks are released and can no longer change.")
    if review is None:
        review = Review(final_id=final.id, reviewer_id=user.id, status="draft", updated_at=clock.now())
        db.add(review)
        db.flush()
    return team, assignment, access, review


def save_review(db: Session, user: User, team_id: int, data: dict, clock: Clock) -> dict:
    team, assignment, access, review = _editable_review(db, user, team_id, clock)
    criteria = {c.id: c for c in rubric(db, assignment.id)}
    for score in data.get("scores", []):
        criterion = criteria.get(score["criterion_id"])
        if criterion is None:
            raise unprocessable("UNKNOWN_CRITERION", f"Criterion {score['criterion_id']} is not in this rubric.")
        if score["points"] > criterion.max_points:
            raise unprocessable(
                "POINTS_OUT_OF_RANGE",
                f"{criterion.title}: at most {criterion.max_points} points.",
                {"criterion_id": criterion.id, "max_points": str(criterion.max_points)},
            )
        row = db.get(ReviewScore, (review.id, criterion.id))
        if row is None:
            db.add(
                ReviewScore(
                    review_id=review.id, criterion_id=criterion.id, points=score["points"], comment=score.get("comment")
                )
            )
        else:
            row.points = score["points"]
            row.comment = score.get("comment")
    if "overall_comment" in data:
        review.overall_comment = data["overall_comment"]
    review.reviewer_id = user.id
    review.updated_at = clock.now()
    if access.as_admin:
        audit(db, user, "review_saved", "reviews", review.id, course_id=assignment.course_id, as_admin=True)
    db.commit()
    return sheet(db, user, team.id, clock)


def set_adjustment(db: Session, user: User, team_id: int, member_id: int, percent: Decimal, reason: str, clock: Clock):
    team, assignment, access, review = _editable_review(db, user, team_id, clock)
    row = db.get(TeamMember, (assignment.id, member_id))
    if row is None or row.team_id != team.id or row.status == "left":
        raise not_found("Team member")
    adj = db.get(MemberAdjustment, (review.id, member_id))
    if adj is None:
        adj = MemberAdjustment(
            review_id=review.id,
            user_id=member_id,
            percent=percent,
            reason=reason.strip(),
            set_by=user.id,
            set_at=clock.now(),
        )
        db.add(adj)
    else:
        adj.percent, adj.reason, adj.set_by, adj.set_at = percent, reason.strip(), user.id, clock.now()
    audit(
        db,
        user,
        "mark_adjusted",
        "reviews",
        review.id,
        course_id=assignment.course_id,
        as_admin=access.as_admin,
        after={"user_id": member_id, "percent": str(percent)},
    )
    db.commit()
    return sheet(db, user, team.id, clock)


def remove_adjustment(db: Session, user: User, team_id: int, member_id: int, clock: Clock) -> None:
    _team, _assignment, _access, review = _editable_review(db, user, team_id, clock)
    db.execute(
        delete(MemberAdjustment).where(MemberAdjustment.review_id == review.id, MemberAdjustment.user_id == member_id)
    )
    db.commit()


def _release(db: Session, user: User, team: Team, assignment: Assignment, review: Review, clock: Clock) -> None:
    criteria = rubric(db, assignment.id)
    if _team_mark(db, review, criteria) is None:
        raise conflict("REVIEW_INCOMPLETE", "Score every criterion before releasing.")
    now = clock.now()
    review.status = "released"
    review.released_at = now
    members = [u.id for _m, u in _members(db, team.id)]
    notify(
        db,
        "marks_released",
        members,
        f"Marks released for {assignment.title}",
        f"/teams/{team.id}/marks",
        now,
        course_id=assignment.course_id,
    )


def release(db: Session, user: User, team_id: int, clock: Clock) -> dict:
    team, assignment, access, review = _editable_review(db, user, team_id, clock)
    _release(db, user, team, assignment, review, clock)
    if access.as_admin:
        audit(db, user, "marks_released", "reviews", review.id, course_id=assignment.course_id, as_admin=True)
    db.commit()
    return sheet(db, user, team.id, clock)


def release_all(db: Session, user: User, assignment_id: int, clock: Clock) -> dict:
    assignment = get_assignment(db, assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    apply_deadline(db, assignment, clock.now())
    released, skipped = 0, []
    teams = db.scalars(select(Team).where(Team.assignment_id == assignment.id).order_by(Team.name)).all()
    for team in teams:
        sub = db.scalar(select(Submission).where(Submission.team_id == team.id))
        if sub is None or sub.current_final_id is None:
            continue
        if sub.closed_at is None:
            skipped.append({"team_id": team.id, "reason": "deadline not passed"})
            continue
        review = db.scalar(select(Review).where(Review.final_id == sub.current_final_id))
        if review is None:
            skipped.append({"team_id": team.id, "reason": "not reviewed"})
            continue
        if review.status == "released":
            continue
        try:
            _release(db, user, team, assignment, review, clock)
            released += 1
        except Exception as exc:  # noqa: BLE001 - report and carry on with the next team
            skipped.append({"team_id": team.id, "reason": getattr(exc, "message", "could not release")})
    if access.as_admin:
        audit(
            db,
            user,
            "marks_released",
            "assignments",
            assignment.id,
            course_id=assignment.course_id,
            as_admin=True,
            after={"released": released},
        )
    db.commit()
    return {"released": released, "skipped": skipped}


def overview(db: Session, user: User, assignment_id: int, params: PageParams, clock: Clock) -> dict:
    """Every team's state for the review page."""
    assignment = get_assignment(db, assignment_id)
    require_teacher(db, user, assignment.course_id, writable=False)
    now = clock.now()
    apply_deadline(db, assignment, now)
    criteria = rubric(db, assignment.id)
    max_mark = _max_mark(criteria)
    rows = []
    for team in db.scalars(
        select(Team).where(Team.assignment_id == assignment.id, Team.closed_at.is_(None)).order_by(Team.name)
    ):
        sub = db.scalar(select(Submission).where(Submission.team_id == team.id))
        final = db.get(FinalSubmission, sub.current_final_id) if sub and sub.current_final_id else None
        review = db.scalar(select(Review).where(Review.final_id == final.id)) if final else None
        version = db.get(SubmissionVersion, final.version_id) if final else None
        members = db.scalar(select(func.count()).where(TeamMember.team_id == team.id, TeamMember.status == "active"))
        rows.append(
            {
                "team": {"id": team.id, "name": team.name},
                "member_count": members or 0,
                "state": team_state(db, team, assignment, now),
                "final_id": final.id if final else None,
                "version_number": version.number if version else None,
                "final_kind": final.kind if final else None,
                "below_min_size": final.below_min_size if final else False,
                "submitted_at": final.submitted_at if final else None,
                "review_status": review.status if review else "none",
                "team_mark": _team_mark(db, review, criteria),
                "max_mark": max_mark,
            }
        )
    return page_of(rows, params)


def my_marks(db: Session, user: User, team_id: int) -> dict:
    from app.modules.teams.service import get_team, require_active_member

    team = get_team(db, team_id)
    require_active_member(db, team, user)
    assignment = db.get(Assignment, team.assignment_id)
    sub = db.scalar(select(Submission).where(Submission.team_id == team.id))
    review = db.scalar(select(Review).where(Review.final_id == sub.current_final_id)) if sub.current_final_id else None
    if review is None or review.status != "released":
        raise not_found("Released marks")
    criteria = rubric(db, assignment.id)
    scores = {s.criterion_id: s for s in db.scalars(select(ReviewScore).where(ReviewScore.review_id == review.id))}
    team_mark = _team_mark(db, review, criteria)
    max_mark = _max_mark(criteria)
    adj = db.get(MemberAdjustment, (review.id, user.id))
    return {
        "assignment": {"id": assignment.id, "title": assignment.title, "course_id": assignment.course_id},
        "team": {"id": team.id, "name": team.name},
        "rubric": [
            {
                "criterion_id": c.id,
                "position": c.position,
                "title": c.title,
                "max_points": c.max_points,
                "points": scores[c.id].points,
                "comment": scores[c.id].comment,
            }
            for c in criteria
        ],
        "overall_comment": review.overall_comment,
        "team_mark": team_mark,
        "max_mark": max_mark,
        "adjustment_percent": adj.percent if adj else None,
        "adjustment_reason": adj.reason if adj else None,
        "my_mark": member_mark(team_mark, adj.percent if adj else None, max_mark),
        "released_at": review.released_at,
    }
