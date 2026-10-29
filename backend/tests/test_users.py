"""Profile, emails, data download and account deletion."""

from sqlalchemy import select

from app.modules.notifications.models import Notification
from app.modules.users.models import User, UserEmail
from app.modules.users.service import finalise_deletions
from tests.conftest import as_user
from tests.factories import enrol, make_course, make_user


def test_profile_and_second_email(client, db):
    student = make_user(db)
    r = client.post("/api/v1/users/me/emails", json={"email": "Personal@Example.com"}, headers=as_user(student))
    assert r.status_code == 201 and r.json() == {
        "id": r.json()["id"],
        "email": "personal@example.com",
        "is_primary": False,
        "verified": False,
    }
    second = r.json()["id"]
    assert (
        client.post("/api/v1/users/me/emails", json={"email": "third@example.com"}, headers=as_user(student)).json()[
            "error"
        ]["code"]
        == "EMAIL_LIMIT"
    )
    assert (
        client.patch(f"/api/v1/users/me/emails/{second}", json={"is_primary": True}, headers=as_user(student)).json()[
            "error"
        ]["code"]
        == "EMAIL_NOT_VERIFIED"
    )
    db.get(UserEmail, second).verified_at = db.get(User, student.id).created_at
    db.commit()
    me = client.patch(f"/api/v1/users/me/emails/{second}", json={"is_primary": True}, headers=as_user(student)).json()
    assert [e["email"] for e in me["emails"] if e["is_primary"]] == ["personal@example.com"]
    old = next(e["id"] for e in me["emails"] if not e["is_primary"])
    assert (
        client.delete(f"/api/v1/users/me/emails/{second}", headers=as_user(student)).json()["error"]["code"]
        == "PRIMARY_EMAIL"
    )
    assert client.delete(f"/api/v1/users/me/emails/{old}", headers=as_user("personal@example.com")).status_code == 204


def test_data_export(client, db):
    student = make_user(db, name="Export Me")
    r = client.get("/api/v1/users/me/personal-data", headers=as_user(student))
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    assert r.json()["profile"]["name"] == "Export Me" and r.json()["emails"] == [student.email]


def test_account_deletion_grace_and_finalise(client, db, clock, storage):
    teacher = make_user(db, "teacher")
    student = make_user(db, password="my password")
    course = make_course(db, teacher)
    enrol(db, course, student)
    preview = client.get("/api/v1/users/me/deletion", headers=as_user(student)).json()
    assert preview == {"running_courses": 1, "active_teams": 0, "grace_days": 7, "can_delete": True}
    assert (
        client.post("/api/v1/users/me/deletion", json={"password": "wrong"}, headers=as_user(student)).status_code
        == 403
    )
    r = client.post("/api/v1/users/me/deletion", json={"password": "my password"}, headers=as_user(student))
    assert r.status_code == 202 and r.json()["status"] == "deactivated"
    assert client.get("/api/v1/users/me", headers=as_user(student)).status_code == 401
    # Logging in within 7 days cancels it
    assert (
        client.post("/api/v1/auth/login", json={"email": student.email, "password": "my password"}).status_code == 200
    )
    assert db.get(User, student.id).status == "active"
    client.cookies.clear()
    client.post("/api/v1/users/me/deletion", json={"password": "my password"}, headers=as_user(student))
    clock.advance(days=8)
    assert finalise_deletions(db, storage, clock) == 1
    user = db.get(User, student.id)
    assert (user.name, user.status, user.password_hash) == ("Former member", "deleted", None)
    assert db.scalar(select(UserEmail).where(UserEmail.user_id == student.id)) is None
    assert db.scalar(select(Notification).where(Notification.user_id == student.id)) is None


def test_last_admin_cannot_delete(client, db):
    admin = make_user(db, "admin", password="admin pass")
    r = client.post("/api/v1/users/me/deletion", json={"password": "admin pass"}, headers=as_user(admin))
    assert r.json()["error"]["code"] == "LAST_ADMIN"
