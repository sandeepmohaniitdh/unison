"""FastAPI dependencies: the database session, the clock and file storage.

Everything here can be replaced in tests with app.dependency_overrides.
"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.storage import LocalStorage
from app.core.time import Clock
from app.db import get_session_factory


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


_clock = Clock()


def get_clock() -> Clock:
    return _clock


def get_storage(settings: Annotated[Settings, Depends(get_settings)]) -> LocalStorage:
    return LocalStorage(settings.upload_dir)


DB = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ClockDep = Annotated[Clock, Depends(get_clock)]
StorageDep = Annotated[LocalStorage, Depends(get_storage)]


def client_ip(request: Request, settings: Settings) -> str:
    """The caller's IP address, used for rate limits.

    X-Forwarded-For is only trusted behind our own nginx (TRUST_PROXY=true),
    because anyone can send that header.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if settings.trust_proxy and forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "127.0.0.1"
