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

    upload_dir: str = "/data/uploads"

    # Google sign-in is optional: empty values switch it off.
    google_client_id: str = ""
    google_client_secret: str = ""

    # AI feedback drafts: "none" switches the feature off.
    ai_provider: Literal["none", "gemini", "ollama", "fake"] = "none"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b"
    ai_timeout_seconds: float = 15.0

    seed_on_start: bool = True
    worker_interval_seconds: int = 30
    worker_heartbeat_file: str = "/tmp/unison-worker-heartbeat"

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
