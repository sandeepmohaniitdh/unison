from fastapi import APIRouter, Response

from app.core.deps import DB, ClockDep, CurrentUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination
from app.modules.teams import service
from app.modules.teams.schemas import MemberMove, TeamIn, TeamOut

router = APIRouter(tags=["teams"])


@router.get(
    "/assignments/{assignment_id}/teams",
    response_model=Page[TeamOut],
    summary="All teams (teachers)",
    responses=errors(401, 403, 404),
)
def list_teams(assignment_id: int, db: DB, clock: ClockDep, user: CurrentUser, page: Pagination):
    return service.list_teams(db, user, assignment_id, page, clock)


@router.post(
    "/assignments/{assignment_id}/teams",
    response_model=TeamOut,
    status_code=201,
    summary="Create a team (students, group assignments)",
    responses=errors(401, 403, 404, 409),
)
def create_team(assignment_id: int, body: TeamIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.create_team(db, user, assignment_id, body.name, clock)


@router.get(
    "/assignments/{assignment_id}/my-team",
    response_model=TeamOut,
    summary="My team for this assignment",
    responses=errors(401, 404),
)
def my_team(assignment_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """For an individual assignment the team of one is created on first use. 404 when the student has no team."""
    return service.my_team(db, user, assignment_id, clock)


@router.get(
    "/teams/{team_id}", response_model=TeamOut, summary="One team (members and teachers)", responses=errors(401, 404)
)
def get_team(team_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    return service.view_team(db, user, team_id, clock)


@router.patch("/teams/{team_id}", response_model=TeamOut, summary="Rename the team", responses=errors(401, 404, 409))
def rename_team(team_id: int, body: TeamIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.rename_team(db, user, team_id, body.name, clock)


@router.delete(
    "/teams/{team_id}/members/me",
    status_code=204,
    summary="Leave the team (before its first final)",
    responses=errors(401, 404, 409),
)
def leave_team(team_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Drafts you uploaded stay with the team. If you were the last member, the team is closed."""
    service.leave_team(db, user, team_id, clock)
    return Response(status_code=204)


@router.delete(
    "/teams/{team_id}/members/{user_id}",
    status_code=204,
    summary="Remove a member (teachers)",
    responses=errors(401, 403, 404, 409),
)
def remove_member(team_id: int, user_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    service.teacher_remove(db, user, team_id, user_id, clock)
    return Response(status_code=204)


@router.patch(
    "/teams/{team_id}/members/{user_id}",
    response_model=TeamOut,
    summary="Move a member to another team (teachers)",
    responses=errors(401, 403, 404, 409),
)
def move_member(team_id: int, user_id: int, body: MemberMove, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"team_id": <another team of the same assignment>}. Returns the team they joined.
    Allowed any time before marks are released; the size limit still applies."""
    return service.teacher_move(db, user, team_id, user_id, body.team_id, clock)
