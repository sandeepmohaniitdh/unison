"""Notifications, email rules and preferences, the outbox and dashboards."""

from sqlalchemy import select

from app.core.mailer import FakeMailer
from app.modules.notifications.models import EmailOutbox
from app.modules.notifications.service import notify, send_outbox
from tests.conftest import as_user
from tests.factories import enrol, make_assignment, make_course, make_user


def test_notify_writes_in_app_and_email_and_respects_switches(client, db, clock):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    notify(
        db, "assignment_published", [student.id], "New assignment", "/assignments/1", clock.now(), course_id=course.id
    )
    db.commit()
    assert client.get("/api/v1/notifications/unread-count", headers=as_user(student)).json() == {"unread": 1}
    assert db.scalar(select(EmailOutbox).where(EmailOutbox.user_id == student.id)) is not None
    # Turn that email type off
    r = client.put(
        "/api/v1/users/me/notification-preferences",
        headers=as_user(student),
        json={"items": [{"event_type": "assignment_published", "email_enabled": False}]},
    )
    assert r.status_code == 204
    prefs = client.get("/api/v1/users/me/notification-preferences", headers=as_user(student)).json()["items"]
    assert next(p for p in prefs if p["event_type"] == "assignment_published")["email_enabled"] is False
    notify(db, "assignment_published", [student.id], "Another", "/assignments/2", clock.now(), course_id=course.id)
    db.commit()
    assert len(list(db.scalars(select(EmailOutbox).where(EmailOutbox.user_id == student.id)))) == 1
    assert client.get("/api/v1/notifications", headers=as_user(student)).json()["total"] == 2
    bad = client.put(
        "/api/v1/users/me/notification-preferences",
        headers=as_user(student),
        json={"items": [{"event_type": "draft_uploaded", "email_enabled": False}]},
    )
    assert bad.json()["error"]["code"] == "UNKNOWN_EVENT_TYPE"


def test_course_rules(client, db, clock):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    r = client.put(
        f"/api/v1/courses/{course.id}/notification-rules",
        headers=as_user(teacher),
        json={"items": [{"event_type": "final_submitted", "email_members": False, "email_teachers": True}]},
    )
    assert r.status_code == 204
    rules = client.get(f"/api/v1/courses/{course.id}/notification-rules", headers=as_user(teacher)).json()["items"]
    assert next(x for x in rules if x["event_type"] == "final_submitted")["email_members"] is False
    notify(db, "final_submitted", [student.id, teacher.id], "Final", "/teams/1", clock.now(), course_id=course.id)
    db.commit()
    to = {e.user_id for e in db.scalars(select(EmailOutbox))}
    assert to == {teacher.id}
    assert client.get(f"/api/v1/courses/{course.id}/notification-rules", headers=as_user(student)).status_code == 403


def test_mark_read(client, db, clock):
    student = make_user(db)
    for i in range(3):
        notify(db, "draft_uploaded", [student.id], f"N{i}", "/x", clock.now())
    db.commit()
    first = client.get("/api/v1/notifications", headers=as_user(student)).json()["items"][0]["id"]
    assert (
        client.patch(f"/api/v1/notifications/{first}", json={"read": True}, headers=as_user(student)).status_code == 200
    )
    assert client.get("/api/v1/notifications?unread_only=true", headers=as_user(student)).json()["total"] == 2
    assert client.patch("/api/v1/notifications", json={"read": True}, headers=as_user(student)).json() == {"marked": 2}
    other = make_user(db)
    assert (
        client.patch(f"/api/v1/notifications/{first}", json={"read": True}, headers=as_user(other)).status_code == 404
    )


def test_outbox_sends_retries_and_forgets_tokens(db, clock):
    from app.modules.notifications.service import queue_email

    queue_email(
        db,
        to="a@example.com",
        template="verify_email",
        payload={"name": "A", "email": "a@example.com", "token": "secret-token"},
        dedup_key="t1",
        now=clock.now(),
    )
    queue_email(
        db,
        to="a@example.com",
        template="verify_email",
        payload={"name": "A", "email": "a@example.com", "token": "secret-token"},
        dedup_key="t1",
        now=clock.now(),
    )
    db.commit()
    mailer = FakeMailer()
    assert send_outbox(db, mailer, clock) == 1  # the duplicate was never queued
    assert "secret-token" in mailer.sent[0]["body"]
    row = db.scalar(select(EmailOutbox))
    assert row.status == "sent" and row.payload["token"] != "secret-token"

    class Broken(FakeMailer):
        def send(self, *a):
            raise OSError("SMTP down")

    queue_email(
        db,
        to="b@example.com",
        template="notification",
        payload={"name": "B", "title": "T", "link": "/"},
        dedup_key="t2",
        now=clock.now(),
    )
    db.commit()
    for _ in range(5):
        send_outbox(db, Broken(), clock)
        clock.advance(minutes=61)
    failed = db.scalar(select(EmailOutbox).where(EmailOutbox.dedup_key == "t2"))
    assert failed.status == "failed" and failed.attempts == 5


def test_dashboards(client, db, clock):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    make_assignment(db, course, teacher, kind="individual")
    s = client.get("/api/v1/dashboards/student", headers=as_user(student)).json()
    assert len(s["courses"]) == 1 and s["upcoming_deadlines"][0]["state"] == "no_work"
    t = client.get("/api/v1/dashboards/teacher", headers=as_user(teacher)).json()
    assert t["courses"][0]["students"] == 1 and len(t["assignments"]) == 1
    assert client.get("/api/v1/dashboards/teacher", headers=as_user(student)).status_code == 403
