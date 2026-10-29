"""Google sign-in: OpenID Connect authorisation code flow with PKCE.

1. /auth/google/start makes a random state, nonce and PKCE verifier, keeps
   them in a short-lived signed cookie, and redirects to Google.
2. Google redirects back to /auth/google/callback with a code.
3. We check the state, exchange the code (with the verifier) for tokens, and
   check the ID token's signature, issuer, audience, expiry and nonce.
"""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx
import jwt
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import Settings
from app.core.errors import bad_request, unavailable

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
ISSUERS = ["https://accounts.google.com", "accounts.google.com"]
STATE_COOKIE = "unison_google_state"
STATE_MAX_AGE = 600

_jwks_client = jwt.PyJWKClient(JWKS_URL, cache_keys=True)


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt="google-oidc")


def redirect_uri(settings: Settings) -> str:
    return settings.api_url.rstrip("/") + "/api/v1/auth/google/callback"


def start(settings: Settings, return_to: str) -> tuple[str, str]:
    """Returns (URL to send the browser to, signed value for the state cookie)."""
    if not settings.google_enabled:
        raise unavailable("GOOGLE_NOT_CONFIGURED", "Google sign-in is not set up on this server.")
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri(settings),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    cookie = _serializer(settings).dumps({"state": state, "nonce": nonce, "verifier": verifier, "return_to": return_to})
    return f"{AUTH_URL}?{query}", cookie


def read_state_cookie(settings: Settings, cookie: str | None, state: str) -> dict:
    if not cookie:
        raise bad_request("GOOGLE_STATE_MISSING", "The sign-in took too long or cookies are blocked. Try again.")
    try:
        data = _serializer(settings).loads(cookie, max_age=STATE_MAX_AGE)
    except BadSignature as exc:
        raise bad_request("GOOGLE_STATE_INVALID", "The sign-in could not be checked. Try again.") from exc
    if not secrets.compare_digest(data["state"], state):
        raise bad_request("GOOGLE_STATE_INVALID", "The sign-in could not be checked. Try again.")
    return data


def exchange_code(settings: Settings, code: str, verifier: str) -> str:
    """Swap the code for tokens; returns the ID token."""
    response = httpx.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri(settings),
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise bad_request("GOOGLE_EXCHANGE_FAILED", "Google did not accept the sign-in. Try again.")
    return response.json()["id_token"]


def verify_id_token(settings: Settings, id_token: str, nonce: str) -> dict:
    """Check signature, issuer, audience, expiry and nonce. Returns the claims."""
    try:
        key = _jwks_client.get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer=ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise bad_request("GOOGLE_TOKEN_INVALID", "Google's answer could not be verified.") from exc
    if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
        raise bad_request("GOOGLE_TOKEN_INVALID", "Google's answer could not be verified.")
    return claims
