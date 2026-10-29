"""Team drafts, the team's final, and the deadline rule.

- Drafts: any active member uploads up to max_files PDF or ZIP files of
  10 MB each. Only the team sees drafts.
- Final: any active member submits one draft as the final, while the team
  is at or above its minimum size. The request names the final the member
  last saw (expected_final_id); if it changed, 409 FINAL_CHANGED. An
  Idempotency-Key makes a repeated click return the first result.
- The teacher sees only the current final.
- At the deadline: the latest draft becomes the final if there is none
  ("submitted at deadline"), even below minimum size (flagged). No drafts
  means "not submitted". No late work.
- The deadline is applied by the worker every 30 seconds, and also whenever
  a submission is read, so it holds even if the worker is down.
"""

import uuid
from datetime import datetime

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, not_found, unprocessable
from app.core.permissions import teacher_ids
from app.core.storage import MB, PDF, SUBMISSION_EXTENSIONS, LocalStorage
from app.core.time import Clock
from app.modules.assignments.models import Assignment
from app.modules.notifications.service import notify
from app.modules.submissions.models import FinalSubmission, Submission, SubmissionFile, SubmissionVersion
from app.modules.submissions.schemas import FinalOut
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User

MAX_FILE_BYTES = 10 * MB


def check_idempotency_key(key: str) -> str:
    try:
        return str(uuid.UUID(key))
    except ValueError as exc:
        raise bad_request("IDEMPOTENCY_KEY_INVALID", "The Idempotency-Key header must be a UUID.") from exc


def submission_for_team(db: Session, team_id: int) -> Submission:
    sub = db.scalar(select(Submission).where(Submission.team_id == team_id))
    if sub is None:
        raise not_found("Submission")
    return sub


# ---------------------------------------------------------------- the deadline


def apply_deadline(db: Session, assignment: Assignment, now: datetime) -> bool:
    """Close an assignment whose deadline has passed. Safe to call any number of times."""
    if assignment.status != "published" or assignment.due_at > now:
        return False
    locked = db.scalar(select(Assignment).where(Assignment.id == assignment.id).with_for_update())
    if locked.status != "published":
        db.commit()
        return False
    teachers = teacher_ids(db, assignment.course_id)
    rows = db.execute(
        select(Submission, Team)
        .join(Team, Team.id == Submission.team_id)
        .where(Team.assignment_id == assignment.id, Submission.closed_at.is_(None))
    ).all()
    for sub, team in rows:
        if sub.current_final_id is None:
            latest = db.scalar(
                select(SubmissionVersion)
                .where(SubmissionVersion.submission_id == sub.id)
                .order_by(SubmissionVersion.number.desc())
                .limit(1)
            )
            if latest is not None:
                members = _active_ids(db, team.id)
                final = FinalSubmission(
                    version_id=latest.id,
                    submitted_by=None,
                    kind="at_deadline",
                    below_min_size=len(members) < assignment.min_team,
                    idempotency_key=None,
                    submitted_at=assignment.due_at,
                )
                db.add(final)
                db.flush()
                sub.current_final_id = final.id
                notify(
                    db,
                    "final_at_deadline",
                    [*members, *teachers],
                    f"{team.name}: v{latest.number} was submitted at the deadline for {assignment.title}",
                    f"/teams/{team.id}",
                    now,
                    course_id=assignment.course_id,
                )
        sub.closed_at = now
    locked.status = "closed"
    db.commit()
    return True


def apply_deadlines_for_course(db: Session, course_id: int, now: datetime) -> None:
    due = db.scalars(
        select(Assignment).where(
            Assignment.course_id == course_id, Assignment.status == "published", Assignment.due_at <= now
        )
    ).all()
    for assignment in due:
        apply_deadline(db, assignment, now)


def apply_due_deadlines(db: Session, clock: Clock) -> int:
    """Worker job."""
    now = clock.now()
    due = db.scalars(select(Assignment).where(Assignment.status == "published", Assignment.due_at <= now)).all()
    return sum(1 for a in due if apply_deadline(db, a, now))


# ---------------------------------------------------------------- state


def _active_ids(db: Session, team_id: int) -> list[int]:
    return list(
        db.scalars(select(TeamMember.user_id).where(TeamMember.team_id == team_id, TeamMember.status == "active"))
    )


def team_state(db: Session, team: Team, assignment: Assignment, now: datetime) -> str:
    from app.modules.reviews.models import Review

    sub = db.scalar(select(Submission).where(Submission.team_id == team.id))
    if sub is None:
        return "no_work"
    if sub.current_final_id is not None:
        review = db.scalar(select(Review).where(Review.final_id == sub.current_final_id))
        if review is not None and review.status == "released":
            return "marks_released"
        final = db.get(FinalSubmission, sub.current_final_id)
        return "submitted_at_deadline" if final.kind == "at_deadline" else "final_submitted"
    has_drafts = db.scalar(select(func.count()).where(SubmissionVersion.submission_id == sub.id)) or 0
    if sub.closed_at is not None or assignment.due_at <= now:
        return "not_submitted"
    return "drafts" if has_drafts else "no_work"


def my_team_state(db: Session, assignment: Assignment, user_id: int, now: datetime) -> dict:
    row = db.get(TeamMember, (assignment.id, user_id))
    if row is None or row.status != "active":
        if assignment.kind == "individual":
            return {"team_id": None, "state": "not_submitted" if assignment.due_at <= now else "no_work"}
        return {"team_id": None, "state": "no_team"}
    team = db.get(Team, row.team_id)
    return {"team_id": team.id, "state": team_state(db, team, assignment, now)}


# ---------------------------------------------------------------- views


def _files(db: Session, version_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {vid: [] for vid in version_ids}
    if not version_ids:
        return out
    for f in db.scalars(
        select(SubmissionFile).where(SubmissionFile.version_id.in_(version_ids)).order_by(SubmissionFile.id)
    ):
        out[f.version_id].append(
            {"id": f.id, "file_name": f.file_name, "mime_type": f.mime_type, "size_bytes": f.size_bytes}
        )
    return out


def _brief(db: Session, user_id: int | None) -> dict | None:
    if user_id is None:
        return None
    u = db.get(User, user_id)
    return {"id": u.id, "name": u.name}


def final_item(db: Session, final: FinalSubmission) -> dict:
    version = db.get(SubmissionVersion, final.version_id)
    return {
        "id": final.id,
        "version_id": version.id,
        "version_number": version.number,
        "submitted_by": _brief(db, final.submitted_by),
        "kind": final.kind,
        "below_min_size": final.below_min_size,
        "submitted_at": final.submitted_at,
        "replaced_at": final.replaced_at,
        "files": _files(db, [version.id])[version.id],
    }


def _access(db: Session, user: User, team_id: int) -> tuple[Team, Assignment, bool]:
    from app.modules.teams.service import require_team_access

    return require_team_access(db, user, team_id)


def submission_view(db: Session, user: User, team_id: int, clock: Clock) -> dict:
    team, assignment, is_teacher = _access(db, user, team_id)
    now = clock.now()
    apply_deadline(db, assignment, now)
    sub = submission_for_team(db, team.id)
    finals = (
        db.scalar(
            select(func.count())
            .select_from(FinalSubmission)
            .join(SubmissionVersion, SubmissionVersion.id == FinalSubmission.version_id)
            .where(SubmissionVersion.submission_id == sub.id)
        )
        or 0
    )
    drafts = db.scalar(select(func.count()).where(SubmissionVersion.submission_id == sub.id)) or 0
    current = db.get(FinalSubmission, sub.current_final_id) if sub.current_final_id else None
    return {
        "team_id": team.id,
        "assignment_id": assignment.id,
        "state": team_state(db, team, assignment, now),
        "due_at": assignment.due_at,
        "closed_at": sub.closed_at,
        "current_final": final_item(db, current) if current else None,
        "replaced_finals": max(0, finals - 1),
        "drafts_count": None if is_teacher and not _is_member(db, team, user) else drafts,
    }


def _is_member(db: Session, team: Team, user: User) -> bool:
    row = db.get(TeamMember, (team.assignment_id, user.id))
    return row is not None and row.team_id == team.id and row.status == "active"


def _require_member(db: Session, user: User, team_id: int) -> tuple[Team, Assignment]:
    """Drafts are for the team only: teachers get 404 as well."""
    from app.modules.teams.service import get_team, require_active_member

    team = get_team(db, team_id)
    require_active_member(db, team, user)
    return team, db.get(Assignment, team.assignment_id)


def draft_item(db: Session, v: SubmissionVersion, files: list[dict], current_version_id: int | None) -> dict:
    return {
        "id": v.id,
        "number": v.number,
        "uploaded_by": _brief(db, v.uploaded_by),
        "created_at": v.created_at,
        "files": files,
        "is_current_final": v.id == current_version_id,
    }


def list_drafts(db: Session, user: User, team_id: int) -> list[dict]:
    team, _assignment = _require_member(db, user, team_id)
    sub = submission_for_team(db, team.id)
    versions = db.scalars(
        select(SubmissionVersion)
        .where(SubmissionVersion.submission_id == sub.id)
        .order_by(SubmissionVersion.number.desc())
    ).all()
    files = _files(db, [v.id for v in versions])
    current_version = db.get(FinalSubmission, sub.current_final_id).version_id if sub.current_final_id else None
    return [draft_item(db, v, files[v.id], current_version) for v in versions]


def list_finals(db: Session, user: User, team_id: int) -> list[dict]:
    team, _assignment = _require_member(db, user, team_id)
    sub = submission_for_team(db, team.id)
    finals = db.scalars(
        select(FinalSubmission)
        .join(SubmissionVersion, SubmissionVersion.id == FinalSubmission.version_id)
        .where(SubmissionVersion.submission_id == sub.id)
        .order_by(FinalSubmission.submitted_at.desc(), FinalSubmission.id.desc())
    ).all()
    return [final_item(db, f) for f in finals]


# ---------------------------------------------------------------- drafts


def _check_open(assignment: Assignment, sub: Submission, team: Team, now: datetime) -> None:
    if assignment.status != "published" or sub.closed_at is not None or assignment.due_at <= now:
        raise conflict("DEADLINE_PASSED", "The deadline has passed. No late submissions.")
    if team.closed_at is not None:
        raise conflict("TEAM_CLOSED", "This team is closed.")


def upload_draft(
    db: Session,
    user: User,
    team_id: int,
    uploads: list[UploadFile],
    key: str,
    storage: LocalStorage,
    clock: Clock,
) -> dict:
    key = check_idempotency_key(key)
    team, assignment = _require_member(db, user, team_id)
    now = clock.now()
    apply_deadline(db, assignment, now)
    sub = db.scalar(select(Submission).where(Submission.team_id == team.id).with_for_update())
    existing = db.scalar(
        select(SubmissionVersion).where(
            SubmissionVersion.uploaded_by == user.id, SubmissionVersion.idempotency_key == key
        )
    )
    if existing is not None:
        db.commit()
        return _draft_out(db, sub, existing)
    _check_open(assignment, sub, team, now)
    if not uploads:
        raise unprocessable("NO_FILES", "Choose at least one file.")
    if len(uploads) > assignment.max_files:
        raise unprocessable("TOO_MANY_FILES", f"A draft can have at most {assignment.max_files} files.")

    stored = []
    try:
        for upload in uploads:
            stored.append(storage.save(upload.file, upload.filename, SUBMISSION_EXTENSIONS, MAX_FILE_BYTES))
    except Exception:
        for s in stored:
            storage.delete(s.key)
        raise
    number = (
        db.scalar(select(func.max(SubmissionVersion.number)).where(SubmissionVersion.submission_id == sub.id)) or 0
    ) + 1
    version = SubmissionVersion(
        submission_id=sub.id, number=number, uploaded_by=user.id, idempotency_key=key, created_at=now
    )
    db.add(version)
    db.flush()
    for s in stored:
        db.add(
            SubmissionFile(
                version_id=version.id,
                file_name=s.file_name,
                storage_key=s.key,
                mime_type=s.mime_type,
                size_bytes=s.size_bytes,
                sha256=s.sha256,
            )
        )
    others = [m for m in _active_ids(db, team.id) if m != user.id]
    notify(
        db,
        "draft_uploaded",
        others,
        f"{user.name} uploaded draft v{number} in {team.name}",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    db.commit()
    return _draft_out(db, sub, version)


def _draft_out(db: Session, sub: Submission, version: SubmissionVersion) -> dict:
    current_version = db.get(FinalSubmission, sub.current_final_id).version_id if sub.current_final_id else None
    return draft_item(db, version, _files(db, [version.id])[version.id], current_version)


# ---------------------------------------------------------------- the final


def submit_final(
    db: Session, user: User, team_id: int, version_id: int, expected_final_id: int | None, key: str, clock: Clock
) -> dict:
    key = check_idempotency_key(key)
    team, assignment = _require_member(db, user, team_id)
    now = clock.now()
    apply_deadline(db, assignment, now)

    # Lock the submission row: two members submitting at once are handled one at a time.
    sub = db.scalar(select(Submission).where(Submission.team_id == team.id).with_for_update())
    repeat = db.scalar(
        select(FinalSubmission).where(FinalSubmission.submitted_by == user.id, FinalSubmission.idempotency_key == key)
    )
    if repeat is not None:
        db.commit()
        return final_item(db, repeat)
    _check_open(assignment, sub, team, now)

    version = db.get(SubmissionVersion, version_id)
    if version is None or version.submission_id != sub.id:
        raise not_found("Draft")
    if sub.current_final_id != expected_final_id:
        current = db.get(FinalSubmission, sub.current_final_id) if sub.current_final_id else None
        raise conflict(
            "FINAL_CHANGED",
            "A teammate changed the final while you were looking. Check the new final first.",
            {
                "current_final": FinalOut.model_validate(final_item(db, current)).model_dump(mode="json")
                if current
                else None
            },
        )
    current = db.get(FinalSubmission, sub.current_final_id) if sub.current_final_id else None
    if current is not None and current.version_id == version.id:
        raise conflict("ALREADY_FINAL", "This draft is already the final.")
    members = _active_ids(db, team.id)
    if len(members) < assignment.min_team:
        raise conflict(
            "TEAM_BELOW_MIN_SIZE",
            f"The team needs at least {assignment.min_team} members to submit.",
            {"min_team": assignment.min_team, "active_members": len(members)},
        )
    if assignment.requires_pdf:
        has_pdf = db.scalar(
            select(func.count()).where(SubmissionFile.version_id == version.id, SubmissionFile.mime_type == PDF)
        )
        if not has_pdf:
            raise unprocessable("PDF_REQUIRED", "This assignment needs a PDF report in the final.")

    final = FinalSubmission(
        version_id=version.id,
        submitted_by=user.id,
        kind="manual",
        below_min_size=False,
        idempotency_key=key,
        submitted_at=now,
    )
    db.add(final)
    db.flush()
    if current is not None:
        current.replaced_at = now
    sub.current_final_id = final.id
    event = "final_replaced" if current is not None else "final_submitted"
    verb = "replaced the final with" if current is not None else "submitted"
    notify(
        db,
        event,
        [*members, *teacher_ids(db, assignment.course_id)],
        f"{user.name} {verb} v{version.number} for {team.name} ({assignment.title})",
        f"/teams/{team.id}",
        now,
        course_id=assignment.course_id,
    )
    db.commit()
    return final_item(db, final)


# ---------------------------------------------------------------- downloads


def file_for_download(db: Session, user: User, file_id: int, storage: LocalStorage):
    """Team members can download any of their drafts' files. Teachers only the current final's."""
    f = db.get(SubmissionFile, file_id)
    if f is None:
        raise not_found("File")
    version = db.get(SubmissionVersion, f.version_id)
    sub = db.get(Submission, version.submission_id)
    team, _assignment, _is_teacher = _access(db, user, sub.team_id)  # members and teachers only
    if not _is_member(db, team, user):
        current = db.get(FinalSubmission, sub.current_final_id) if sub.current_final_id else None
        if current is None or current.version_id != version.id:
            raise not_found("File")  # a teacher asking for a draft
    return storage.path(f.storage_key), f.file_name, f.mime_type
