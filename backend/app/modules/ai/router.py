from fastapi import APIRouter, Response

from app.core.deps import DB, ClockDep, CurrentUser, SettingsDep
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of
from app.modules.ai import service
from app.modules.ai.schemas import AiDraftOut, AiStatus, DraftAllOut, DraftRequest

router = APIRouter(tags=["ai"])


@router.get("/ai/status", response_model=AiStatus, summary="Is the AI feedback draft available?", responses=errors(401))
def get_ai_status(db: DB, settings: SettingsDep, _user: CurrentUser):
    return service.status(settings, db)


@router.post(
    "/teams/{team_id}/review/ai-drafts",
    response_model=AiDraftOut,
    status_code=202,
    summary="Ask for an AI feedback draft for the team's final",
    responses={
        200: {"model": AiDraftOut, "description": "A cached draft for the same PDF and rubric"},
        **errors(401, 403, 404, 409, 429, 503),
    },
)
def create_ai_draft(
    team_id: int,
    body: DraftRequest,
    response: Response,
    db: DB,
    settings: SettingsDep,
    clock: ClockDep,
    user: CurrentUser,
):
    """Teachers. Returns 202 with a queued draft; poll GET /ai-drafts/{id}.
    Reads only the PDF report; names, emails and roll numbers are removed first.
    At most 3 per final; 429 beyond the limits; 503 when AI is switched off."""
    draft, cached = service.request_draft(db, user, team_id, body.file_id, settings, clock)
    if cached:
        response.status_code = 200
    return draft


@router.get(
    "/teams/{team_id}/review/ai-drafts",
    response_model=Page[AiDraftOut],
    summary="AI drafts for the team's current final",
    responses=errors(401, 403, 404, 409),
)
def list_ai_drafts(team_id: int, db: DB, user: CurrentUser, page: Pagination):
    """Newest first."""
    return page_of(service.list_for_team(db, user, team_id), page)


@router.post(
    "/assignments/{assignment_id}/ai-drafts",
    response_model=DraftAllOut,
    status_code=202,
    summary="Draft all: queue a draft for every final",
    responses=errors(401, 403, 404, 503),
)
def create_ai_drafts_for_assignment(
    assignment_id: int, db: DB, settings: SettingsDep, clock: ClockDep, user: CurrentUser
):
    """One background job, one team at a time. Teams with no PDF, several PDFs or
    an existing draft are skipped and listed."""
    return service.draft_all(db, user, assignment_id, settings, clock)


@router.get(
    "/ai-drafts/{draft_id}",
    response_model=AiDraftOut,
    summary="One AI draft (poll until ready)",
    responses=errors(401, 403, 404),
)
def get_ai_draft(draft_id: int, db: DB, user: CurrentUser):
    return service.get_draft(db, user, draft_id)
