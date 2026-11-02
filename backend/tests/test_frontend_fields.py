"""Fields the web frontend reads: catalogue counts, your enrolment, team sizes, member emails
and the admin overview numbers."""

import io
from datetime import timedelta

from app.modules.notifications.models import EmailOutbox
from tests.conftest import START, as_user
from tests.factories import PDF_BYTES, enrol, make_assignment, make_course, make_user
from tests.submission_helpers import key, team_of, upload


def test_catalogue_counts_only_published_work(client, db):
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    make_assignment(db, course, teacher)
    make_assignment(db, course, teacher, status="draft")
    r = client.post(
        f"/api/v1/courses/{course.id}/resources/files",
        headers=as_user(teacher),
        data={"title": "Slides"},
        files={"file": ("slides.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )
    client.post(
        f"/api/v1/courses/{course.id}/resources/links",
        headers=as_user(teacher),
        json={"title": "Draft link", "url": "https://example.com/x"},
    )
    client.post(
        f"/api/v1/courses/{course.id}/resource-publications",
        headers=as_user(teacher),
        json={"resource_ids": [r.json()["id"]]},
    )
    items = client.get("/api/v1/courses", params={"q": course.code}).json()["items"]
    card = next(c for c in items if c["id"] == course.id)
    assert card["assignment_count"] == 1 and card["resource_count"] == 1


def test_my_enrolment_says_how_you_joined(client, db):
    teacher, student, visitor = make_user(db, "teacher"), make_user(db), make_user(db)
    course = make_course(db, teacher)
    assert client.get(f"/api/v1/courses/{course.id}").json()["my_enrolment"] is None
    assert client.get(f"/api/v1/courses/{course.id}", headers=as_user(visitor)).json()["my_enrolment"] is None

    mine = client.get(f"/api/v1/courses/{course.id}", headers=as_user(teacher)).json()["my_enrolment"]
    assert mine["role"] == "teacher" and mine["via"] == "added"

    client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(student))
    req = client.get(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(teacher)).json()["items"][0]
    client.patch(
        f"/api/v1/courses/{course.id}/join-requests/{req['id']}", json={"status": "approved"}, headers=as_user(teacher)
    )
    mine = client.get(f"/api/v1/courses/{course.id}", headers=as_user(student)).json()["my_enrolment"]
    assert mine["role"] == "student" and mine["via"] == "join_request"
    assert mine["decided_by"] == {"id": teacher.id, "name": teacher.name}


def test_team_invitation_shows_largest_team_and_members_have_emails(client, db):
    teacher, assignment, team_id, students = team_of(client, db, size=2, max_team=4)
    lead, newcomer = students[0], students[2]
    client.post(f"/api/v1/teams/{team_id}/invitations", json={"email": newcomer.email}, headers=as_user(lead))
    invitations = client.get("/api/v1/users/me/invitations", headers=as_user(newcomer)).json()["items"]
    assert invitations[0]["team"]["max_team"] == 4

    team = client.get(f"/api/v1/teams/{team_id}", headers=as_user(lead)).json()
    assert {m["email"] for m in team["members"]} == {lead.email, students[1].email}


def test_teacher_dashboard_gives_assignment_kind(client, db):
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    group = make_assignment(db, course, teacher, due_at=START + timedelta(days=2))
    solo = make_assignment(db, course, teacher, kind="individual", due_at=START + timedelta(days=3))
    dash = client.get("/api/v1/dashboards/teacher", headers=as_user(teacher)).json()
    kinds = {a["id"]: a["kind"] for a in dash["assignments"]}
    assert kinds[group.id] == "group" and kinds[solo.id] == "individual"


def test_admin_stats_count_this_week_and_failed_emails(client, db, clock):
    admin = make_user(db, "admin")
    before = client.get("/api/v1/admin/stats", headers=as_user(admin)).json()
    _teacher, _assignment, team_id, students = team_of(client, db, size=2)
    v = upload(client, team_id, students[0], "report.pdf").json()
    client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(students[0]), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    db.add(
        EmailOutbox(
            to_email="someone@iitdh.ac.in",
            template="test",
            payload={},
            dedup_key="frontend-fields-failed",
            status="failed",
            attempts=4,
            send_after=clock.now(),
        )
    )
    db.commit()
    now = client.get("/api/v1/admin/stats", headers=as_user(admin)).json()
    assert now["finals_this_week"] == before["finals_this_week"] + 1
    assert now["failed_emails_24h"] == before["failed_emails_24h"] + 1

    clock.advance(days=8)
    later = client.get("/api/v1/admin/stats", headers=as_user(admin)).json()
    assert later["finals_last_week"] == before["finals_last_week"] + 1
    assert later["failed_emails_24h"] == before["failed_emails_24h"]


def test_course_member_list_still_private(client, db):
    teacher, student, outsider = make_user(db, "teacher"), make_user(db), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    assert client.get(f"/api/v1/courses/{course.id}/members", headers=as_user(outsider)).status_code in (403, 404)
