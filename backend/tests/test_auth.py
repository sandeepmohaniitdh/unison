"""Sign-up, login, sessions, CSRF, rate limits, email links."""

from datetime import timedelta

from sqlalchemy import select

from app.modules.auth.models import EmailToken
from app.modules.auth.service import create_session
from app.modules.notifications.models import EmailOutbox
from app.modules.users.models import User
from tests.factories import make_user

CSRF = {"X-Unison-Client": "web"}


def signup(client, email="cs26mt099@iitdh.ac.in", **kw):
    body = {"name": "New Student", "email": email, "password": "correct horse", "consent": True, **kw}
    return client.post("/api/v1/auth/register", json=body)


def test_signup_creates_logged_in_student_and_sends_verification(client, db):
    r = signup(client)
    assert r.status_code == 201
    me = r.json()
    assert me["role"] == "student" and me["emails"][0] == {
        "id": me["emails"][0]["id"],
        "email": "cs26mt099@iitdh.ac.in",
        "is_primary": True,
        "verified": False,
    }
    assert "unison_session" in r.cookies
    assert client.get("/api/v1/users/me").json()["id"] == me["id"]
    outbox = db.scalars(select(EmailOutbox).where(EmailOutbox.template == "verify_email")).all()
    assert len(outbox) == 1 and outbox[0].to_email == "cs26mt099@iitdh.ac.in"


def test_signup_rules(client):
    assert signup(client, email="someone@gmail.com").json()["error"]["code"] == "EMAIL_DOMAIN_NOT_ALLOWED"
    assert signup(client, consent=False).json()["error"]["code"] == "CONSENT_REQUIRED"
    assert signup(client, password="short").status_code == 422
    assert signup(client).status_code == 201
    assert signup(client).json()["error"]["code"] == "EMAIL_TAKEN"


def test_signup_rate_limit_per_ip(client):
    for i in range(5):
        signup(client, email=f"cs26mt{100 + i}@iitdh.ac.in")
    r = signup(client, email="cs26mt200@iitdh.ac.in")
    assert r.status_code == 429 and r.headers["Retry-After"] == "3600"


def test_verify_email_link(client, db, clock):
    signup(client)
    raw = db.scalar(select(EmailOutbox)).payload["token"]
    r = client.post("/api/v1/auth/email-verifications", json={"token": raw})
    assert r.status_code == 201 and r.json()["email"] == "cs26mt099@iitdh.ac.in"
    assert client.get("/api/v1/users/me").json()["emails"][0]["verified"] is True
    again = client.post("/api/v1/auth/email-verifications", json={"token": raw})
    assert again.json()["error"]["code"] == "INVALID_TOKEN"


def test_login_logout_and_session_cookie(client, db):
    person = make_user(db, "student", email="cs26mt050@iitdh.ac.in", password="secret pass")
    r = client.post("/api/v1/auth/login", json={"email": "CS26MT050@iitdh.ac.in", "password": "secret pass"})
    assert r.status_code == 200 and r.json()["id"] == person.id
    assert client.get("/api/v1/users/me").status_code == 200
    # Changing something with the cookie needs the CSRF header.
    assert client.patch("/api/v1/users/me", json={"name": "X"}).json()["error"]["code"] == "CSRF_HEADER_MISSING"
    assert client.patch("/api/v1/users/me", json={"name": "Renamed"}, headers=CSRF).json()["name"] == "Renamed"
    assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204
    assert client.get("/api/v1/users/me").status_code == 401


def test_wrong_password_and_throttling(client, db, sleeps):
    make_user(db, "student", email="cs26mt051@iitdh.ac.in", password="secret pass")
    for _ in range(5):
        r = client.post("/api/v1/auth/login", json={"email": "cs26mt051@iitdh.ac.in", "password": "wrong"})
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = client.post("/api/v1/auth/login", json={"email": "cs26mt051@iitdh.ac.in", "password": "secret pass"})
    assert r.status_code == 429  # the email-and-IP pair is paused, even with the right password
    assert sleeps  # failed attempts are slowed down


def test_pause_ends_after_15_minutes(client, db, clock):
    make_user(db, "student", email="cs26mt052@iitdh.ac.in", password="secret pass")
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "cs26mt052@iitdh.ac.in", "password": "wrong"})
    clock.advance(minutes=16)
    r = client.post("/api/v1/auth/login", json={"email": "cs26mt052@iitdh.ac.in", "password": "secret pass"})
    assert r.status_code == 200


def test_expired_or_revoked_session(client, db, clock):
    person = make_user(db, "student")
    raw = create_session(db, person.user, clock.now(), days=7)
    db.commit()
    client.cookies.set("unison_session", raw)
    assert client.get("/api/v1/users/me").status_code == 200
    clock.advance(days=8)
    r = client.get("/api/v1/users/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "SESSION_EXPIRED"


def test_forgot_and_reset_password(client, db, clock):
    make_user(db, "student", email="cs26mt053@iitdh.ac.in", password="old password")
    r = client.post("/api/v1/auth/password-reset-requests", json={"email": "cs26mt053@iitdh.ac.in"})
    assert r.status_code == 202
    assert client.post("/api/v1/auth/password-reset-requests", json={"email": "unknown@iitdh.ac.in"}).status_code == 202
    raw = db.scalar(select(EmailOutbox).where(EmailOutbox.template == "reset_password")).payload["token"]
    r = client.post("/api/v1/auth/password-resets", json={"token": raw, "new_password": "new password"})
    assert r.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "cs26mt053@iitdh.ac.in", "password": "new password"}
        ).status_code
        == 200
    )
    again = client.post("/api/v1/auth/password-resets", json={"token": raw, "new_password": "another one"})
    assert again.json()["error"]["code"] == "INVALID_TOKEN"


def test_reset_link_expires_after_30_minutes(client, db, clock):
    make_user(db, "student", email="cs26mt054@iitdh.ac.in", password="old password")
    client.post("/api/v1/auth/password-reset-requests", json={"email": "cs26mt054@iitdh.ac.in"})
    raw = db.scalar(select(EmailOutbox).where(EmailOutbox.template == "reset_password")).payload["token"]
    clock.advance(minutes=31)
    r = client.post("/api/v1/auth/password-resets", json={"token": raw, "new_password": "new password"})
    assert r.json()["error"]["code"] == "INVALID_TOKEN"
    token = db.scalar(select(EmailToken))
    assert token.expires_at - token.expires_at.replace(minute=0, second=0, microsecond=0) is not None


def test_first_admin_must_change_password(client, db):
    person = make_user(db, "admin", email="admin@example.com", password="unison-admin")
    person.user.must_change_password = True
    db.commit()
    client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "unison-admin"})
    r = client.get("/api/v1/admin/stats")
    assert r.status_code == 403 and r.json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    assert client.get("/api/v1/users/me").json()["must_change_password"] is True
    r = client.put(
        "/api/v1/users/me/password",
        headers=CSRF,
        json={"current_password": "unison-admin", "new_password": "a much better one"},
    )
    assert r.status_code == 204
    assert client.get("/api/v1/admin/stats").status_code == 200


def test_suspended_user_cannot_log_in(client, db):
    person = make_user(db, "student", email="cs26mt055@iitdh.ac.in", password="secret pass")
    person.user.status = "suspended"
    db.commit()
    r = client.post("/api/v1/auth/login", json={"email": "cs26mt055@iitdh.ac.in", "password": "secret pass"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"


def test_auth_config_and_google_off(client):
    cfg = client.get("/api/v1/auth/config").json()
    assert cfg == {
        "google_enabled": False,
        "allowed_email_domain": "iitdh.ac.in",
        "auth_mode": "demo",
        "csrf_header": "X-Unison-Client",
    }
    r = client.get("/api/v1/auth/google", follow_redirects=False)
    assert r.status_code == 503 and r.json()["error"]["code"] == "GOOGLE_NOT_CONFIGURED"


def test_google_sign_in_links_and_creates(db, clock):
    from app.core.errors import AppError
    from app.modules.auth.service import google_sign_in

    existing = make_user(db, "student", email="cs26mt056@iitdh.ac.in")
    user, raw = google_sign_in(
        db, subject="g-1", email="cs26mt056@iitdh.ac.in", email_verified=True, name="X", clock=clock, session_days=7
    )
    assert user.id == existing.id and raw
    new, _ = google_sign_in(
        db,
        subject="g-2",
        email="cs26mt057@iitdh.ac.in",
        email_verified=True,
        name="Google Person",
        clock=clock,
        session_days=7,
    )
    assert new.role == "student" and new.password_hash is None
    for kwargs, code in [
        ({"subject": "g-3", "email": "x@gmail.com", "email_verified": True}, "EMAIL_DOMAIN_NOT_ALLOWED"),
        ({"subject": "g-4", "email": "cs26mt058@iitdh.ac.in", "email_verified": False}, "GOOGLE_EMAIL_NOT_VERIFIED"),
    ]:
        try:
            google_sign_in(db, name="n", clock=clock, session_days=7, **kwargs)
            raise AssertionError("should fail")
        except AppError as exc:
            assert exc.code == code
    assert db.get(User, new.id).name == "Google Person"
    assert timedelta(days=7)
