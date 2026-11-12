"""Settings, read from environment variables.

Every setting has a default, so a fresh clone runs with no .env file.
The environment variable for a setting is its name in capitals, for example
DATABASE_URL or AUTH_MODE.
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel


class Settings(BaseModel):
    app_env: str = "development"
    database_url: str = "mysql+pymysql://unison:unison@db:3306/unison?charset=utf8mb4"

    # "session": only the session cookie counts (the real login).
    # "demo": an X-Demo-User header with a user's email also works, so the API
    # can be tried in Swagger. Never use "demo" on a public server.
    auth_mode: Literal["session", "demo"] = "session"
    cookie_secure: bool = True
    session_days: int = 7
    secret_key: str = "dev-secret-change-me"

    # Where people open the site (links in emails) and where the API answers.
    frontend_url: str = "http://localhost:8080"
    api_url: str = "http://localhost:8000"
    # True only when nginx sits in front and sets X-Forwarded-For.
    trust_proxy: bool = False

    # The first administrator, created on the first start.
    admin_email: str = "admin@example.com"
    admin_password: str = "unison-admin"
    admin_name: str = "Platform Admin"

    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "Unison <no-reply@unison.local>"
    # A real mail service (for example Brevo, SendGrid or Gmail) needs a login and STARTTLS.
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False

    upload_dir: str = "/data/uploads"

    # Google sign-in is optional: empty values switch it off.
    google_client_id: str = ""
    google_client_secret: str = ""

    # AI feedback drafts: "none" switches the feature off.
    ai_provider: Literal["none", "gemini", "ollama", "fake"] = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    # Used when the main model is overloaded (HTTP 503), too slow or out of quota. Empty: no fallback.
    gemini_fallback_model: str = "gemini-flash-lite-latest"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b"
    # Thinking models (gemini-flash-latest) often need more than 15 s for a whole report.
    ai_timeout_seconds: float = 60.0

    seed_on_start: bool = True
    worker_interval_seconds: int = 30
    worker_heartbeat_file: str = "/tmp/unison-worker-heartbeat"

    def production_problems(self) -> list[str]:
        """Settings that are fine on a laptop but unsafe on a public server.

        Only checked when APP_ENV=production; the services refuse to start until
        every problem is fixed.
        """
        if self.app_env != "production":
            return []
        problems = []
        if self.auth_mode != "session":
            problems.append("AUTH_MODE must be session (demo lets anyone log in with a header).")
        if self.secret_key == "dev-secret-change-me" or len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be a long random value (at least 32 characters).")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (the site must use HTTPS).")
        if not self.frontend_url.startswith("https://") or not self.api_url.startswith("https://"):
            problems.append("FRONTEND_URL and API_URL must start with https://.")
        if self.admin_password == "unison-admin":
            problems.append("ADMIN_PASSWORD must not be the demo password.")
        if self.seed_on_start:
            problems.append("SEED_ON_START must be false (no demo data on a real site).")
        return problems

    def check_production(self) -> None:
        problems = self.production_problems()
        if problems:
            raise RuntimeError("Unsafe settings for APP_ENV=production:\n- " + "\n- ".join(problems))

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def ai_enabled(self) -> bool:
        if self.ai_provider == "gemini":
            return bool(self.gemini_api_key)
        return self.ai_provider in ("ollama", "fake")

    @classmethod
    def from_env(cls) -> "Settings":
        values = {}
        for name in cls.model_fields:
            env = os.environ.get(name.upper())
            if env is not None:
                values[name] = env
        return cls(**values)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
