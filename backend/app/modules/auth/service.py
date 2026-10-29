"""Sign-up, login, sessions, rate limits, email links and Google sign-in.

Rate limits never lock an account: failed logins are counted per
email-and-IP pair and per IP. Five failures for one pair in 15 minutes pause
that pair for 15 minutes; 30 failures from one IP pause the IP. Failures for
one email from many IPs only add a growing delay of up to 10 seconds, so
nobody can lock a named user out.
"""

import ipaddress
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import bad_request, conflict, forbidden, too_many, unauthorized
from app.core.security import hash_token, new_token, verify_password
from app.core.time import Clock
from app.modules.admin.service import get_setting
from app.modules.auth.models import EmailToken, LoginAttempt, OAuthIdentity, UserSession
from app.modules.notifications.service import queue_email
from app.modules.users import service as users
from app.modules.users.models import User, UserEmail

PAIR_LIMIT = 5
IP_LIMIT = 30
WINDOW = timedelta(minutes=15)
MAX_DELAY_SECONDS = 10
VERIFY_HOURS = 48
RESET_MINUTES = 30


def _ip_bytes(ip: str) -> bytes:
    try:
        return ipaddress.ip_address(ip).packed
    except ValueError:
        return ipaddress.ip_address("0.0.0.0").packed


# ---------------------------------------------------------------- sessions


def create_session(db: Session, user: User, now: datetime, days: int) -> str:
    """Start a session. Returns the raw token for the cookie; only its hash is stored."""
    raw, token_hash = new_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(days=days),
            last_seen_at=now,
            created_at=now,
        )
    )
    return raw


def user_for_session(db: Session, raw_token: str, now: datetime) -> tuple[User, UserSession] | None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(raw_token)))
    if session is None or session.revoked_at is not None or session.expires_at <= now:
        return None
    user = db.get(User, session.user_id)
    if user is None:
        return None
    if now - session.last_seen_at > timedelta(minutes=5):
        session.last_seen_at = now
        db.commit()
    return user, session


def revoke_session(db: Session, raw_token: str, now: datetime) -> None:
    db.execute(
        update(UserSession)
        .where(UserSession.token_hash == hash_token(raw_token), UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()


def revoke_all_sessions(db: Session, user_id: int, now: datetime, except_session_id: int | None = None) -> None:
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    db.execute(stmt.values(revoked_at=now))


# ---------------------------------------------------------------- rate limits


def _failures(db: Session, since: datetime, *, email: str | None = None, ip: bytes | None = None) -> int:
    stmt = select(func.count()).where(
        LoginAttempt.kind == "login", LoginAttempt.succeeded.is_(False), LoginAttempt.created_at >= since
    )
    if email is not None:
        stmt = stmt.where(LoginAttempt.email == email)
    if ip is not None:
        stmt = stmt.where(LoginAttempt.ip == ip)
    return db.scalar(stmt) or 0


def check_login_allowed(db: Session, email: str, ip: str, now: datetime) -> float:
    """Raise 429 when the pair or the IP is paused. Returns the delay in seconds to wait."""
    since = now - WINDOW
    ip_b = _ip_bytes(ip)
    if _failures(db, since, email=email, ip=ip_b) >= PAIR_LIMIT:
        raise too_many(
            "TOO_MANY_ATTEMPTS",
            "Too many failed logins for this email from your network. Try again in 15 minutes.",
            900,
        )
    if _failures(db, since, ip=ip_b) >= IP_LIMIT:
        raise too_many("TOO_MANY_ATTEMPTS", "Too many failed logins from your network. Try again in 15 minutes.", 900)
    from_anywhere = _failures(db, since, email=email)
    if from_anywhere < PAIR_LIMIT:
        return 0.0
    return float(min(MAX_DELAY_SECONDS, from_anywhere - PAIR_LIMIT + 1))


def record_attempt(db: Session, kind: str, email: str | None, ip: str, ok: bool, now: datetime) -> None:
    db.add(LoginAttempt(kind=kind, email=email, ip=_ip_bytes(ip), succeeded=ok, created_at=now))


def check_signup_allowed(db: Session, ip: str, now: datetime) -> None:
    limit = int(get_setting(db, "signups_per_ip_per_hour"))
    count = db.scalar(
        select(func.count()).where(
            LoginAttempt.kind == "signup",
            LoginAttempt.ip == _ip_bytes(ip),
            LoginAttempt.created_at >= now - timedelta(hours=1),
        )
    )
    if (count or 0) >= limit:
        raise too_many("TOO_MANY_SIGNUPS", "Too many sign-ups from your network. Try again in an hour.", 3600)


# ---------------------------------------------------------------- email links


def send_verification(db: Session, user: User, user_email: UserEmail, now: datetime) -> None:
    raw, token_hash = new_token()
    token = EmailToken(
        user_id=user.id,
        user_email_id=user_email.id,
        purpose="verify_email",
        token_hash=token_hash,
        expires_at=now + timedelta(hours=VERIFY_HOURS),
    )
    db.add(token)
    db.flush()
    queue_email(
        db,
        to=user_email.email,
        user_id=user.id,
        template="verify_email",
        payload={"name": user.name, "email": user_email.email, "token": raw},
        dedup_key=f"verify:{token.id}",
        now=now,
    )


def _use_token(db: Session, raw: str, purpose: str, now: datetime) -> EmailToken:
    token = db.scalar(select(EmailToken).where(EmailToken.token_hash == hash_token(raw), EmailToken.purpose == purpose))
    if token is None or token.used_at is not None or token.expires_at <= now:
        raise bad_request("INVALID_TOKEN", "This link is invalid, already used or expired.")
    token.used_at = now
    return token


def verify_email(db: Session, raw: str, clock: Clock) -> str:
    now = clock.now()
    token = _use_token(db, raw, "verify_email", now)
    row = db.get(UserEmail, token.user_email_id) if token.user_email_id else None
    if row is None:
        raise bad_request("INVALID_TOKEN", "This email is no longer on the account.")
    row.verified_at = row.verified_at or now
    db.commit()
    return row.email


def forgot_password(db: Session, email: str, clock: Clock) -> None:
    """Always answers the same way, so nobody can test which emails have accounts."""
    now = clock.now()
    user = users.find_user_by_email(db, email)
    if user is None or user.status in ("deleted", "suspended"):
        return
    raw, token_hash = new_token()
    token = EmailToken(
        user_id=user.id,
        purpose="reset_password",
        token_hash=token_hash,
        expires_at=now + timedelta(minutes=RESET_MINUTES),
    )
    db.add(token)
    db.flush()
    queue_email(
        db,
        to=users.normalise_email(email),
        user_id=user.id,
        template="reset_password",
        payload={"name": user.name, "token": raw},
        dedup_key=f"reset:{token.id}",
        now=now,
    )
    db.commit()


def reset_password(db: Session, raw: str, new_password: str, clock: Clock) -> None:
    now = clock.now()
    users.check_password_strength(new_password)
    token = _use_token(db, raw, "reset_password", now)
    user = db.get(User, token.user_id)
    from app.core.security import hash_password

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    revoke_all_sessions(db, user.id, now)
    db.commit()


# ---------------------------------------------------------------- sign-up and login


def _check_domain(db: Session, email: str) -> None:
    domain = str(get_setting(db, "allowed_email_domain")).lower()
    if not email.endswith("@" + domain):
        raise forbidden(f"Sign-up is open only to @{domain} email addresses.", "EMAIL_DOMAIN_NOT_ALLOWED")


def signup(
    db: Session,
    *,
    name: str,
    email: str,
    password: str,
    consent: bool,
    invitation_token: str | None,
    ip: str,
    clock: Clock,
    session_days: int,
) -> tuple[User, str]:
    """Create a student account (or the invited staff role) and log in."""
    from app.modules.invitations.service import invitation_for_signup

    now = clock.now()
    email = users.normalise_email(email)
    if not consent:
        raise bad_request("CONSENT_REQUIRED", "Please accept the data notice to create an account.")
    check_signup_allowed(db, ip, now)
    record_attempt(db, "signup", email, ip, True, now)
    db.commit()  # the attempt counts even if the sign-up fails below
    users.check_password_strength(password)

    invitation = invitation_for_signup(db, invitation_token, email, now) if invitation_token else None
    if invitation is None:
        _check_domain(db, email)
    if users.email_taken(db, email):
        raise conflict("EMAIL_TAKEN", "An account with this email already exists. Log in instead.")

    role = invitation.role if invitation is not None and invitation.kind == "staff" else "student"
    user = users.create_user(
        db, name=name, email=email, role=role, password=password, now=now, verified=invitation is not None
    )
    if invitation is None:
        row = db.scalar(select(UserEmail).where(UserEmail.user_id == user.id))
        send_verification(db, user, row, now)
    elif invitation.kind == "staff":
        # Signing up through a staff link uses it up: the account gets the role now.
        invitation.status = "accepted"
        invitation.accepted_user_id = user.id
        invitation.responded_at = now
    raw = create_session(db, user, now, session_days)
    db.commit()
    return user, raw


def login(db: Session, email: str, password: str, ip: str, clock: Clock, session_days: int) -> tuple[User, str, float]:
    """Check the password and start a session. Returns (user, raw token, delay seconds)."""
    now = clock.now()
    email = users.normalise_email(email)
    delay = check_login_allowed(db, email, ip, now)
    user = users.find_user_by_email(db, email)
    ok = user is not None and user.status != "deleted" and verify_password(password, user.password_hash)
    if not ok:
        record_attempt(db, "login", email, ip, False, now)
        db.commit()
        raise unauthorized("The email or password is wrong.", "INVALID_CREDENTIALS")
    if user.status == "suspended":
        raise forbidden("Your account is suspended. Contact an administrator.", "ACCOUNT_SUSPENDED")
    record_attempt(db, "login", email, ip, True, now)
    users.cancel_deletion_on_login(user)
    raw = create_session(db, user, now, session_days)
    db.commit()
    return user, raw, delay


# ---------------------------------------------------------------- Google sign-in


def google_sign_in(
    db: Session, *, subject: str, email: str, email_verified: bool, name: str, clock: Clock, session_days: int
) -> tuple[User, str]:
    """After the ID token was checked: find or create the account and start a session.

    A Google account is linked to an existing account only if Google says
    the email is verified. New accounts must use the allowed domain.
    """
    now = clock.now()
    email = users.normalise_email(email)
    if not email_verified:
        raise forbidden("Your Google email is not verified.", "GOOGLE_EMAIL_NOT_VERIFIED")
    identity = db.scalar(
        select(OAuthIdentity).where(OAuthIdentity.provider == "google", OAuthIdentity.subject == subject)
    )
    if identity is not None:
        user = db.get(User, identity.user_id)
    else:
        user = users.find_user_by_email(db, email)
        if user is None:
            _check_domain(db, email)
            user = users.create_user(
                db, name=name or email.split("@")[0], email=email, role="student", now=now, verified=True
            )
        else:
            row = db.scalar(select(UserEmail).where(UserEmail.email == email))
            row.verified_at = row.verified_at or now
        db.add(OAuthIdentity(user_id=user.id, provider="google", subject=subject, created_at=now))
    if user.status == "deleted":
        raise forbidden("This account was deleted.", "ACCOUNT_DELETED")
    if user.status == "suspended":
        raise forbidden("Your account is suspended. Contact an administrator.", "ACCOUNT_SUSPENDED")
    users.cancel_deletion_on_login(user)
    raw = create_session(db, user, now, session_days)
    db.commit()
    return user, raw
