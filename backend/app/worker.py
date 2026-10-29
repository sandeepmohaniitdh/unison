"""The background worker: `python -m app.worker`.

Every 30 seconds it runs each job once, in its own database session, using
MySQL as the queue (SELECT ... FOR UPDATE SKIP LOCKED). It touches a
heartbeat file after every round; the Docker healthcheck reads it.
"""

import logging
import time
from pathlib import Path

from app.config import Settings, get_settings
from app.core.mailer import Mailer, SmtpMailer
from app.core.storage import LocalStorage
from app.core.time import Clock
from app.db import get_session_factory
from app.modules.ai import service as ai
from app.modules.ai.providers import get_provider
from app.modules.invitations.service import expire_invitations
from app.modules.notifications.service import send_outbox
from app.modules.submissions.service import apply_due_deadlines
from app.modules.users.service import finalise_deletions

log = logging.getLogger("unison.worker")


def run_once(settings: Settings, mailer: Mailer, clock: Clock, storage: LocalStorage, provider) -> dict:
    """One round of every job. Returns how much each job did (for logs and tests)."""
    jobs = {
        "deadlines": lambda db: apply_due_deadlines(db, clock),
        "invitations_expired": lambda db: expire_invitations(db, clock),
        "emails_sent": lambda db: send_outbox(db, mailer, clock),
        "ai_drafts": lambda db: ai.run_jobs(db, storage, provider, clock),
        "accounts_deleted": lambda db: finalise_deletions(db, storage, clock),
    }
    done = {}
    for name, job in jobs.items():
        db = get_session_factory()()
        try:
            done[name] = job(db)
        except Exception:  # noqa: BLE001 - one failing job must not stop the others
            db.rollback()
            log.exception("Job %s failed", name)
            done[name] = -1
        finally:
            db.close()
    return done


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    mailer = SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_from)
    storage = LocalStorage(settings.upload_dir)
    provider = get_provider(settings)
    clock = Clock()
    heartbeat = Path(settings.worker_heartbeat_file)
    log.info("Worker started (every %s s, AI provider: %s)", settings.worker_interval_seconds, settings.ai_provider)
    while True:
        done = run_once(settings, mailer, clock, storage, provider)
        if any(v for v in done.values()):
            log.info("Round: %s", done)
        heartbeat.write_text(str(time.time()))
        time.sleep(settings.worker_interval_seconds)


if __name__ == "__main__":
    main()
