"""Teams.

- A student creates a team for a group assignment and invites classmates
  (invitations module). The creator has no extra rights.
- Members + pending invitations can never exceed max_team.
- One team per student per assignment (primary key of team_members).
- A student can leave before the team's first final; after it, only a
  teacher can remove or move someone, until marks are released.
- An individual assignment is a team of one, created automatically.
"""

from datetime import datetime

from sqlalchemy import exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found
from app.core.pagination import PageParams, paginate
from app.core.permissions import course_access, require_student, require_teacher
from app.core.time import Clock
from app.modules.admin.service import audit
from app.modules.assignments.models import Assignment
from app.modules.assignments.service import get_assignment
from app.modules.invitations.models import Invitation
from app.modules.notifications.service import notify
from app.modules.submissions.models import FinalSubmission, Submission, SubmissionVersion
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User

# ---------------------------------------------------------------- small helpers


def get_team(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise not_found("Team")
    return team


def active_member_ids(db: Session, team_id: int) -> list[int]:
    return list(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id, TeamMember.status == "active"))
    )


def pending_invitation_count(db: Session, team_id: int) -> int:
    return db.scalar(select(func.count()).where(Invitation.team_id == team_id, Invitation.status == "pending")) or 0


def has_final(db: Session, team_id: int) -> bool:
    """True once the team has submitted any final (even if it was replaced later)."""
    return bool(
        db.scalar(
            select(
                exists()
                .where(Submission.team_id == team_id)
                .where(SubmissionVersion.submission_id == Submission.id)
                .where(FinalSubmission.version_id == SubmissionVersion.id)
            )
        )
    )


def marks_released(db: Session, team_id: int) -> bool:
    from app.modules.reviews.models import Review

    return bool(
        db.scalar(
            select(
                exists().where(
                    Submission.team_id == team_id,
                    Review.final_id == Submission.current_final_id,
                    Review.status == "released",
                )
            )
        )
    )


def membership(db: Session, assignment_id: int, user_id: int) -> TeamMember | None:
    return db.get(TeamMember, (assignment_id, user_id))


def require_active_member(db: Session, team: Team, user: User) -> TeamMember:
    """404 for people who are not on the team: they should not learn it exists."""
    row = membership(db, team.assignment_id, user.id)
    if row is None or row.team_id != team.id or row.status != "active":
        raise not_found("Team")
    return row


def check_students_can_change(assignment: Assignment, now: datetime) -> None:
    if assignment.status != "published":
        raise conflict("ASSIGNMENT_NOT_OPEN", "This assignment is not open.")
    if assignment.due_at <= now:
        raise conflict("DEADLINE_PASSED", "The deadline has passed.")
    if assignment.teams_locked:
        raise conflict("TEAMS_LOCKED", "The teacher has locked the teams.")


def _new_team(db: Session, assignment: Assignment, name: str, creator_id: int, now: datetime) -> Team:
    team = Team(assignment_id=assignment.id, name=name, created_by=creator_id, created_at=now)
    db.add(team)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("TEAM_NAME_TAKEN", "Another team already uses this name.") from exc
    db.add(Submission(team_id=team.id, created_at=now))
    return team


def _place_member(db: Session, assignment_id: int, team_id: int, user_id: int, now: datetime) -> None:
    """Put a student on a team, reusing their row if they were on another team before."""
    row = membership(db, assignment_id, user_id)
    if row is None:
        db.add(
            TeamMember(assignment_id=assignment_id, user_id=user_id, team_id=team_id, status="active", joined_at=now)
        )
    else:
        row.team_id = team_id
        row.status = "active"
        row.joined_at = now
        row.left_at = None
    db.flush()


def _close_if_empty(db: Session, team: Team, now: datetime) -> None:
    if not active_member_ids(db, team.id) and not has_final(db, team.id):
        team.closed_at = now
        db.execute(
            update(Invitation)
            .where(Invitation.team_id == team.id, Invitation.status == "pending")
            .values(status="cancelled", responded_at=now)
        )


# ---------------------------------------------------------------- views


def team_detail(db: Session, team: Team, viewer: User, now: datetime) -> dict:
    from app.modules.submissions.service import team_state

    assignment = db.get(Assignment, team.assignment_id)
    members = db.execute(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team.id, TeamMember.status != "left")
        .order_by(TeamMember.joined_at)
    ).all()
    is_member = any(m.user_id == viewer.id and m.status == "active" for m, _u in members)
    active = sum(1 for m, _u in members if m.status == "active")
    pending = []
    if is_member:
        rows = db.execute(
            select(Invitation, User.name)
            .join(User, User.id == Invitation.invited_by)
            .where(Invitation.team_id == team.id, Invitation.status == "pending")
            .order_by(Invitation.created_at)
        ).all()
        pending = [
            {
                "id": inv.id,
                "email": inv.email,
                "invited_by": {"id": inv.invited_by, "name": name},
                "expires_at": inv.expires_at,
            }
            for inv, name in rows
        ]
    pending_count = len(pending) if is_member else pending_invitation_count(db, team.id)
    return {
        "id": team.id,
        "name": team.name,
        "assignment_id": team.assignment_id,
        "course_id": assignment.course_id,
        "kind": assignment.kind,
        "min_team": assignment.min_team,
        "max_team": assignment.max_team,
        "closed": team.closed_at is not None,
        "created_by": team.created_by,
        "members": [
            {"user": {"id": u.id, "name": u.name}, "status": m.status, "joined_at": m.joined_at} for m, u in members
        ],
        "pending_invitations": pending,
        "places_left": max(0, assignment.max_team - active - pending_count),
        "has_final": has_final(db, team.id),
        "state": team_state(db, team, assignment, now),
    }


def view_team(db: Session, user: User, team_id: int, clock: Clock) -> dict:
    from app.modules.submissions.service import apply_deadline

    team = get_team(db, team_id)
    assignment = db.get(Assignment, team.assignment_id)
    access = course_access(db, user, assignment.course_id)
    if not access.is_teacher:
        require_active_member(db, team, user)
    apply_deadline(db, assignment, clock.now())
    return team_detail(db, team, user, clock.now())


def list_teams(db: Session, user: User, assignment_id: int, params: PageParams, clock: Clock) -> dict:
    from app.modules.submissions.service import apply_deadline

    assignment = get_assignment(db, assignment_id)
    require_teacher(db, user, assignment.course_id, writable=False)
    apply_deadline(db, assignment, clock.now())
    stmt = select(Team).where(Team.assignment_id == assignment_id).order_by(Team.closed_at.is_not(None), Team.name)
    now = clock.now()
    return paginate(db, stmt, params, lambda t: team_detail(db, t, user, now))


def my_team(db: Session, user: User, assignment_id: int, clock: Clock) -> dict:
    """The student's team. For individual assignments it is created on first use."""
    from app.modules.submissions.service import apply_deadline

    assignment = get_assignment(db, assignment_id)
    access = course_access(db, user, assignment.course_id)
    if access.role != "student" or assignment.status == "draft":
        raise not_found("Team")
    now = clock.now()
    apply_deadline(db, assignment, now)
    row = membership(db, assignment.id, user.id)
    if row is not None and row.status == "active":
        return team_detail(db, db.get(Team, row.team_id), user, now)
    if assignment.kind == "individual" and assignment.status == "published" and assignment.due_at > now:
        team = individual_team(db, assignment, user.id, now)
        db.commit()
        return team_detail(db, team, user, now)
    raise not_found("Team")


def individual_team(db: Session, assignment: Assignment, user_id: int, now: datetime) -> Team:
    row = membership(db, assignment.id, user_id)
    if row is not None:
        return db.get(Team, row.team_id)
    team = _new_team(db, assignment, f"Individual {user_id}", user_id, now)
    _place_member(db, assignment.id, team.id, user_id, now)
    return team


# ---------------------------------------------------------------- student actions


def create_team(db: Session, user: User, assignment_id: int, name: str, clock: Clock) -> dict:
    assignment = get_assignment(db, assignment_id)
    require_student(db, user, assignment.course_id)
    now = clock.now()
    if assignment.kind != "group":
        raise conflict("NOT_GROUP", "Individual assignments have no teams to create.")
    check_students_can_change(assignment, now)
    row = membership(db, assignment.id, user.id)
    if row is not None and row.status == "active":
        raise conflict("ALREADY_IN_TEAM", "You are already in a team for this assignment. Leave it first.")
    team = _new_team(db, assignment, name.strip(), user.id, now)
    _place_member(db, assignment.id, team.id, user.id, now)
    db.commit()
    return team_detail(db, team, user, now)


def rename_team(db: Session, user: User, team_id: int, name: str, clock: Clock) -> dict:
    team = get_team(db, team_id)
    require_active_member(db, team, user)
    team.name = name.strip()
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("TEAM_NAME_TAKEN", "Another team already uses this name.") from exc
    return team_detail(db, team, user, clock.now())


def leave_team(db: Session, user: User, team_id: int, clock: Clock) -> None:
    team = get_team(db, team_id)
    assignment = db.get(Assignment, team.assignment_id)
    row = require_active_member(db, team, user)
    now = clock.now()
    if assignment.kind != "group":
        raise conflict("NOT_GROUP", "You cannot leave an individual assignment.")
    check_students_can_change(assignment, now)
    if has_final(db, team.id):
        raise conflict("TEAM_HAS_FINAL", "Your team has submitted a final. Only the teacher can change the team now.")
    row.status = "left"
    row.left_at = now
    db.flush()
    _close_if_empty(db, team, now)
    notify(
        db,
        "team_member_left",
        active_member_ids(db, team.id),
        f"{user.name} left {team.name}",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    db.commit()


def join_from_invitation(db: Session, team_id: int, user: User, now: datetime) -> Team:
    """Called when a team invitation is accepted, inside its transaction.

    The team row is locked (SELECT ... FOR UPDATE), so two people accepting
    at the same moment are handled one at a time, and room is checked again.
    """
    team = db.scalar(select(Team).where(Team.id == team_id).with_for_update())
    assignment = db.get(Assignment, team.assignment_id)
    require_student(db, user, assignment.course_id)
    check_students_can_change(assignment, now)
    if team.closed_at is not None:
        raise conflict("TEAM_CLOSED", "This team no longer exists.")
    if has_final(db, team.id):
        raise conflict("TEAM_HAS_FINAL", "This team has already submitted a final.")
    row = membership(db, assignment.id, user.id)
    if row is not None and row.status == "active":
        raise conflict("ALREADY_IN_TEAM", "You are already in a team for this assignment. Leave it first.")
    if len(active_member_ids(db, team.id)) >= assignment.max_team:
        raise conflict("TEAM_FULL", "This team is full.")
    others = active_member_ids(db, team.id)
    _place_member(db, assignment.id, team.id, user.id, now)
    notify(
        db,
        "team_member_joined",
        others,
        f"{user.name} joined {team.name}",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    return team


# ---------------------------------------------------------------- teacher actions


def _teacher_change_allowed(db: Session, team: Team) -> None:
    if marks_released(db, team.id):
        raise conflict("MARKS_RELEASED", "Marks for this team are released; the team can no longer change.")


def teacher_remove(db: Session, user: User, team_id: int, member_id: int, clock: Clock) -> None:
    team = get_team(db, team_id)
    assignment = db.get(Assignment, team.assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    _teacher_change_allowed(db, team)
    row = membership(db, assignment.id, member_id)
    if row is None or row.team_id != team.id or row.status != "active":
        raise not_found("Team member")
    now = clock.now()
    row.status = "removed" if has_final(db, team.id) else "left"
    row.left_at = now
    db.flush()
    _close_if_empty(db, team, now)
    member = db.get(User, member_id)
    notify(
        db,
        "team_member_left",
        [*active_member_ids(db, team.id), member_id],
        f"The teacher removed {member.name} from {team.name}",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    audit(
        db,
        user,
        "team_member_removed",
        "teams",
        team.id,
        course_id=assignment.course_id,
        as_admin=access.as_admin,
        after={"user_id": member_id},
    )
    db.commit()


def teacher_move(db: Session, user: User, team_id: int, member_id: int, to_team_id: int, clock: Clock) -> dict:
    """Move a student to another team of the same assignment, any time before marks are released.

    Their drafts stay with the old team. The size limit still applies.
    """
    team = get_team(db, team_id)
    target = db.scalar(select(Team).where(Team.id == to_team_id).with_for_update())
    if target is None or target.assignment_id != team.assignment_id:
        raise not_found("Target team")
    if target.id == team.id:
        raise conflict("SAME_TEAM", "The student is already in this team.")
    assignment = db.get(Assignment, team.assignment_id)
    access = require_teacher(db, user, assignment.course_id)
    _teacher_change_allowed(db, team)
    _teacher_change_allowed(db, target)
    if target.closed_at is not None:
        raise conflict("TEAM_CLOSED", "The target team is closed.")
    row = membership(db, assignment.id, member_id)
    if row is None or row.team_id != team.id or row.status != "active":
        raise not_found("Team member")
    if len(active_member_ids(db, target.id)) >= assignment.max_team:
        raise conflict("TEAM_FULL", "The target team is full.")
    now = clock.now()
    _place_member(db, assignment.id, target.id, member_id, now)
    _close_if_empty(db, team, now)
    member = db.get(User, member_id)
    notify(
        db,
        "team_member_left",
        active_member_ids(db, team.id),
        f"{member.name} was moved to {target.name}",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    notify(
        db,
        "team_member_joined",
        active_member_ids(db, target.id),
        f"{member.name} was moved into {target.name}",
        f"/teams/{target.id}",
        now,
        course_id=assignment.course_id,
    )
    audit(
        db,
        user,
        "team_member_moved",
        "teams",
        target.id,
        course_id=assignment.course_id,
        as_admin=access.as_admin,
        before={"team_id": team.id},
        after={"team_id": target.id, "user_id": member_id},
    )
    db.commit()
    return team_detail(db, target, user, now)


# ---------------------------------------------------------------- course removal


def on_removed_from_course(db: Session, course_id: int, user_id: int, now: datetime) -> set[int]:
    """A student was removed from the course. Returns teammates to notify.

    Before the team's first final they leave as if they left themselves;
    after it, the final stands and they show as Removed.
    """
    rows = db.execute(
        select(TeamMember, Team)
        .join(Team, Team.id == TeamMember.team_id)
        .join(Assignment, Assignment.id == TeamMember.assignment_id)
        .where(Assignment.course_id == course_id, TeamMember.user_id == user_id, TeamMember.status == "active")
    ).all()
    mates: set[int] = set()
    for row, team in rows:
        if has_final(db, team.id):
            row.status = "removed"
        else:
            row.status = "left"
        row.left_at = now
        db.flush()
        _close_if_empty(db, team, now)
        mates.update(active_member_ids(db, team.id))
    return mates


def on_reinstated(db: Session, course_id: int, user_id: int) -> None:
    """Re-enrolled: places they lost by removal after a final come back."""
    rows = db.scalars(
        select(TeamMember)
        .join(Assignment, Assignment.id == TeamMember.assignment_id)
        .where(Assignment.course_id == course_id, TeamMember.user_id == user_id, TeamMember.status == "removed")
    ).all()
    for row in rows:
        row.status = "active"
        row.left_at = None


def require_team_access(db: Session, user: User, team_id: int) -> tuple[Team, Assignment, bool]:
    """For other modules: (team, assignment, is_teacher). Members and the course's teachers only."""
    team = get_team(db, team_id)
    assignment = db.get(Assignment, team.assignment_id)
    access = course_access(db, user, assignment.course_id)
    if access.is_teacher:
        return team, assignment, True
    require_active_member(db, team, user)
    if access.role != "student":
        raise forbidden("Only members of this course can see this.", "NOT_COURSE_MEMBER")
    return team, assignment, False
