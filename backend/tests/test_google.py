"""Google sign-in and Google-only accounts."""

from urllib.parse import parse_qs, urlparse

from app.config import Settings, get_settings
from app.modules.auth import google
from tests.factories import make_user


def _google_settings():
    return Settings(
        google_client_id="client-1",
        google_client_secret="secret",
        cookie_secure=False,
        frontend_url="http://localhost:8080",
        api_url="http://localhost:8000",
    )


def test_google_start_and_callback(app, client, db, monkeypatch):
    app.dependency_overrides[get_settings] = _google_settings
    r = client.get("/api/v1/auth/google?return_to=/courses", follow_redirects=False)
    assert r.status_code == 302
    url = urlparse(r.headers["location"])
    query = parse_qs(url.query)
    assert url.netloc == "accounts.google.com" and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/v1/auth/google/callback"]
    state = query["state"][0]

    monkeypatch.setattr(google, "exchange_code", lambda settings, code, verifier: "id-token")
    monkeypatch.setattr(
        google,
        "verify_id_token",
        lambda settings, token, nonce: {
            "sub": "google-123",
            "email": "cs26mt090@iitdh.ac.in",
            "email_verified": True,
            "name": "Google Student",
        },
    )
    r = client.get(f"/api/v1/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "http://localhost:8080/courses"
    assert "unison_session" in r.cookies
    me = client.get("/api/v1/users/me").json()
    assert me["name"] == "Google Student" and me["google_linked"] is True and me["has_password"] is False

    # The state cookie is used up, so the same callback cannot be replayed.
    replay = client.get(f"/api/v1/auth/google/callback?code=abc&state={state}", follow_redirects=False)
    assert replay.json()["error"]["code"] == "GOOGLE_STATE_MISSING"
    client.get("/api/v1/auth/google", follow_redirects=False)
    forged = client.get("/api/v1/auth/google/callback?code=abc&state=forged", follow_redirects=False)
    assert forged.json()["error"]["code"] == "GOOGLE_STATE_INVALID"


def test_google_only_account_deletion_needs_fresh_sign_in(client, db, clock):
    from app.modules.auth.service import create_session

    person = make_user(db)  # no password
    raw = create_session(db, person.user, clock.now(), 7)
    db.commit()
    client.cookies.set("unison_session", raw)
    clock.advance(minutes=30)
    r = client.post("/api/v1/users/me/deletion", json={}, headers={"X-Unison-Client": "web"})
    assert r.json()["error"]["code"] == "REAUTH_REQUIRED"
