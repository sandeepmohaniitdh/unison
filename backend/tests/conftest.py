"""Test setup.

Tests run against a real MySQL database whose name ends in _test
(TEST_DATABASE_URL), because row locks and generated columns behave
differently in SQLite. Each test runs inside one transaction that is rolled
back at the end, so tests never see each other's data. The services' own
commits become savepoints inside that transaction.

Replaced for tests: the clock (frozen, so tests can jump past deadlines),
and file storage (a temporary folder).
"""

import os
import tempfile
from datetime import datetime

import pytest

UPLOADS = tempfile.mkdtemp(prefix="unison-test-uploads-")
os.environ.setdefault("TEST_DATABASE_URL", "mysql+pymysql://unison:unison@db:3306/unison_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["AUTH_MODE"] = "demo"
os.environ["COOKIE_SECURE"] = "false"
os.environ["UPLOAD_DIR"] = UPLOADS
os.environ["AI_PROVIDER"] = "fake"
os.environ["SEED_ON_START"] = "false"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.deps import get_clock, get_db, get_storage  # noqa: E402
from app.core.storage import LocalStorage  # noqa: E402
from app.core.time import FrozenClock  # noqa: E402
from app.db import Base, make_engine  # noqa: E402
from app.main import create_app  # noqa: E402

START = datetime(2026, 11, 2, 4, 30)  # 10:00 IST on Monday 2 November 2026


def _check_test_database(url: str) -> None:
    if not url.startswith("mysql"):
        raise RuntimeError("The tests need MySQL (see TEST_DATABASE_URL).")
    name = url.rsplit("/", 1)[-1].split("?")[0]
    if not name.endswith("_test"):
        raise RuntimeError(f"Refusing to run tests on '{name}': the database name must end in _test.")


@pytest.fixture(scope="session")
def engine():
    url = os.environ["TEST_DATABASE_URL"]
    _check_test_database(url)
    eng = make_engine(url)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture
def clock():
    return FrozenClock(START)


@pytest.fixture
def storage():
    return LocalStorage(UPLOADS)


@pytest.fixture
def app(db, clock, storage):
    application = create_app()
    application.dependency_overrides[get_db] = lambda: db
    application.dependency_overrides[get_clock] = lambda: clock
    application.dependency_overrides[get_storage] = lambda: storage
    return application


@pytest.fixture
def client(app):
    return TestClient(app)
