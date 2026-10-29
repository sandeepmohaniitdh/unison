import time
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.core.deps import CSRF_HEADER, DB, SESSION_COOKIE, ClockDep, CurrentUser, SettingsDep, client_ip
from app.core.openapi import errors
from app.modules.admin.service import get_setting
from app.modules.auth import google
from app.modules.auth import service as auth
from app.modules.auth.schemas import Accepted, AuthConfig, ForgotIn, LoginIn, ResetIn, SignupIn, TokenIn, VerifiedOut
from app.modules.users import service as users
from app.modules.users.schemas import MeOut

router = APIRouter(prefix="/auth", tags=["auth"])


def get_sleeper() -> Callable[[float], None]:
    """Waits during the growing login delay. Tests replace it so they don't wait."""
    return time.sleep


def _set_session_cookie(response: Response, raw: str, settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/config", response_model=AuthConfig, summary="Login options for the sign-in page")
def auth_config(db: DB, settings: SettingsDep):
    return {
        "google_enabled": settings.google_enabled,
        "allowed_email_domain": get_setting(db, "allowed_email_domain"),
        "auth_mode": settings.auth_mode,
        "csrf_header": CSRF_HEADER,
    }


@router.post(
    "/register",
    response_model=MeOut,
    status_code=201,
    summary="Register: create a student account and log in",
    responses=errors(400, 403, 409, 429),
)
def register(body: SignupIn, request: Request, response: Response, db: DB, settings: SettingsDep, clock: ClockDep):
    """Always creates a student, and only for the allowed domain (@iitdh.ac.in),
    unless an invitation token for this email is given. Sends a verification email."""
    user, raw = auth.signup(
        db,
        name=body.name,
        email=body.email,
        password=body.password,
        consent=body.consent,
        invitation_token=body.invitation_token,
        ip=client_ip(request, settings),
        clock=clock,
        session_days=settings.session_days,
    )
    _set_session_cookie(response, raw, settings)
    return users.me(db, user)


@router.post(
    "/login",
    response_model=MeOut,
    summary="Log in with email and password",
    responses=errors(401, 403, 429),
)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: DB,
    settings: SettingsDep,
    clock: ClockDep,
    sleep: Annotated[Callable[[float], None], Depends(get_sleeper)],
):
    """Sets the session cookie. Logging in during the 7-day deletion grace period cancels the deletion."""
    try:
        user, raw, delay = auth.login(
            db, body.email, body.password, client_ip(request, settings), clock, settings.session_days
        )
    except Exception:
        sleep(1.0)  # slows down guessing
        raise
    if delay:
        sleep(delay)
    _set_session_cookie(response, raw, settings)
    return users.me(db, user)


@router.post("/logout", status_code=204, summary="Log out (ends this session)", responses=errors(401))
def logout(request: Request, response: Response, db: DB, clock: ClockDep, _user: CurrentUser):
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        auth.revoke_session(db, raw, clock.now())
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


@router.post(
    "/email-verifications",
    response_model=VerifiedOut,
    status_code=201,
    summary="Confirm an email with the token from its link",
    responses=errors(400),
)
def verify_email(body: TokenIn, db: DB, clock: ClockDep):
    email = auth.verify_email(db, body.token, clock)
    return {"email": email, "message": "Email confirmed."}


@router.post(
    "/password-reset-requests",
    response_model=Accepted,
    status_code=202,
    summary="Email a password reset link",
)
def forgot_password(body: ForgotIn, db: DB, clock: ClockDep):
    """Answers the same whether or not the email has an account."""
    auth.forgot_password(db, body.email, clock)
    return {"message": "If an account uses this email, a reset link is on its way."}


@router.post(
    "/password-resets", status_code=204, summary="Choose a new password from the emailed link", responses=errors(400)
)
def reset_password(body: ResetIn, db: DB, clock: ClockDep):
    """The link works once and for 30 minutes. All sessions are logged out."""
    auth.reset_password(db, body.token, body.new_password, clock)
    return Response(status_code=204)


@router.get(
    "/google",
    status_code=302,
    summary="Start Google sign-in (redirects to Google)",
    responses={302: {"description": "Redirect to Google"}, **errors(503)},
)
def google_sign_in(
    settings: SettingsDep,
    return_to: Annotated[str, Query(description="Frontend path to open after signing in.")] = "/dashboard",
):
    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/dashboard"
    url, cookie = google.start(settings, return_to)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        google.STATE_COOKIE,
        cookie,
        max_age=google.STATE_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth/google",
    )
    return response


@router.get(
    "/google/callback",
    status_code=302,
    summary="Google redirects back here",
    responses={302: {"description": "Redirect to the frontend"}, **errors(400, 403)},
)
def google_callback(
    request: Request,
    db: DB,
    settings: SettingsDep,
    clock: ClockDep,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
):
    data = google.read_state_cookie(settings, request.cookies.get(google.STATE_COOKIE), state)
    id_token = google.exchange_code(settings, code, data["verifier"])
    claims = google.verify_id_token(settings, id_token, data["nonce"])
    _user, raw = auth.google_sign_in(
        db,
        subject=claims["sub"],
        email=claims.get("email", ""),
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name", ""),
        clock=clock,
        session_days=settings.session_days,
    )
    response = RedirectResponse(settings.frontend_url.rstrip("/") + data["return_to"], status_code=302)
    _set_session_cookie(response, raw, settings)
    response.delete_cookie(google.STATE_COOKIE, path="/api/v1/auth/google")
    return response
