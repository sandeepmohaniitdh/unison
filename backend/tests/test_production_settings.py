"""The production safety check and the SMTP login used on a real server."""

import pytest

from app.config import Settings
from app.core import mailer as mailer_module
from app.core.mailer import SmtpMailer

SAFE = dict(
    app_env="production",
    auth_mode="session",
    secret_key="x" * 40,
    cookie_secure=True,
    frontend_url="https://unison.example.org",
    api_url="https://unison.example.org",
    admin_password="a long admin password",
    seed_on_start=False,
)


def test_development_settings_are_never_blocked():
    assert Settings().production_problems() == []
    Settings().check_production()


def test_safe_production_settings_pass():
    assert Settings(**SAFE).production_problems() == []


@pytest.mark.parametrize(
    ("change", "word"),
    [
        ({"auth_mode": "demo"}, "AUTH_MODE"),
        ({"secret_key": "dev-secret-change-me"}, "SECRET_KEY"),
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"cookie_secure": False}, "COOKIE_SECURE"),
        ({"frontend_url": "http://unison.example.org"}, "https://"),
        ({"admin_password": "unison-admin"}, "ADMIN_PASSWORD"),
        ({"seed_on_start": True}, "SEED_ON_START"),
    ],
)
def test_each_unsafe_production_setting_is_reported(change, word):
    settings = Settings(**{**SAFE, **change})
    problems = settings.production_problems()
    assert len(problems) == 1 and word in problems[0]
    with pytest.raises(RuntimeError, match=word):
        settings.check_production()


def test_settings_read_booleans_from_the_environment(monkeypatch):
    monkeypatch.setenv("SMTP_STARTTLS", "true")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    s = Settings.from_env()
    assert s.smtp_starttls is True and s.cookie_secure is False


class FakeSMTP:
    calls: list = []

    def __init__(self, host, port, timeout):
        FakeSMTP.calls = [("connect", host, port)]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        FakeSMTP.calls.append(("starttls",))

    def login(self, user, password):
        FakeSMTP.calls.append(("login", user, password))

    def send_message(self, msg):
        FakeSMTP.calls.append(("send", msg["To"], msg["Subject"]))


def test_smtp_mailer_logs_in_over_starttls(monkeypatch):
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", FakeSMTP)
    SmtpMailer("smtp.example.org", 587, "Unison <no-reply@example.org>", "apikey", "secret", starttls=True).send(
        "cs26mt001@iitdh.ac.in", "Hello", "Body"
    )
    assert FakeSMTP.calls == [
        ("connect", "smtp.example.org", 587),
        ("starttls",),
        ("login", "apikey", "secret"),
        ("send", "cs26mt001@iitdh.ac.in", "Hello"),
    ]


def test_smtp_mailer_without_login_for_mailpit(monkeypatch):
    monkeypatch.setattr(mailer_module.smtplib, "SMTP", FakeSMTP)
    SmtpMailer("mailpit", 1025, "Unison <no-reply@unison.local>").send("a@iitdh.ac.in", "Hi", "Body")
    assert [c[0] for c in FakeSMTP.calls] == ["connect", "send"]
