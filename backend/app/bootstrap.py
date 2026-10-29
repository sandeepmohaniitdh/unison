"""The `init` service: `python -m app.bootstrap`.

Runs once on every `docker compose up`, before the backend starts:
1. waits for MySQL,
2. applies the Alembic migrations.
"""

import logging
import time
from pathlib import Path

from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db import get_engine

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


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    wait_for_database()
    migrate()
    logging.getLogger().setLevel(logging.INFO)  # Alembic's logging setup lowers it
    log.info("Init finished.")


if __name__ == "__main__":
    main()
