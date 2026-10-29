from typing import Literal

from fastapi import APIRouter, Response

from app.core.deps import DB, AdminUser, ClockDep, CurrentUser, OptionalUser
from app.core.openapi import errors
from app.core.pagination import Page, Pagination, page_of
from app.modules.invitations import service
from app.modules.invitations.schemas import (
    CourseInvitationIn,
    CourseInvitationResult,
    InvitationOut,
    InvitationResponseIn,
    InvitationResponseOut,
    InvitationView,
    StaffInvitationIn,
)
from app.modules.teams.schemas import TeamInvitationIn

router = APIRouter(tags=["invitations"])

Status = Literal["pending", "accepted", "declined", "cancelled", "expired"]


# ---------------------------------------------------------------- sending


@router.post(
    "/courses/{course_id}/invitations",
    response_model=CourseInvitationResult,
    status_code=201,
    summary="Invite students (or a co-teacher) by email",
    responses=errors(401, 403, 404, 409),
)
def create_course_invitations(course_id: int, body: CourseInvitationIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Each link works once, for 7 days, for an account with that verified email.
    Emails that are already members or already invited are skipped and listed."""
    return service.invite_to_course(db, user, course_id, body.emails, body.role, clock)


@router.get(
    "/courses/{course_id}/invitations",
    response_model=Page[InvitationOut],
    summary="List a course's invitations",
    responses=errors(401, 403, 404),
)
def list_course_invitations(course_id: int, db: DB, user: CurrentUser, page: Pagination, status: Status | None = None):
    return service.list_course_invitations(db, user, course_id, page, status)


@router.post(
    "/teams/{team_id}/invitations",
    response_model=InvitationOut,
    status_code=201,
    summary="Invite a classmate to the team",
    responses=errors(400, 401, 404, 409),
)
def create_team_invitation(team_id: int, body: TeamInvitationIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Any active member can invite. Members plus pending invitations can never exceed the team size."""
    return service.invite_to_team(db, user, team_id, body.email, clock)


@router.get(
    "/teams/{team_id}/invitations",
    response_model=Page[InvitationOut],
    summary="List the team's invitations",
    responses=errors(401, 404),
)
def list_team_invitations(team_id: int, db: DB, user: CurrentUser, page: Pagination):
    return page_of(service.list_team_invitations(db, user, team_id), page)


@router.post(
    "/admin/staff-invitations",
    response_model=InvitationOut,
    status_code=201,
    summary="Invite a teacher or admin",
    responses=errors(401, 403, 409),
)
def create_staff_invitation(body: StaffInvitationIn, db: DB, clock: ClockDep, admin: AdminUser):
    """Signing up through the link creates the account with that role; an existing
    student account with that email is upgraded when it accepts."""
    return service.invite_staff(db, admin, body.email, body.role, clock)


@router.get(
    "/admin/staff-invitations",
    response_model=Page[InvitationOut],
    summary="List staff invitations",
    responses=errors(401, 403),
)
def list_staff_invitations(db: DB, _admin: AdminUser, page: Pagination, status: Status | None = None):
    return service.list_staff_invitations(db, page, status)


@router.delete(
    "/invitations/{invitation_id}",
    status_code=204,
    summary="Cancel a pending invitation (sender)",
    responses=errors(401, 403, 404, 409),
)
def delete_invitation(invitation_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    """Course invitations: the course's teachers. Team invitations: any active member. Staff: admins."""
    service.cancel(db, user, invitation_id, clock)
    return Response(status_code=204)


# ---------------------------------------------------------------- the invitee's side


@router.get(
    "/users/me/invitations",
    response_model=Page[InvitationView],
    summary="List my pending invitations",
    responses=errors(401),
)
def list_my_invitations(db: DB, clock: ClockDep, user: CurrentUser, page: Pagination):
    """Invitations to any of my verified emails, soonest expiry first."""
    return page_of(service.my_invitations(db, user, clock), page)


@router.patch(
    "/invitations/{invitation_id}",
    response_model=InvitationResponseOut,
    summary="Accept or decline an invitation (invitee)",
    responses=errors(401, 403, 404, 409),
)
def respond_to_invitation(invitation_id: int, body: InvitationResponseIn, db: DB, clock: ClockDep, user: CurrentUser):
    """Send {"status": "accepted"} or {"status": "declined"}. Accepting a team invitation
    declines your other invitations for that assignment."""
    return service.respond(db, user, clock, body.status, invitation_id=invitation_id)


@router.get(
    "/invitation-links/{token}",
    response_model=InvitationView,
    summary="Open an invitation link",
    responses=errors(404),
)
def get_invitation_link(token: str, db: DB, clock: ClockDep, user: OptionalUser):
    """Works without logging in. `problem` says why it can't be accepted yet
    (for example log_in, wrong_account, expired)."""
    return service.view_by_token(db, token, user, clock)


@router.patch(
    "/invitation-links/{token}",
    response_model=InvitationResponseOut,
    summary="Accept or decline from the emailed link",
    responses=errors(401, 403, 404, 409),
)
def respond_to_invitation_link(token: str, body: InvitationResponseIn, db: DB, clock: ClockDep, user: CurrentUser):
    return service.respond(db, user, clock, body.status, token=token)
