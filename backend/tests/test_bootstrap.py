"""The init job: first administrator and default settings."""

from sqlalchemy import func, select

from app import bootstrap
from app.modules.admin.models import PlatformSetting
from app.modules.users.models import User
from tests.factories import NoCloseSession


def test_first_admin_is_created_once(db, monkeypatch):
    monkeypatch.setattr(bootstrap, "get_session_factory", lambda: NoCloseSession(db))
    assert bootstrap.ensure_first_admin() is True
    admin = db.scalar(select(User).where(User.role == "admin"))
    assert admin.must_change_password is True
    assert db.scalar(select(func.count()).select_from(PlatformSetting)) == 5
    assert bootstrap.ensure_first_admin() is False
