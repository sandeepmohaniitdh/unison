import json

from fastapi import APIRouter, Request, Response

from app.core.deps import DB, ClockDep, CurrentUser
from app.core.openapi import errors
from app.modules.users import service
from app.modules.users.schemas import (
    DeletionOut,
    DeletionPreview,
    DeletionRequest,
    EmailAdd,
    EmailOut,
    EmailUpdate,
    MeOut,
    PasswordChange,
    ProfileUpdate,
)

router = APIRouter(prefix="/users/me", tags=["users"])


@router.get("", response_model=MeOut, summary="The logged-in user", responses=errors(401))
def get_me(db: DB, user: CurrentUser):
    return service.me(db, user)


@router.patch("", response_model=MeOut, summary="Edit the profile", responses=errors(401))
def update_me(body: ProfileUpdate, db: DB, user: CurrentUser):
    return service.update_profile(db, user, body.name)


@router.put("/password", status_code=204, summary="Set or change the password", responses=errors(401, 400, 403))
def change_password(body: PasswordChange, request: Request, db: DB, clock: ClockDep, user: CurrentUser):
    """Other sessions are logged out; this one stays."""
    session = getattr(request.state, "session", None)
    service.change_password(db, user, body.current_password, body.new_password, clock, session.id if session else None)
    return Response(status_code=204)


@router.post(
    "/emails", response_model=EmailOut, status_code=201, summary="Add a second email", responses=errors(401, 409)
)
def add_email(body: EmailAdd, db: DB, clock: ClockDep, user: CurrentUser):
    """Any domain is allowed. A verification link is emailed; invitations to this
    address work once it is verified."""
    return service.add_email(db, user, body.email, clock)


@router.delete("/emails/{email_id}", status_code=204, summary="Remove a second email", responses=errors(401, 404, 409))
def remove_email(email_id: int, db: DB, user: CurrentUser):
    service.remove_email(db, user, email_id)
    return Response(status_code=204)


@router.patch(
    "/emails/{email_id}",
    response_model=MeOut,
    summary="Make a verified email the primary one",
    responses=errors(401, 404, 409),
)
def update_email(email_id: int, body: EmailUpdate, db: DB, user: CurrentUser):
    """Send {"is_primary": true}. The email must be verified."""
    return service.make_primary(db, user, email_id)


@router.post(
    "/emails/{email_id}/verifications",
    status_code=202,
    summary="Send the verification link again",
    responses=errors(401, 404, 409),
)
def resend_verification(email_id: int, db: DB, clock: ClockDep, user: CurrentUser):
    service.resend_verification(db, user, email_id, clock)
    return Response(status_code=202)


@router.delete("/google", status_code=204, summary="Unlink the Google account", responses=errors(401, 409))
def unlink_google(db: DB, user: CurrentUser):
    service.unlink_google(db, user)
    return Response(status_code=204)


@router.get(
    "/personal-data",
    summary="Download my data (JSON)",
    responses={
        200: {"content": {"application/json": {}}, "description": "All data Unison holds about you"},
        **errors(401),
    },
)
def data_export(db: DB, user: CurrentUser):
    data = service.export_data(db, user)
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="unison-my-data.json"'},
    )


@router.get(
    "/deletion", response_model=DeletionPreview, summary="What deleting the account would leave", responses=errors(401)
)
def deletion_preview(db: DB, user: CurrentUser):
    return service.deletion_preview(db, user)


@router.post(
    "/deletion",
    response_model=DeletionOut,
    status_code=202,
    summary="Delete my account",
    responses=errors(401, 403, 409),
)
def request_deletion(body: DeletionRequest, request: Request, db: DB, clock: ClockDep, user: CurrentUser):
    """Deactivates the account at once and logs out everywhere. Logging in again
    within 7 days cancels the deletion; after that it is final."""
    when = service.request_deletion(db, user, body.password, getattr(request.state, "session", None), clock)
    return {
        "status": "deactivated",
        "final_deletion_at": when,
        "message": "Your account is deactivated. Log in within 7 days to cancel the deletion.",
    }
