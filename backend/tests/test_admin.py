"""The admin console: roles, suspension, audit log, settings and statistics."""

from datetime import timedelta

from sqlalchemy import select

from app.modules.admin.models import AuditLog
from tests.conftest import as_user
from tests.factories import make_course, make_user


def test_roles_suspend_audit_and_settings(client, db):
    admin, student = make_user(db, "admin"), make_user(db)
    assert client.get("/api/v1/admin/stats", headers=as_user(student)).status_code == 403
    r = client.patch(f"/api/v1/admin/users/{student.id}", json={"role": "teacher"}, headers=as_user(admin))
    assert r.json()["role"] == "teacher"
    assert (
        client.patch(f"/api/v1/admin/users/{admin.id}", json={"role": "student"}, headers=as_user(admin)).json()[
            "error"
        ]["code"]
        == "LAST_ADMIN"
    )
    r = client.patch(f"/api/v1/admin/users/{student.id}", json={"status": "suspended"}, headers=as_user(admin))
    assert r.json()["status"] == "suspended"
    assert client.get("/api/v1/users/me", headers=as_user(student)).json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    assert (
        client.patch(f"/api/v1/admin/users/{student.id}", json={"status": "active"}, headers=as_user(admin)).json()[
            "status"
        ]
        == "active"
    )
    log = client.get("/api/v1/admin/audit-entries?action=role_changed", headers=as_user(admin)).json()
    assert log["total"] == 1 and log["items"][0]["after"] == {"role": "teacher"}
    detail = client.get(f"/api/v1/admin/users/{student.id}", headers=as_user(admin)).json()
    assert detail["emails"][0]["email"] == student.email

    settings = client.get("/api/v1/admin/settings", headers=as_user(admin)).json()["items"]
    assert {s["key"] for s in settings} >= {"allowed_email_domain", "ai_requests_per_submission"}
    r = client.put("/api/v1/admin/settings/join_requests_per_day", json={"value": 3}, headers=as_user(admin))
    assert r.json()["value"] == 3
    assert (
        client.put(
            "/api/v1/admin/settings/join_requests_per_day", json={"value": "x"}, headers=as_user(admin)
        ).status_code
        == 400
    )
    assert client.put("/api/v1/admin/settings/nope", json={"value": 1}, headers=as_user(admin)).status_code == 404
    assert db.scalar(select(AuditLog).where(AuditLog.action == "setting_changed")) is not None


def test_stats_and_courses_without_teacher(client, db):
    admin, teacher = make_user(db, "admin"), make_user(db, "teacher")
    make_course(db, teacher)
    leaver = make_user(db, "teacher")
    orphan = make_course(db, leaver)
    leaver.user.status = "deactivated"  # e.g. the only teacher is deleting their account
    db.commit()
    stats = client.get("/api/v1/admin/stats", headers=as_user(admin)).json()
    assert stats["courses"] >= 2 and stats["courses_without_teacher"] >= 1
    ids = [
        c["id"]
        for c in client.get("/api/v1/admin/courses?without_teacher=true", headers=as_user(admin)).json()["items"]
    ]
    assert orphan.id in ids


def test_staff_invitation_list_and_cancel(client, db):
    admin = make_user(db, "admin")
    inv = client.post(
        "/api/v1/admin/staff-invitations", json={"email": "t@example.com", "role": "teacher"}, headers=as_user(admin)
    ).json()
    assert client.get("/api/v1/admin/staff-invitations", headers=as_user(admin)).json()["total"] == 1
    assert client.delete(f"/api/v1/invitations/{inv['id']}", headers=as_user(admin)).status_code == 204
    assert timedelta(days=1)
