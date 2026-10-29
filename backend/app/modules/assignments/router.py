from fastapi import APIRouter, Response

from app.core.deps import DB, ClockDep, CurrentUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination
from app.modules.assignments import service
from app.modules.assignments.schemas import (
    AssignmentDetail,
    AssignmentIn,
    AssignmentSummary,
    AssignmentUpdate,
)

router = APIRouter(tags=["assignments"])


@router.get(
    "/courses/{course_id}/assignments",
    response_model=Page[AssignmentSummary],
    summary="A course's assignments",
    responses=errors(401, 403, 404),
)
def list_course_assignments(course_id: int, db: DB, clock: ClockDep, user: CurrentUser, page: Pagination):
    """Students see published and closed assignments with their team's state; teachers also see drafts."""
    return service.list_for_course(db, user, course_id, page, clock)


@router.post(
    "/courses/{course_id}/assignments",
    response_model=AssignmentDetail,
    status_code=201,
    summary="Create an assignment (as a draft)",
    responses=errors(400, 401, 403, 404, 409),
)
def create_assignment(course_id: int, body: AssignmentIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.create(db, user, course_id, body.model_dump(), clock)


@router.get(
    "/assignments/{assignment_id}",
    response_model=AssignmentDetail,
    summary="One assignment with its rubric",
    responses=errors(401, 403, 404),
)
def get_assignment(assignment_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    return service.get_detail(db, user, assignment_id, clock)


@router.patch(
    "/assignments/{assignment_id}",
    response_model=AssignmentDetail,
    summary="Edit, publish, extend or lock an assignment",
    responses=errors(400, 401, 403, 404, 409),
)
def update_assignment(assignment_id: int, body: AssignmentUpdate, db: DB, clock: ClockDep, user: CurrentUser):
    """Examples: {"status": "published"} publishes a draft and notifies the class;
    {"due_at": "2026-11-25T23:59"} extends a published deadline (before it passes);
    {"teams_locked": true} freezes the teams."""
    data = body.model_dump(exclude_unset=True)
    return service.update(db, user, assignment_id, data, clock)


@router.delete(
    "/assignments/{assignment_id}",
    status_code=204,
    summary="Delete a draft assignment",
    responses=errors(401, 403, 404, 409),
)
def delete_assignment(assignment_id: int, db: DB, user: CurrentUser):
    service.remove(db, user, assignment_id)
    return Response(status_code=204)
