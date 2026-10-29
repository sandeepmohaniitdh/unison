"""Course, team and staff invitations.

A link carries a random token (only its hash is stored), works once, for 7
days, and only for an account that has the invited address as a verified
email. Team invitations reserve places: members + pending invitations can
never exceed the team size.
"""

from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.pagination import PageParams, paginate
from app.core.permissions import course_access, get_course, require_teacher
from app.core.security import hash_token, new_token
from app.core.time import Clock, ist_text
from app.modules.admin.service import audit
from app.modules.assignments.models import Assignment
from app.modules.courses.models import Course, Enrollment
from app.modules.invitations.models import Invitation
from app.modules.notifications.service import notify, queue_email
from app.modules.teams.models import Team, TeamMember
from app.modules.users import service as users
from app.modules.users.models import User

VALID_DAYS = 7


def item(db: Session, inv: Invitation) -> dict:
    inviter = db.get(User, inv.invited_by)
    return {
        "id": inv.id,
        "kind": inv.kind,
        "email": inv.email,
        "role": inv.role,
        "status": inv.status,
        "course_id": inv.course_id,
        "team_id": inv.team_id,
        "invited_by": {"id": inviter.id, "name": inviter.name},
        "expires_at": inv.expires_at,
        "created_at": inv.created_at,
    }


def _create(
    db: Session,
    *,
    kind: str,
    email: str,
    role: str,
    inviter: User,
    now: datetime,
    subject: str,
    text: str,
    course_id: int | None = None,
    team_id: int | None = None,
) -> Invitation:
    raw, token_hash = new_token()
    inv = Invitation(
        kind=kind,
        email=email,
        role=role,
        course_id=course_id,
        team_id=team_id,
        invited_by=inviter.id,
        token_hash=token_hash,
        status="pending",
        expires_at=now + timedelta(days=VALID_DAYS),
        created_at=now,
    )
    db.add(inv)
    db.flush()
    invitee = users.find_user_by_email(db, email)
    queue_email(
        db,
        to=email,
        user_id=invitee.id if invitee else None,
        template="invitation",
        payload={"subject": subject, "text": text, "token": raw, "email": email, "expires": ist_text(inv.expires_at)},
        dedup_key=f"invitation:{inv.id}",
        now=now,
    )
    if invitee is not None:
        notify(db, f"{kind}_invitation", [invitee.id], subject, f"/invitations?id={inv.id}", now, course_id=course_id)
    return inv


# ---------------------------------------------------------------- sending


def invite_to_course(db: Session, user: User, course_id: int, emails: list[str], role: str, clock: Clock) -> dict:
    access = require_teacher(db, user, course_id)
    course = access.course
    now = clock.now()
    created, skipped = [], []
    for raw_email in dict.fromkeys(users.normalise_email(e) for e in emails):
        existing = users.find_user_by_email(db, raw_email)
        if existing is not None:
            member = db.scalar(
                select(Enrollment).where(
                    Enrollment.course_id == course_id, Enrollment.user_id == existing.id, Enrollment.status == "active"
                )
            )
            if member is not None:
                skipped.append({"email": raw_email, "reason": "already a member"})
                continue
            if role == "teacher" and existing.role == "student":
                skipped.append({"email": raw_email, "reason": "not a teacher account"})
                continue
        pending = db.scalar(
            select(Invitation.id).where(
                Invitation.course_id == course_id,
                Invitation.email == raw_email,
                Invitation.status == "pending",
                Invitation.kind == "course",
            )
        )
        if pending:
            skipped.append({"email": raw_email, "reason": "already invited"})
            continue
        what = "as a co-teacher" if role == "teacher" else "as a student"
        inv = _create(
            db,
            kind="course",
            email=raw_email,
            role=role,
            inviter=user,
            now=now,
            course_id=course_id,
            subject=f"Invitation to {course.code} {course.title}",
            text=f"{user.name} invited you to join {course.code} {course.title} ({course.term}) {what} on Unison.",
        )
        created.append(inv)
    if access.as_admin and created:
        audit(
            db,
            user,
            "course_invitations_sent",
            "courses",
            course_id,
            course_id=course_id,
            as_admin=True,
            after={"emails": [i.email for i in created], "role": role},
        )
    db.commit()
    return {"created": [item(db, i) for i in created], "skipped": skipped}


def invite_to_team(db: Session, user: User, team_id: int, email: str, clock: Clock) -> dict:
    from app.modules.teams.service import (
        active_member_ids,
        check_students_can_change,
        get_team,
        has_final,
        pending_invitation_count,
        require_active_member,
    )

    team = get_team(db, team_id)
    require_active_member(db, team, user)
    assignment = db.get(Assignment, team.assignment_id)
    now = clock.now()
    if assignment.kind != "group":
        raise conflict("NOT_GROUP", "Individual assignments have no teams.")
    check_students_can_change(assignment, now)
    if has_final(db, team.id):
        raise conflict("TEAM_HAS_FINAL", "Your team has submitted a final, so it cannot take new members.")
    email = users.normalise_email(email)
    invitee = users.find_user_by_email(db, email)
    if invitee is None or course_access(db, invitee, assignment.course_id).role != "student":
        raise bad_request("NOT_ENROLLED", "Only students enrolled in this course can be invited.")
    if invitee.id == user.id:
        raise bad_request("CANNOT_INVITE_SELF", "You are already in this team.")
    their_row = db.get(TeamMember, (assignment.id, invitee.id))
    if their_row is not None and their_row.status == "active":
        raise conflict("ALREADY_IN_TEAM", "This student is already in a team for this assignment.")
    already = db.scalar(
        select(Invitation.id).where(
            Invitation.team_id == team.id, Invitation.email == email, Invitation.status == "pending"
        )
    )
    if already:
        raise conflict("ALREADY_INVITED", "This student already has a pending invitation to your team.")
    # Lock the team row so two members inviting at once cannot overfill it.
    db.scalar(select(Team).where(Team.id == team.id).with_for_update())
    used = len(active_member_ids(db, team.id)) + pending_invitation_count(db, team.id)
    if used >= assignment.max_team:
        raise conflict(
            "TEAM_FULL",
            "Members and pending invitations already fill the team. Cancel an invitation first.",
            {"max_team": assignment.max_team, "members_and_pending": used},
        )
    course = db.get(Course, assignment.course_id)
    inv = _create(
        db,
        kind="team",
        email=email,
        role="student",
        inviter=user,
        now=now,
        course_id=course.id,
        team_id=team.id,
        subject=f"{user.name} invited you to team {team.name}",
        text=f"{user.name} invited you to team {team.name} for {assignment.title} in {course.code}. "
        f"Deadline: {ist_text(assignment.due_at)}.",
    )
    db.commit()
    return item(db, inv)


def invite_staff(db: Session, admin: User, email: str, role: str, clock: Clock) -> dict:
    now = clock.now()
    email = users.normalise_email(email)
    existing = users.find_user_by_email(db, email)
    if existing is not None and (existing.role == role or existing.role == "admin"):
        raise conflict("ALREADY_STAFF", "This person already has this role or a higher one.")
    pending = db.scalar(
        select(Invitation.id).where(
            Invitation.kind == "staff", Invitation.email == email, Invitation.status == "pending"
        )
    )
    if pending:
        raise conflict("ALREADY_INVITED", "This email already has a pending staff invitation.")
    inv = _create(
        db,
        kind="staff",
        email=email,
        role=role,
        inviter=admin,
        now=now,
        subject=f"Invitation to join Unison as {role}",
        text=f"{admin.name} invited you to join Unison as {'an administrator' if role == 'admin' else 'a teacher'}.",
    )
    audit(db, admin, "staff_invited", "invitations", inv.id, after={"email": email, "role": role})
    db.commit()
    return item(db, inv)


# ---------------------------------------------------------------- listing and cancelling


def list_course_invitations(db: Session, user: User, course_id: int, params: PageParams, status: str | None) -> dict:
    require_teacher(db, user, course_id, writable=False)
    stmt = select(Invitation).where(Invitation.course_id == course_id, Invitation.kind == "course")
    if status:
        stmt = stmt.where(Invitation.status == status)
    stmt = stmt.order_by(Invitation.created_at.desc(), Invitation.id.desc())
    return paginate(db, stmt, params, lambda i: item(db, i))


def list_staff_invitations(db: Session, params: PageParams, status: str | None) -> dict:
    stmt = select(Invitation).where(Invitation.kind == "staff")
    if status:
        stmt = stmt.where(Invitation.status == status)
    stmt = stmt.order_by(Invitation.created_at.desc(), Invitation.id.desc())
    return paginate(db, stmt, params, lambda i: item(db, i))


def list_team_invitations(db: Session, user: User, team_id: int) -> list[dict]:
    from app.modules.teams.service import get_team, require_active_member

    team = get_team(db, team_id)
    require_active_member(db, team, user)
    rows = db.scalars(
        select(Invitation).where(Invitation.team_id == team_id).order_by(Invitation.created_at.desc())
    ).all()
    return [item(db, i) for i in rows]


def cancel(db: Session, user: User, invitation_id: int, clock: Clock) -> None:
    from app.modules.teams.service import get_team, require_active_member

    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise not_found("Invitation")
    if inv.kind == "course":
        access = require_teacher(db, user, inv.course_id)
        if access.as_admin:
            audit(db, user, "invitation_cancelled", "invitations", inv.id, course_id=inv.course_id, as_admin=True)
    elif inv.kind == "team":
        require_active_member(db, get_team(db, inv.team_id), user)
    else:
        if user.role != "admin":
            raise forbidden("Only administrators can cancel staff invitations.", "ADMIN_ONLY")
        audit(db, user, "invitation_cancelled", "invitations", inv.id)
    if inv.status != "pending":
        raise conflict("NOT_PENDING", "Only pending invitations can be cancelled.")
    inv.status = "cancelled"
    inv.responded_at = clock.now()
    db.commit()


def cancel_for_member(db: Session, course_id: int, user_id: int, now: datetime) -> None:
    """A student left the course: cancel their course invitations, and team
    invitations in the course that they sent or received."""
    emails = users.all_emails(db, user_id) or [""]
    db.execute(
        update(Invitation)
        .where(
            Invitation.course_id == course_id,
            Invitation.status == "pending",
            or_(Invitation.email.in_(emails), Invitation.invited_by == user_id),
        )
        .values(status="cancelled", responded_at=now)
    )


# ---------------------------------------------------------------- the invitee's side


def _by_token(db: Session, token: str) -> Invitation:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if inv is None:
        raise not_found("Invitation")
    return inv


def _by_id_for_user(db: Session, user: User, invitation_id: int) -> Invitation:
    inv = db.get(Invitation, invitation_id)
    if inv is None or inv.email not in users.all_emails(db, user.id):
        raise not_found("Invitation")
    return inv


def _expire_if_due(inv: Invitation, now: datetime) -> None:
    if inv.status == "pending" and inv.expires_at <= now:
        inv.status = "expired"


def _problem(db: Session, inv: Invitation, user: User | None) -> str | None:
    if inv.status == "expired":
        return "expired"
    if inv.status == "accepted":
        return "used"
    if inv.status in ("cancelled", "declined"):
        return inv.status
    if user is None:
        return "log_in"
    if inv.email not in users.all_emails(db, user.id):
        return "wrong_account"
    if inv.email not in users.verified_emails(db, user.id):
        return "email_not_verified"
    return None


def view(db: Session, inv: Invitation, user: User | None, now: datetime) -> dict:
    _expire_if_due(inv, now)
    inviter = db.get(User, inv.invited_by)
    course = db.get(Course, inv.course_id) if inv.course_id else None
    team_ref = None
    if inv.team_id:
        team = db.get(Team, inv.team_id)
        assignment = db.get(Assignment, team.assignment_id)
        names = db.scalars(
            select(User.name)
            .join(TeamMember, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team.id, TeamMember.status == "active")
        ).all()
        team_ref = {
            "id": team.id,
            "name": team.name,
            "assignment_id": assignment.id,
            "assignment_title": assignment.title,
            "due_at": assignment.due_at,
            "members": list(names),
        }
    problem = _problem(db, inv, user)
    return {
        "id": inv.id,
        "kind": inv.kind,
        "role": inv.role,
        "status": inv.status,
        "email": inv.email,
        "invited_by": {"id": inviter.id, "name": inviter.name},
        "course": {"id": course.id, "code": course.code, "title": course.title, "term": course.term}
        if course
        else None,
        "team": team_ref,
        "expires_at": inv.expires_at,
        "can_accept": problem is None,
        "problem": problem,
    }


def view_by_token(db: Session, token: str, user: User | None, clock: Clock) -> dict:
    inv = _by_token(db, token)
    out = view(db, inv, user, clock.now())
    db.commit()
    return out


def my_invitations(db: Session, user: User, clock: Clock) -> list[dict]:
    now = clock.now()
    emails = users.verified_emails(db, user.id) or [""]
    rows = db.scalars(
        select(Invitation)
        .where(Invitation.email.in_(emails), Invitation.status == "pending", Invitation.expires_at > now)
        .order_by(Invitation.expires_at)
    ).all()
    return [view(db, inv, user, now) for inv in rows]


def accept(
    db: Session, user: User, clock: Clock, *, token: str | None = None, invitation_id: int | None = None
) -> dict:
    from app.modules.courses.service import enrol_student
    from app.modules.teams.service import join_from_invitation

    now = clock.now()
    inv = _by_token(db, token) if token else _by_id_for_user(db, user, invitation_id)
    _expire_if_due(inv, now)
    problem = _problem(db, inv, user)
    if problem in ("expired", "used", "cancelled", "declined"):
        db.commit()
        raise conflict("INVITATION_NOT_PENDING", f"This invitation is {inv.status}.")
    if problem == "wrong_account":
        raise forbidden(
            f"This invitation is for {inv.email}. Log in with that account, or add and verify that email.",
            "WRONG_ACCOUNT",
        )
    if problem == "email_not_verified":
        raise forbidden(f"Verify {inv.email} on your profile first.", "EMAIL_NOT_VERIFIED")

    result = {
        "status": "accepted",
        "kind": inv.kind,
        "course_id": inv.course_id,
        "team_id": inv.team_id,
        "role": inv.role,
    }
    if inv.kind == "course":
        course = get_course(db, inv.course_id)
        if course.archived_at is not None:
            raise conflict("COURSE_ARCHIVED", "This course is archived.")
        if inv.role == "teacher":
            if user.role == "student":
                raise forbidden("Only teacher accounts can join as a co-teacher. Ask an admin.", "NOT_A_TEACHER")
            row = db.scalar(select(Enrollment).where(Enrollment.course_id == course.id, Enrollment.user_id == user.id))
            if row is None:
                db.add(
                    Enrollment(
                        course_id=course.id,
                        user_id=user.id,
                        role="teacher",
                        status="active",
                        decided_by=inv.invited_by,
                        decided_at=now,
                        created_at=now,
                    )
                )
            else:
                row.role, row.status, row.decided_at = "teacher", "active", now
        else:
            enrol_student(db, course.id, user.id, now)
    elif inv.kind == "team":
        team = join_from_invitation(db, inv.team_id, user, now)
        # One team per assignment: decline the student's other invitations for it.
        emails = users.all_emails(db, user.id)
        other_teams = select(Team.id).where(Team.assignment_id == team.assignment_id, Team.id != team.id)
        db.execute(
            update(Invitation)
            .where(Invitation.team_id.in_(other_teams), Invitation.email.in_(emails), Invitation.status == "pending")
            .values(status="declined", responded_at=now)
        )
    else:
        before = user.role
        if user.role == "student" or inv.role == "admin":
            user.role = inv.role
        inviter = db.get(User, inv.invited_by)
        audit(
            db,
            inviter,
            "role_changed",
            "users",
            user.id,
            before={"role": before},
            after={"role": user.role, "via": "staff_invitation"},
        )
    inv.status = "accepted"
    inv.accepted_user_id = user.id
    inv.responded_at = now
    db.commit()
    return result


def decline(
    db: Session, user: User, clock: Clock, *, token: str | None = None, invitation_id: int | None = None
) -> dict:
    inv = _by_token(db, token) if token else _by_id_for_user(db, user, invitation_id)
    _expire_if_due(inv, clock.now())
    if inv.email not in users.all_emails(db, user.id):
        raise forbidden(f"This invitation is for {inv.email}.", "WRONG_ACCOUNT")
    if inv.status != "pending":
        db.commit()
        raise conflict("INVITATION_NOT_PENDING", f"This invitation is {inv.status}.")
    inv.status = "declined"
    inv.responded_at = clock.now()
    db.commit()
    return {
        "status": "declined",
        "kind": inv.kind,
        "course_id": inv.course_id,
        "team_id": inv.team_id,
        "role": inv.role,
    }


def respond(
    db: Session, user: User, clock: Clock, status: str, *, token: str | None = None, invitation_id: int | None = None
) -> dict:
    """The invitee accepts or declines (PATCH with {"status": "accepted"} or {"status": "declined"})."""
    if status == "accepted":
        return accept(db, user, clock, token=token, invitation_id=invitation_id)
    return decline(db, user, clock, token=token, invitation_id=invitation_id)


def invitation_for_signup(db: Session, token: str, email: str, now: datetime) -> Invitation:
    """Signing up from a link: the invitation must be pending and for this email."""
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if inv is None or inv.status != "pending" or inv.expires_at <= now or inv.email != email:
        raise bad_request("INVALID_INVITATION", "This invitation link is not valid for this email.")
    return inv


# ---------------------------------------------------------------- worker job


def expire_invitations(db: Session, clock: Clock) -> int:
    result = db.execute(
        update(Invitation)
        .where(Invitation.status == "pending", Invitation.expires_at <= clock.now())
        .values(status="expired")
    )
    db.commit()
    return result.rowcount or 0
