from fastapi import APIRouter, Response

from app.core.deps import DB, ClockDep, CurrentUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination
from app.modules.reviews import service
from app.modules.reviews.schemas import (
    AdjustmentIn,
    BulkReleaseOut,
    MyMarks,
    ReleaseIn,
    ReviewIn,
    ReviewRow,
    ReviewSheet,
)

router = APIRouter(tags=["reviews"])


@router.get(
    "/assignments/{assignment_id}/reviews",
    response_model=Page[ReviewRow],
    summary="Every team's state and mark (review page)",
    responses=errors(401, 403, 404),
)
def list_reviews(assignment_id: int, db: DB, clock: ClockDep, user: CurrentUser, page: Pagination):
    return service.overview(db, user, assignment_id, page, clock)


@router.patch(
    "/assignments/{assignment_id}/reviews",
    response_model=BulkReleaseOut,
    summary="Release every complete review of the assignment",
    responses=errors(401, 403, 404, 409),
)
def release_reviews(assignment_id: int, body: ReleaseIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"status": "released"}. Teams whose review is missing or incomplete are skipped and listed."""
    return service.release_all(db, user, assignment_id, clock)


@router.get(
    "/teams/{team_id}/review",
    response_model=ReviewSheet,
    summary="Review sheet for the team's final",
    responses=errors(401, 403, 404, 409),
)
def get_review(team_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Teachers. Shows the current final only, the rubric, the contribution summary and each member's mark."""
    return service.sheet(db, user, team_id, clock)


@router.put(
    "/teams/{team_id}/review",
    response_model=ReviewSheet,
    summary="Save scores and comments",
    responses=errors(401, 403, 404, 409),
)
def save_review(team_id: int, body: ReviewIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Allowed after the deadline and until marks are released."""
    return service.save_review(db, user, team_id, body.model_dump(exclude_unset=True), clock)


@router.put(
    "/teams/{team_id}/review/adjustments/{user_id}",
    response_model=ReviewSheet,
    summary="Adjust one member's mark",
    responses=errors(401, 403, 404, 409),
)
def set_adjustment(team_id: int, user_id: int, body: AdjustmentIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.set_adjustment(db, user, team_id, user_id, body.percent, body.reason, clock)


@router.delete(
    "/teams/{team_id}/review/adjustments/{user_id}",
    status_code=204,
    summary="Remove an adjustment",
    responses=errors(401, 403, 404, 409),
)
def remove_adjustment(team_id: int, user_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    service.remove_adjustment(db, user, team_id, user_id, clock)
    return Response(status_code=204)


@router.patch(
    "/teams/{team_id}/review",
    response_model=ReviewSheet,
    summary="Release this team's marks",
    responses=errors(401, 403, 404, 409),
)
def release_review(team_id: int, body: ReleaseIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"status": "released"}. Every criterion must be scored. Every member is notified."""
    return service.release(db, user, team_id, clock)


@router.get("/teams/{team_id}/marks", response_model=MyMarks, summary="My released marks", responses=errors(401, 404))
def get_my_marks(team_id: int, db: DB, user: CurrentUser):
    """Team members, after release. Each student sees only their own adjustment."""
    return service.my_marks(db, user, team_id)
