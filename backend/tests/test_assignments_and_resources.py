"""Assignments, rubrics, deadlines and course resources."""

import io

from sqlalchemy import select

from app.modules.notifications.models import EmailOutbox, Notification
from tests.conftest import as_user
from tests.factories import PDF_BYTES, enrol, make_course, make_user

BODY = {
    "title": "Project report",
    "kind": "group",
    "min_team": 2,
    "max_team": 4,
    "due_at": "2026-11-20T23:59",
    "rubric": [{"title": "Design", "max_points": 10}, {"title": "Testing", "max_points": 15}],
}


def _course(db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    return teacher, student, course


def test_create_publish_and_view_assignment(client, db):
    teacher, student, course = _course(db)
    r = client.post(f"/api/v1/courses/{course.id}/assignments", json=BODY, headers=as_user(teacher))
    assert r.status_code == 201
    a = r.json()
    # 23:59 IST means 23:59:59 IST
    assert a["due_at"] == "2026-11-20T23:59:59+05:30" and a["status"] == "draft" and a["total_points"] == "25.0"
    assert client.get(f"/api/v1/assignments/{a['id']}", headers=as_user(student)).status_code == 404  # drafts hidden
    assert client.get(f"/api/v1/courses/{course.id}/assignments", headers=as_user(student)).json()["total"] == 0
    r = client.patch(f"/api/v1/assignments/{a['id']}", json={"status": "published"}, headers=as_user(teacher))
    assert r.json()["status"] == "published"
    assert (
        db.scalar(select(Notification).where(Notification.user_id == student.id)).event_type == "assignment_published"
    )
    listed = client.get(f"/api/v1/courses/{course.id}/assignments", headers=as_user(student)).json()["items"][0]
    assert listed["my_team"] == {"team_id": None, "state": "no_team"}
    detail = client.get(f"/api/v1/assignments/{a['id']}", headers=as_user(student)).json()
    assert [c["title"] for c in detail["rubric"]] == ["Design", "Testing"]


def test_assignment_validation_and_draft_only_edits(client, db):
    teacher, _s, course = _course(db)
    bad = {**BODY, "min_team": 4, "max_team": 2}
    assert (
        client.post(f"/api/v1/courses/{course.id}/assignments", json=bad, headers=as_user(teacher)).status_code == 422
    )
    past = {**BODY, "due_at": "2026-01-01T10:00"}
    assert (
        client.post(f"/api/v1/courses/{course.id}/assignments", json=past, headers=as_user(teacher)).json()["error"][
            "code"
        ]
        == "DEADLINE_IN_PAST"
    )
    a = client.post(f"/api/v1/courses/{course.id}/assignments", json=BODY, headers=as_user(teacher)).json()
    r = client.patch(
        f"/api/v1/assignments/{a['id']}",
        headers=as_user(teacher),
        json={"rubric": [{"title": "Only", "max_points": 50}], "max_team": 3},
    )
    assert r.json()["total_points"] == "50.0" and r.json()["max_team"] == 3
    client.patch(f"/api/v1/assignments/{a['id']}", json={"status": "published"}, headers=as_user(teacher))
    r = client.patch(f"/api/v1/assignments/{a['id']}", headers=as_user(teacher), json={"max_team": 5})
    assert r.json()["error"]["code"] == "ASSIGNMENT_PUBLISHED"
    assert (
        client.patch(f"/api/v1/assignments/{a['id']}", headers=as_user(teacher), json={"title": "Renamed"}).json()[
            "title"
        ]
        == "Renamed"
    )
    assert client.delete(f"/api/v1/assignments/{a['id']}", headers=as_user(teacher)).status_code == 409


def test_individual_is_a_team_of_one_and_delete_draft(client, db):
    teacher, _s, course = _course(db)
    a = client.post(
        f"/api/v1/courses/{course.id}/assignments",
        headers=as_user(teacher),
        json={**BODY, "kind": "individual", "min_team": 3, "max_team": 5},
    ).json()
    assert (a["min_team"], a["max_team"]) == (1, 1)
    assert client.delete(f"/api/v1/assignments/{a['id']}", headers=as_user(teacher)).status_code == 204


def test_extend_deadline(client, db, clock):
    teacher, student, course = _course(db)
    a = client.post(f"/api/v1/courses/{course.id}/assignments", json=BODY, headers=as_user(teacher)).json()
    client.patch(f"/api/v1/assignments/{a['id']}", json={"status": "published"}, headers=as_user(teacher))
    earlier = client.patch(
        f"/api/v1/assignments/{a['id']}", json={"due_at": "2026-11-19T10:00"}, headers=as_user(teacher)
    )
    assert earlier.json()["error"]["code"] == "NOT_LATER"
    r = client.patch(f"/api/v1/assignments/{a['id']}", json={"due_at": "2026-11-25T23:59"}, headers=as_user(teacher))
    assert r.json()["due_at"] == "2026-11-25T23:59:59+05:30"
    events = list(db.scalars(select(Notification.event_type).where(Notification.user_id == student.id)))
    assert "deadline_extended" in events
    clock.advance(days=40)
    late = client.patch(f"/api/v1/assignments/{a['id']}", json={"due_at": "2027-01-25T23:59"}, headers=as_user(teacher))
    assert late.json()["error"]["code"] == "DEADLINE_PASSED"


def test_resources_draft_publish_download(client, db, clock):
    teacher, student, course = _course(db)
    r = client.post(
        f"/api/v1/courses/{course.id}/resources/files",
        headers=as_user(teacher),
        data={"title": "Lecture 1 slides"},
        files={"file": ("lecture1.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    assert r.status_code == 201 and r.json()["status"] == "draft" and r.json()["kind"] == "file"
    file_id = r.json()["id"]
    link = client.post(
        f"/api/v1/courses/{course.id}/resources/links",
        headers=as_user(teacher),
        json={"title": "Course site", "url": "https://example.com/cs301"},
    ).json()
    assert client.get(f"/api/v1/courses/{course.id}/resources", headers=as_user(student)).json()["total"] == 0
    assert client.get(f"/api/v1/resources/{file_id}/content", headers=as_user(student)).status_code == 404
    r = client.post(
        f"/api/v1/courses/{course.id}/resource-publications",
        headers=as_user(teacher),
        json={"resource_ids": [file_id, link["id"]]},
    )
    assert {x["status"] for x in r.json()} == {"published"}
    notes = list(db.scalars(select(Notification).where(Notification.user_id == student.id)))
    assert len(notes) == 1 and notes[0].title.startswith("2 new resources")  # one notification for both
    email = db.scalar(select(EmailOutbox).where(EmailOutbox.template == "resources_published"))
    assert email.payload["titles"] == ["Lecture 1 slides", "Course site"] and email.send_after > clock.now()
    # A second publish within 10 minutes joins the same email
    third = client.post(
        f"/api/v1/courses/{course.id}/resources/links",
        headers=as_user(teacher),
        json={"title": "Reading list", "url": "https://example.com/reading"},
    ).json()
    clock.advance(minutes=3)
    client.post(
        f"/api/v1/courses/{course.id}/resource-publications",
        headers=as_user(teacher),
        json={"resource_ids": [third["id"]]},
    )
    emails = list(db.scalars(select(EmailOutbox).where(EmailOutbox.template == "resources_published")))
    assert len(emails) == 1 and emails[0].payload["titles"][-1] == "Reading list"
    d = client.get(f"/api/v1/resources/{file_id}/content", headers=as_user(student))
    assert d.status_code == 200 and d.content == PDF_BYTES and "attachment" in d.headers["content-disposition"]
    assert (
        client.get(f"/api/v1/resources/{link['id']}/content", headers=as_user(student)).json()["error"]["code"]
        == "RESOURCE_IS_LINK"
    )


def test_resource_rules(client, db):
    teacher, student, course = _course(db)
    svg = client.post(
        f"/api/v1/courses/{course.id}/resources/files",
        headers=as_user(teacher),
        data={"title": "x"},
        files={"file": ("x.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")},
    )
    assert svg.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
    assert (
        client.post(
            f"/api/v1/courses/{course.id}/resources/links",
            headers=as_user(student),
            json={"title": "x", "url": "https://example.com"},
        ).status_code
        == 403
    )
    link = client.post(
        f"/api/v1/courses/{course.id}/resources/links",
        headers=as_user(teacher),
        json={"title": "Old", "url": "https://example.com"},
    ).json()
    r = client.patch(
        f"/api/v1/resources/{link['id']}", headers=as_user(teacher), json={"title": "New", "url": "https://example.org"}
    )
    assert r.json()["title"] == "New" and r.json()["url"].startswith("https://example.org")
    r = client.post(
        f"/api/v1/courses/{course.id}/resource-publications",
        headers=as_user(teacher),
        json={"resource_ids": [link["id"]], "notify": False},
    )
    assert r.status_code == 201
    assert db.scalar(select(Notification).where(Notification.user_id == student.id)) is None
    assert client.delete(f"/api/v1/resources/{link['id']}", headers=as_user(teacher)).status_code == 204
