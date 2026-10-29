"""The `init` service: `python -m app.bootstrap`.

Runs once on every `docker compose up`, before the backend and worker start:
1. waits for MySQL,
2. applies the Alembic migrations,
3. adds default platform settings,
4. creates the first administrator from ADMIN_EMAIL and ADMIN_PASSWORD
   (who must change the password at first login),
5. loads the seed data, if SEED_ON_START is true (the seed skips itself if data is there).
"""

import logging
import time
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select, text

from alembic import command
from app.config import get_settings
from app.core.storage import LocalStorage
from app.core.time import utcnow
from app.db import get_engine, get_session_factory
from app.modules.admin.service import audit, ensure_default_settings
from app.modules.users import service as users
from app.modules.users.models import User

log = logging.getLogger("unison.init")
BACKEND_DIR = Path(__file__).resolve().parent.parent


def wait_for_database(seconds: int = 90) -> None:
    deadline = time.time() + seconds
    while True:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001
            if time.time() > deadline:
                raise
            log.info("Waiting for the database: %s", exc.__class__.__name__)
            time.sleep(2)


def migrate() -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


def ensure_first_admin() -> bool:
    settings = get_settings()
    db = get_session_factory()()
    try:
        ensure_default_settings(db)
        if db.scalar(select(User.id).where(User.role == "admin")) is not None:
            db.commit()
            return False
        now = utcnow()
        admin = users.create_user(
            db,
            name=settings.admin_name,
            email=settings.admin_email,
            role="admin",
            password=settings.admin_password,
            now=now,
            verified=True,
            must_change_password=True,
        )
        audit(db, admin, "first_admin_created", "users", admin.id, after={"email": settings.admin_email})
        db.commit()
        log.info("Created the first administrator %s (must change the password at first login)", settings.admin_email)
        return True
    finally:
        db.close()


def seed_if_empty() -> None:
    from app.seed.run import seed

    settings = get_settings()
    if not settings.seed_on_start:
        return
    db = get_session_factory()()
    try:
        seed(db, LocalStorage(settings.upload_dir))
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    wait_for_database()
    migrate()
    logging.getLogger().setLevel(logging.INFO)  # Alembic's logging setup lowers it
    ensure_first_admin()
    seed_if_empty()
    log.info("Init finished.")


if __name__ == "__main__":
    main()
