"""Departments, catalogue, course management, members and join requests."""

from sqlalchemy import select

from app.modules.admin.models import AuditLog
from app.modules.notifications.models import Notification
from tests.conftest import as_user
from tests.factories import enrol, make_course, make_user


def test_departments_admin_only(client, db):
    admin, teacher = make_user(db, "admin"), make_user(db, "teacher")
    body = {"code": "cse", "name": "Computer Science and Engineering"}
    assert client.post("/api/v1/departments", json=body, headers=as_user(teacher)).status_code == 403
    r = client.post("/api/v1/departments", json=body, headers=as_user(admin))
    assert r.status_code == 201 and r.json()["code"] == "CSE"
    assert client.post("/api/v1/departments", json=body, headers=as_user(admin)).status_code == 409
    dept_id = r.json()["id"]
    r = client.patch(f"/api/v1/departments/{dept_id}", json={"name": "CSE Dept"}, headers=as_user(admin))
    assert r.json()["name"] == "CSE Dept"
    assert any(d["code"] == "CSE" for d in client.get("/api/v1/departments").json()["items"])


def test_teacher_creates_course_and_teaches_it(client, db):
    admin, teacher, student = make_user(db, "admin"), make_user(db, "teacher"), make_user(db)
    dept = client.post("/api/v1/departments", json={"code": "EE", "name": "Electrical"}, headers=as_user(admin)).json()
    body = {"department_id": dept["id"], "code": "ee201", "term": "Jul-Nov 2026", "title": "Signals"}
    assert client.post("/api/v1/courses", json=body, headers=as_user(student)).status_code == 403
    r = client.post("/api/v1/courses", json=body, headers=as_user(teacher))
    assert r.status_code == 201
    course = r.json()
    assert course["code"] == "EE201" and course["teachers"] == [{"id": teacher.id, "name": teacher.name}]
    assert course["my_status"] == "teacher"
    assert (
        client.post("/api/v1/courses", json=body, headers=as_user(teacher)).json()["error"]["code"] == "COURSE_EXISTS"
    )


def test_admin_creates_course_for_teachers_and_is_audited(client, db):
    admin, t1, t2 = make_user(db, "admin"), make_user(db, "teacher"), make_user(db, "teacher")
    dept = client.post("/api/v1/departments", json={"code": "ME", "name": "Mechanical"}, headers=as_user(admin)).json()
    body = {
        "department_id": dept["id"],
        "code": "ME101",
        "term": "Jul-Nov 2026",
        "title": "Mechanics",
        "teacher_ids": [t1.id, t2.id],
    }
    course = client.post("/api/v1/courses", json=body, headers=as_user(admin)).json()
    assert {t["id"] for t in course["teachers"]} == {t1.id, t2.id}
    assert db.scalar(select(AuditLog).where(AuditLog.action == "course_created")) is not None


def test_catalogue_is_public_with_search_and_filters(client, db):
    teacher = make_user(db, "teacher", name="Dr. Kavya Menon")
    make_course(db, teacher, code="CS301", title="Software Engineering")
    make_course(db, teacher, code="CS302", title="Databases")
    r = client.get("/api/v1/courses?q=Software")
    assert r.status_code == 200
    assert [c["code"] for c in r.json()["items"]] == ["CS301"]
    assert {c["code"] for c in client.get("/api/v1/courses?q=Kavya").json()["items"]} == {"CS301", "CS302"}
    assert {c["code"] for c in client.get("/api/v1/courses?q=CS3").json()["items"]} == {"CS301", "CS302"}
    assert client.get("/api/v1/courses?q=Software").json()["items"][0]["my_status"] == "none"


def test_course_detail_and_my_courses(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    detail = client.get(f"/api/v1/courses/{course.id}", headers=as_user(student)).json()
    assert detail["my_status"] == "student" and detail["student_count"] == 1
    assert [c["id"] for c in client.get("/api/v1/users/me/courses", headers=as_user(student)).json()["items"]] == [
        course.id
    ]
    assert client.get("/api/v1/courses/999999").status_code == 404


def test_edit_and_archive(client, db):
    teacher, other = make_user(db, "teacher"), make_user(db, "teacher")
    course = make_course(db, teacher)
    assert client.patch(f"/api/v1/courses/{course.id}", json={"title": "XY"}, headers=as_user(other)).status_code == 403
    r = client.patch(f"/api/v1/courses/{course.id}", json={"title": "New title"}, headers=as_user(teacher))
    assert r.json()["title"] == "New title"
    assert (
        client.patch(f"/api/v1/courses/{course.id}", json={"archived": True}, headers=as_user(teacher)).json()[
            "archived"
        ]
        is True
    )
    r = client.patch(f"/api/v1/courses/{course.id}", json={"title": "YZ"}, headers=as_user(teacher))
    assert r.json()["error"]["code"] == "COURSE_ARCHIVED"


def test_join_request_flow(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    r = client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(student))
    assert r.status_code == 201 and r.json()["status"] == "requested"
    assert client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(student)).status_code == 409
    assert (
        db.scalar(select(Notification).where(Notification.user_id == teacher.id)).event_type == "join_request_received"
    )
    requests = client.get(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(teacher)).json()
    assert requests["total"] == 1
    req_id = requests["items"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/courses/{course.id}/join-requests/{req_id}", json={"status": "approved"}, headers=as_user(student)
        ).status_code
        == 403
    )
    r = client.patch(
        f"/api/v1/courses/{course.id}/join-requests/{req_id}", json={"status": "approved"}, headers=as_user(teacher)
    )
    assert r.json()["status"] == "active"
    assert client.get(f"/api/v1/courses/{course.id}", headers=as_user(student)).json()["my_status"] == "student"


def test_join_request_reject_cancel_and_closed(client, db):
    teacher, s1, s2 = make_user(db, "teacher"), make_user(db), make_user(db)
    course = make_course(db, teacher)
    client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(s1))
    req_id = client.get(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(teacher)).json()["items"][0]["id"]
    assert (
        client.patch(
            f"/api/v1/courses/{course.id}/join-requests/{req_id}", json={"status": "rejected"}, headers=as_user(teacher)
        ).json()["status"]
        == "rejected"
    )
    client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(s2))
    assert client.delete(f"/api/v1/courses/{course.id}/join-requests/mine", headers=as_user(s2)).status_code == 204
    closed = make_course(db, teacher, join_requests_open=False)
    r = client.post(f"/api/v1/courses/{closed.id}/join-requests", headers=as_user(s1))
    assert r.json()["error"]["code"] == "JOIN_REQUESTS_CLOSED"


def test_join_request_daily_limit(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    courses = [make_course(db, teacher) for _ in range(11)]
    for c in courses[:10]:
        assert client.post(f"/api/v1/courses/{c.id}/join-requests", headers=as_user(student)).status_code == 201
    r = client.post(f"/api/v1/courses/{courses[10].id}/join-requests", headers=as_user(student))
    assert r.status_code == 429 and r.json()["error"]["code"] == "JOIN_REQUEST_LIMIT"


def test_members_remove_and_reinstate(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, student)
    members = client.get(f"/api/v1/courses/{course.id}/members", headers=as_user(teacher)).json()
    assert members["total"] == 2
    assert (
        client.delete(f"/api/v1/courses/{course.id}/members/{student.id}", headers=as_user(teacher)).status_code == 204
    )
    assert client.get(f"/api/v1/courses/{course.id}/resources", headers=as_user(student)).status_code == 403
    r = client.post(f"/api/v1/courses/{course.id}/join-requests", headers=as_user(student))
    assert r.json()["error"]["code"] == "REMOVED_FROM_COURSE"
    assert (
        client.patch(
            f"/api/v1/courses/{course.id}/members/{student.id}", json={"status": "active"}, headers=as_user(teacher)
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/courses/{course.id}/resources", headers=as_user(student)).status_code == 200


def test_last_teacher_and_teacher_removal_rules(client, db):
    admin, teacher, t2 = make_user(db, "admin"), make_user(db, "teacher"), make_user(db, "teacher")
    course = make_course(db, teacher)
    assert (
        client.delete(f"/api/v1/courses/{course.id}/members/{teacher.id}", headers=as_user(teacher)).status_code == 403
    )
    r = client.delete(f"/api/v1/courses/{course.id}/members/{teacher.id}", headers=as_user(admin))
    assert r.json()["error"]["code"] == "LAST_TEACHER"
    assert (
        client.post(
            f"/api/v1/courses/{course.id}/teachers", json={"user_id": t2.id}, headers=as_user(admin)
        ).status_code
        == 201
    )
    assert client.delete(f"/api/v1/courses/{course.id}/members/{teacher.id}", headers=as_user(admin)).status_code == 204


def test_admin_acts_as_teacher_and_is_audited(client, db):
    admin, teacher = make_user(db, "admin"), make_user(db, "teacher")
    course = make_course(db, teacher)
    r = client.patch(f"/api/v1/courses/{course.id}", json={"title": "Changed by admin"}, headers=as_user(admin))
    assert r.status_code == 200
    log = db.scalar(select(AuditLog).where(AuditLog.action == "course_updated"))
    assert log.as_admin is True and log.course_id == course.id
