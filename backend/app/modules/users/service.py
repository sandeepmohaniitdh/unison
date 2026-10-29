"""Profile, emails, data download and account deletion."""

from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, forbidden, not_found
from app.core.security import MIN_PASSWORD_LENGTH, hash_password, verify_password
from app.core.storage import LocalStorage
from app.core.time import Clock
from app.modules.users.models import User, UserEmail

GRACE_DAYS = 7
FORMER_MEMBER = "Former member"


def normalise_email(email: str) -> str:
    return email.strip().lower()


def find_user_by_email(db: Session, email: str) -> User | None:
    """The user who owns this address (primary or second, verified or not)."""
    return db.scalar(
        select(User).join(UserEmail, UserEmail.user_id == User.id).where(UserEmail.email == normalise_email(email))
    )


def verified_emails(db: Session, user_id: int) -> list[str]:
    return list(
        db.scalars(select(UserEmail.email).where(UserEmail.user_id == user_id, UserEmail.verified_at.is_not(None)))
    )


def all_emails(db: Session, user_id: int) -> list[str]:
    return list(db.scalars(select(UserEmail.email).where(UserEmail.user_id == user_id)))


def email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(UserEmail.id).where(UserEmail.email == normalise_email(email))) is not None


def check_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise bad_request("PASSWORD_TOO_SHORT", f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > 128:
        raise bad_request("PASSWORD_TOO_LONG", "Passwords can have at most 128 characters.")


def create_user(
    db: Session,
    *,
    name: str,
    email: str,
    role: str,
    now: datetime,
    password: str | None = None,
    verified: bool = False,
    must_change_password: bool = False,
) -> User:
    user = User(
        name=name.strip(),
        role=role,
        status="active",
        password_hash=hash_password(password) if password else None,
        must_change_password=must_change_password,
        consent_at=now,
        created_at=now,
    )
    db.add(user)
    db.flush()
    db.add(
        UserEmail(
            user_id=user.id,
            email=normalise_email(email),
            is_primary=True,
            verified_at=now if verified else None,
            created_at=now,
        )
    )
    db.flush()
    return user


# ---------------------------------------------------------------- profile


def me(db: Session, user: User) -> dict:
    from app.modules.auth.models import OAuthIdentity

    emails = db.scalars(select(UserEmail).where(UserEmail.user_id == user.id).order_by(UserEmail.id)).all()
    google = db.scalar(select(OAuthIdentity.id).where(OAuthIdentity.user_id == user.id)) is not None
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "emails": [email_item(e) for e in emails],
        "has_password": user.password_hash is not None,
        "google_linked": google,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
    }


def email_item(e: UserEmail) -> dict:
    return {"id": e.id, "email": e.email, "is_primary": e.is_primary, "verified": e.verified_at is not None}


def update_profile(db: Session, user: User, name: str) -> dict:
    user.name = name.strip()
    db.commit()
    return me(db, user)


def change_password(db: Session, user: User, current: str | None, new: str, clock: Clock, keep_session_id: int | None):
    """Set or change the password. Other sessions are logged out."""
    from app.modules.auth.service import revoke_all_sessions

    if user.password_hash is not None and not verify_password(current or "", user.password_hash):
        raise forbidden("The current password is wrong.", "WRONG_PASSWORD")
    check_password_strength(new)
    user.password_hash = hash_password(new)
    user.must_change_password = False
    revoke_all_sessions(db, user.id, clock.now(), except_session_id=keep_session_id)
    db.commit()


def add_email(db: Session, user: User, email: str, clock: Clock) -> dict:
    from app.modules.auth.service import send_verification

    email = normalise_email(email)
    if email_taken(db, email):
        raise conflict("EMAIL_TAKEN", "This email is already used by an account.")
    count = db.scalar(select(func.count()).where(UserEmail.user_id == user.id)) or 0
    if count >= 2:
        raise conflict("EMAIL_LIMIT", "An account can have a primary and one second email.")
    row = UserEmail(user_id=user.id, email=email, is_primary=False, created_at=clock.now())
    db.add(row)
    db.flush()
    send_verification(db, user, row, clock.now())
    db.commit()
    return email_item(row)


def _own_email(db: Session, user: User, email_id: int) -> UserEmail:
    row = db.get(UserEmail, email_id)
    if row is None or row.user_id != user.id:
        raise not_found("Email")
    return row


def remove_email(db: Session, user: User, email_id: int) -> None:
    from app.modules.auth.models import EmailToken

    row = _own_email(db, user, email_id)
    if row.is_primary:
        raise conflict("PRIMARY_EMAIL", "The primary email cannot be removed. Make another email primary first.")
    db.execute(delete(EmailToken).where(EmailToken.user_email_id == row.id))
    db.delete(row)
    db.commit()


def make_primary(db: Session, user: User, email_id: int) -> dict:
    row = _own_email(db, user, email_id)
    if row.verified_at is None:
        raise conflict("EMAIL_NOT_VERIFIED", "Verify this email before making it primary.")
    if not row.is_primary:
        # Two steps, so the unique index never sees two primary emails at once.
        db.execute(update(UserEmail).where(UserEmail.user_id == user.id).values(is_primary=False))
        db.flush()
        row.is_primary = True
        db.commit()
    return me(db, user)


def resend_verification(db: Session, user: User, email_id: int, clock: Clock) -> None:
    from app.modules.auth.service import send_verification

    row = _own_email(db, user, email_id)
    if row.verified_at is not None:
        raise conflict("ALREADY_VERIFIED", "This email is already verified.")
    send_verification(db, user, row, clock.now())
    db.commit()


def unlink_google(db: Session, user: User) -> None:
    from app.modules.auth.models import OAuthIdentity

    if user.password_hash is None:
        raise conflict("NO_PASSWORD", "Set a password before unlinking Google, or you could not log in.")
    db.execute(delete(OAuthIdentity).where(OAuthIdentity.user_id == user.id))
    db.commit()


# ---------------------------------------------------------------- data download


def export_data(db: Session, user: User) -> dict:
    """Everything Unison stores about this user, as JSON (DPDP Act)."""
    from app.modules.assignments.models import Assignment
    from app.modules.courses.models import Course, Enrollment
    from app.modules.notifications.models import Notification
    from app.modules.submissions.models import Submission, SubmissionFile, SubmissionVersion
    from app.modules.teams.models import Team, TeamMember

    def iso(dt):
        return dt.isoformat() if dt else None

    enrolments = db.execute(
        select(Enrollment, Course).join(Course, Course.id == Enrollment.course_id).where(Enrollment.user_id == user.id)
    ).all()
    teams = db.execute(
        select(TeamMember, Team, Assignment)
        .join(Team, Team.id == TeamMember.team_id)
        .join(Assignment, Assignment.id == TeamMember.assignment_id)
        .where(TeamMember.user_id == user.id)
    ).all()
    drafts = db.execute(
        select(SubmissionVersion, Team.name)
        .join(Submission, Submission.id == SubmissionVersion.submission_id)
        .join(Team, Team.id == Submission.team_id)
        .where(SubmissionVersion.uploaded_by == user.id)
    ).all()
    files_by_version: dict[int, list[str]] = {}
    for f in db.scalars(select(SubmissionFile).where(SubmissionFile.version_id.in_([v.id for v, _ in drafts] or [0]))):
        files_by_version.setdefault(f.version_id, []).append(f.file_name)
    notes = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id)).all()
    return {
        "profile": {
            "id": user.id,
            "name": user.name,
            "role": user.role,
            "created_at": iso(user.created_at),
            "consent_at": iso(user.consent_at),
        },
        "emails": all_emails(db, user.id),
        "courses": [
            {"course": f"{c.code} {c.title} ({c.term})", "role": e.role, "status": e.status} for e, c in enrolments
        ],
        "teams": [
            {"assignment": a.title, "team": t.name, "status": m.status, "joined_at": iso(m.joined_at)}
            for m, t, a in teams
        ],
        "drafts_uploaded": [
            {
                "team": team,
                "version": v.number,
                "files": files_by_version.get(v.id, []),
                "uploaded_at": iso(v.created_at),
            }
            for v, team in drafts
        ],
        "notifications": [{"title": n.title, "created_at": iso(n.created_at)} for n in notes],
    }


# ---------------------------------------------------------------- account deletion


def deletion_preview(db: Session, user: User) -> dict:
    from app.modules.courses.models import Course, Enrollment
    from app.modules.teams.models import TeamMember

    courses = db.scalar(
        select(func.count())
        .select_from(Enrollment)
        .join(Course, Course.id == Enrollment.course_id)
        .where(Enrollment.user_id == user.id, Enrollment.status == "active", Course.archived_at.is_(None))
    )
    teams = db.scalar(select(func.count()).where(TeamMember.user_id == user.id, TeamMember.status == "active"))
    return {
        "running_courses": courses or 0,
        "active_teams": teams or 0,
        "grace_days": GRACE_DAYS,
        "can_delete": not _is_last_admin(db, user),
    }


def _is_last_admin(db: Session, user: User) -> bool:
    if user.role != "admin":
        return False
    others = db.scalar(select(func.count()).where(User.role == "admin", User.status == "active", User.id != user.id))
    return (others or 0) == 0


def request_deletion(db: Session, user: User, password: str | None, session, clock: Clock) -> datetime:
    """Step 1: deactivate now, delete for good after 7 days unless they log in again."""
    from app.core.permissions import teacher_ids
    from app.modules.auth.service import revoke_all_sessions
    from app.modules.courses.models import Enrollment
    from app.modules.notifications.service import notify
    from app.modules.teams.models import TeamMember

    now = clock.now()
    if _is_last_admin(db, user):
        raise conflict("LAST_ADMIN", "The last administrator cannot delete their account.")
    if user.password_hash is not None:
        if not verify_password(password or "", user.password_hash):
            raise forbidden("The password is wrong.", "WRONG_PASSWORD")
    else:
        # Google-only accounts confirm by having signed in within the last 10 minutes.
        if session is None or session.created_at < now - timedelta(minutes=10):
            raise forbidden("Sign in with Google again, then delete within 10 minutes.", "REAUTH_REQUIRED")

    user.status = "deactivated"
    user.deletion_requested_at = now
    revoke_all_sessions(db, user.id, now)

    # Teammates and teachers are told.
    team_ids = list(
        db.scalars(select(TeamMember.team_id).where(TeamMember.user_id == user.id, TeamMember.status == "active"))
    )
    if team_ids:
        mates = set(
            db.scalars(
                select(TeamMember.user_id).where(
                    TeamMember.team_id.in_(team_ids), TeamMember.status == "active", TeamMember.user_id != user.id
                )
            )
        )
        notify(db, "account_deletion_requested", mates, f"{user.name} is deleting their account", "/dashboard", now)
    course_ids = list(
        db.scalars(select(Enrollment.course_id).where(Enrollment.user_id == user.id, Enrollment.status == "active"))
    )
    for course_id in course_ids:
        teachers = [t for t in teacher_ids(db, course_id) if t != user.id]
        notify(
            db,
            "account_deletion_requested",
            teachers,
            f"{user.name} is deleting their account",
            f"/courses/{course_id}/manage",
            now,
            course_id=course_id,
        )
    db.commit()
    return now + timedelta(days=GRACE_DAYS)


def cancel_deletion_on_login(user: User) -> bool:
    """Logging in during the grace period cancels the deletion."""
    if user.status == "deactivated" and user.deletion_requested_at is not None:
        user.status = "active"
        user.deletion_requested_at = None
        return True
    return False


def finalise_deletions(db: Session, storage: LocalStorage, clock: Clock) -> int:
    """Worker job. After 7 days the account is anonymised and its private data deleted.

    Kept: the users row (as "Former member", so group drafts and finals still
    show who uploaded them as Former member). Deleted: name, emails, password,
    Google link, sessions, notifications, preferences, individual-assignment
    work and the user's own marks.
    """
    now = clock.now()
    due = db.scalars(
        select(User).where(
            User.status == "deactivated",
            User.deletion_requested_at.is_not(None),
            User.deletion_requested_at <= now - timedelta(days=GRACE_DAYS),
        )
    ).all()
    for user in due:
        _anonymise(db, user, storage, now)
        db.commit()
    return len(due)


def _anonymise(db: Session, user: User, storage: LocalStorage, now: datetime) -> None:
    from app.modules.ai.models import AiFeedback
    from app.modules.assignments.models import Assignment
    from app.modules.auth.models import EmailToken, OAuthIdentity, UserSession
    from app.modules.courses.models import Enrollment
    from app.modules.invitations.models import Invitation
    from app.modules.notifications.models import EmailOutbox, Notification, NotificationPreference
    from app.modules.reviews.models import MemberAdjustment, Review
    from app.modules.submissions.models import FinalSubmission, Submission, SubmissionFile, SubmissionVersion
    from app.modules.teams.models import Team, TeamMember

    emails = all_emails(db, user.id)

    # Pending invitations to or from this person are cancelled.
    db.execute(
        update(Invitation)
        .where(
            Invitation.status == "pending", or_(Invitation.email.in_(emails or [""]), Invitation.invited_by == user.id)
        )
        .values(status="cancelled", responded_at=now)
    )

    # Individual-assignment work is deleted, with its files and marks.
    individual_teams = list(
        db.scalars(
            select(Team.id)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .join(Assignment, Assignment.id == Team.assignment_id)
            .where(TeamMember.user_id == user.id, Assignment.kind == "individual")
        )
    )
    for team_id in individual_teams:
        submission = db.scalar(select(Submission).where(Submission.team_id == team_id))
        if submission is not None:
            version_ids = list(
                db.scalars(select(SubmissionVersion.id).where(SubmissionVersion.submission_id == submission.id))
            )
            final_ids = list(
                db.scalars(select(FinalSubmission.id).where(FinalSubmission.version_id.in_(version_ids or [0])))
            )
            submission.current_final_id = None
            db.flush()
            db.execute(delete(AiFeedback).where(AiFeedback.final_id.in_(final_ids or [0])))
            db.execute(delete(Review).where(Review.final_id.in_(final_ids or [0])))
            db.execute(delete(FinalSubmission).where(FinalSubmission.id.in_(final_ids or [0])))
            for key in db.scalars(
                select(SubmissionFile.storage_key).where(SubmissionFile.version_id.in_(version_ids or [0]))
            ):
                storage.delete(key)
            db.execute(delete(SubmissionFile).where(SubmissionFile.version_id.in_(version_ids or [0])))
            db.execute(delete(SubmissionVersion).where(SubmissionVersion.id.in_(version_ids or [0])))
            db.delete(submission)
            db.flush()
        db.execute(delete(TeamMember).where(TeamMember.team_id == team_id))
        db.execute(delete(Invitation).where(Invitation.team_id == team_id))
        db.execute(delete(Team).where(Team.id == team_id))

    # Their own marks in group work: the adjustment rows about them.
    db.execute(delete(MemberAdjustment).where(MemberAdjustment.user_id == user.id))

    # Removed from every course and team; group uploads stay, as "Former member".
    db.execute(
        update(Enrollment)
        .where(Enrollment.user_id == user.id, Enrollment.status.in_(["active", "requested"]))
        .values(status="left", decided_at=now)
    )
    db.execute(update(TeamMember).where(TeamMember.user_id == user.id).values(status="former", left_at=now))

    db.execute(delete(Notification).where(Notification.user_id == user.id))
    db.execute(delete(NotificationPreference).where(NotificationPreference.user_id == user.id))
    db.execute(delete(EmailOutbox).where(EmailOutbox.user_id == user.id, EmailOutbox.status == "pending"))
    db.execute(update(EmailOutbox).where(EmailOutbox.user_id == user.id).values(user_id=None, to_email="deleted"))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
    db.execute(delete(OAuthIdentity).where(OAuthIdentity.user_id == user.id))
    db.execute(delete(UserEmail).where(UserEmail.user_id == user.id))

    user.name = FORMER_MEMBER
    user.password_hash = None
    user.status = "deleted"
    user.deleted_at = now
