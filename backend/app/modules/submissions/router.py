from typing import Annotated

from fastapi import APIRouter, File, Header, UploadFile

from app.core.deps import DB, ClockDep, CurrentUser, StorageDep
from app.core.downloads import FILE_RESPONSE, file_download
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of
from app.modules.submissions import service
from app.modules.submissions.schemas import DraftOut, FinalIn, FinalOut, SubmissionOut

router = APIRouter(tags=["submissions"])

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", description="A new UUID per action. Repeating it returns the first result."),
]


@router.get(
    "/teams/{team_id}/submission",
    response_model=SubmissionOut,
    summary="The team's submission state",
    responses=errors(401, 404),
)
def get_submission(team_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Members and the course's teachers. Teachers see only the current final, never drafts."""
    return service.submission_view(db, user, team_id, clock)


@router.get(
    "/teams/{team_id}/submission/drafts",
    response_model=Page[DraftOut],
    summary="The team's drafts",
    responses=errors(401, 404),
)
def list_drafts(team_id: int, db: DB, user: CurrentUser, page: Pagination):
    """Team members only, newest first."""
    return page_of(service.list_drafts(db, user, team_id), page)


@router.post(
    "/teams/{team_id}/submission/drafts",
    response_model=DraftOut,
    status_code=201,
    summary="Upload a draft",
    responses=errors(400, 401, 404, 409, 413),
)
def create_draft(
    team_id: int,
    db: DB,
    storage: StorageDep,
    clock: ClockDep,
    user: CurrentUser,
    files: Annotated[list[UploadFile], File(description="Up to 5 PDF or ZIP files, 10 MB each.")],
    idempotency_key: IdempotencyKey,
):
    """Any active member, before the deadline. Teammates get an in-app notification."""
    return service.upload_draft(db, user, team_id, files, idempotency_key, storage, clock)


@router.get(
    "/teams/{team_id}/submission/finals",
    response_model=Page[FinalOut],
    summary="Every final, including replaced ones",
    responses=errors(401, 404),
)
def list_finals(team_id: int, db: DB, user: CurrentUser, page: Pagination):
    """Team members only, newest first."""
    return page_of(service.list_finals(db, user, team_id), page)


@router.post(
    "/teams/{team_id}/submission/finals",
    response_model=FinalOut,
    status_code=201,
    summary="Submit a draft as the team's final",
    responses=errors(400, 401, 404, 409),
)
def create_final(
    team_id: int, body: FinalIn, db: DB, clock: ClockDep, user: CurrentUser, idempotency_key: IdempotencyKey
):
    """Before the deadline and only while the team has at least its minimum size.
    Replaces any earlier final. Every member and the teachers are notified.

    409 FINAL_CHANGED: someone changed the final since you looked; details.current_final has it."""
    return service.submit_final(db, user, team_id, body.version_id, body.expected_final_id, idempotency_key, clock)


@router.get(
    "/submission-files/{file_id}/content",
    summary="Download a submitted file",
    responses={**FILE_RESPONSE, **errors(401, 404)},
)
def get_submission_file_content(file_id: int, db: DB, storage: StorageDep, user: CurrentUser):
    """Members: any of their team's files. Teachers: files of the current final only."""
    path, name, mime = service.file_for_download(db, user, file_id, storage)
    return file_download(path, name, mime)
