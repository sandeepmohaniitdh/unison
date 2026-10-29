"""One round of the background worker."""

from app import worker
from app.config import get_settings
from app.core.mailer import FakeMailer
from app.modules.ai.providers import FakeProvider
from app.modules.notifications.service import queue_email
from tests.factories import NoCloseSession


def test_worker_round_runs_every_job(db, clock, storage, monkeypatch):
    monkeypatch.setattr(worker, "get_session_factory", lambda: NoCloseSession(db))
    queue_email(
        db,
        to="x@example.com",
        template="notification",
        payload={"name": "X", "title": "Hi", "link": "/"},
        dedup_key="w1",
        now=clock.now(),
    )
    db.commit()
    mailer = FakeMailer()
    done = worker.run_once(get_settings(), mailer, clock, storage, FakeProvider())
    assert done == {"deadlines": 0, "invitations_expired": 0, "emails_sent": 1, "ai_drafts": 0, "accounts_deleted": 0}
    assert mailer.sent[0]["to"] == "x@example.com"
