"""FastAPI dependencies: the database session, the clock, file storage and,
most importantly, the current user.

Everything here can be replaced in tests with app.dependency_overrides.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import forbidden, unauthorized
from app.core.storage import LocalStorage
from app.core.time import Clock
from app.db import get_session_factory
from app.modules.users.models import User

SESSION_COOKIE = "unison_session"
CSRF_HEADER = "X-Unison-Client"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Requests a user with must_change_password may still make.
PASSWORD_CHANGE_ALLOWED = {
    "/api/v1/users/me",
    "/api/v1/users/me/password",
    "/api/v1/auth/logout",
}


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


_clock = Clock()


def get_clock() -> Clock:
    return _clock


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> LocalStorage:
    return LocalStorage(settings.upload_dir)


DB = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ClockDep = Annotated[Clock, Depends(get_clock)]
StorageDep = Annotated[LocalStorage, Depends(get_storage)]

session_cookie = APIKeyCookie(
    name=SESSION_COOKIE,
    scheme_name="SessionCookie",
    auto_error=False,
    description="Set by POST /auth/login. State-changing requests that use the cookie "
    f"must also send the header `{CSRF_HEADER}: web`.",
)
demo_header = APIKeyHeader(
    name="X-Demo-User",
    scheme_name="DemoUser",
    auto_error=False,
    description="Demo mode only (AUTH_MODE=demo): the email of a seeded user, "
    "for example demo.student@example.com. Ignored on the real site.",
)


def _resolve_user(
    request: Request, db: Session, settings: Settings, clock: Clock, cookie: str | None, demo: str | None
):
    # Imported here to avoid an import cycle (auth uses these dependencies too).
    from app.modules.auth import service as auth_service
    from app.modules.users import service as users_service

    if demo and settings.auth_mode == "demo":
        user = users_service.find_user_by_email(db, demo)
        if user is None:
            raise unauthorized("No user has this demo email.", "DEMO_USER_UNKNOWN")
        request.state.auth_via = "demo"
    elif cookie:
        found = auth_service.user_for_session(db, cookie, clock.now())
        if found is None:
            raise unauthorized("Your session has ended. Please log in again.", "SESSION_EXPIRED")
        user, session = found
        request.state.session = session
        request.state.auth_via = "cookie"
        if request.method not in SAFE_METHODS and request.headers.get(CSRF_HEADER) != "web":
            raise forbidden(f"Missing the {CSRF_HEADER} header.", "CSRF_HEADER_MISSING")
    else:
        return None

    if user.status == "suspended":
        raise forbidden("Your account is suspended. Contact an administrator.", "ACCOUNT_SUSPENDED")
    if user.status != "active":
        raise unauthorized("This account is not active.", "ACCOUNT_INACTIVE")
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED:
        raise forbidden("Please change your password first.", "PASSWORD_CHANGE_REQUIRED")
    request.state.user = user
    return user


def get_current_user(
    request: Request,
    db: DB,
    settings: SettingsDep,
    clock: ClockDep,
    cookie: Annotated[str | None, Security(session_cookie)] = None,
    demo: Annotated[str | None, Security(demo_header)] = None,
) -> User:
    """The logged-in user, or 401. Every protected route depends on this."""
    user = _resolve_user(request, db, settings, clock, cookie, demo)
    if user is None:
        raise unauthorized()
    return user


def get_optional_user(
    request: Request,
    db: DB,
    settings: SettingsDep,
    clock: ClockDep,
    cookie: Annotated[str | None, Security(session_cookie)] = None,
    demo: Annotated[str | None, Security(demo_header)] = None,
) -> User | None:
    """For public pages that show more to logged-in users."""
    return _resolve_user(request, db, settings, clock, cookie, demo)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise forbidden("Only administrators can do this.", "ADMIN_ONLY")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def client_ip(request: Request, settings: Settings) -> str:
    """The caller's IP address, used for rate limits.

    X-Forwarded-For is only trusted behind our own nginx (TRUST_PROXY=true),
    because anyone can send that header.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if settings.trust_proxy and forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "127.0.0.1"
