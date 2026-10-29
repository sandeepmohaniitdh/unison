"""Course and staff invitations."""

from sqlalchemy import select

from app.modules.invitations.models import Invitation
from app.modules.notifications.models import EmailOutbox
from tests.conftest import as_user
from tests.factories import enrol, make_course, make_user


def _token_for(db, email):
    rows = db.scalars(select(EmailOutbox).where(EmailOutbox.template == "invitation", EmailOutbox.to_email == email))
    return list(rows)[-1].payload["token"]


def test_course_invitation_by_email_and_accept_by_link(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    course = make_course(db, teacher)
    r = client.post(
        f"/api/v1/courses/{course.id}/invitations",
        headers=as_user(teacher),
        json={"emails": [student.email, "NEW.PERSON@iitdh.ac.in", student.email]},
    )
    assert r.status_code == 201
    assert len(r.json()["created"]) == 2 and r.json()["skipped"] == []
    token = _token_for(db, student.email)

    view = client.get(f"/api/v1/invitation-links/{token}").json()
    assert view["kind"] == "course" and view["problem"] == "log_in" and view["course"]["id"] == course.id
    view = client.get(f"/api/v1/invitation-links/{token}", headers=as_user(student)).json()
    assert view["can_accept"] is True

    r = client.patch(f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user(student))
    assert r.status_code == 200 and r.json()["course_id"] == course.id
    assert client.get(f"/api/v1/courses/{course.id}", headers=as_user(student)).json()["my_status"] == "student"
    again = client.patch(f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user(student))
    assert again.status_code == 409


def test_invitation_rules(client, db, clock):
    teacher, student, other = make_user(db, "teacher"), make_user(db), make_user(db)
    course = make_course(db, teacher)
    enrol(db, course, other)
    r = client.post(
        f"/api/v1/courses/{course.id}/invitations",
        headers=as_user(teacher),
        json={"emails": [student.email, other.email]},
    )
    assert r.json()["skipped"] == [{"email": other.email, "reason": "already a member"}]
    again = client.post(
        f"/api/v1/courses/{course.id}/invitations", headers=as_user(teacher), json={"emails": [student.email]}
    )
    assert again.json()["skipped"][0]["reason"] == "already invited"
    token = _token_for(db, student.email)
    # Wrong account
    r = client.patch(f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user(other))
    assert r.status_code == 403 and r.json()["error"]["code"] == "WRONG_ACCOUNT"
    # Expired after 7 days
    clock.advance(days=7, minutes=1)
    r = client.patch(f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user(student))
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVITATION_NOT_PENDING"


def test_unverified_email_cannot_accept(client, db):
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    client.post(
        "/api/v1/auth/register",
        json={"name": "N", "email": "cs26mt077@iitdh.ac.in", "password": "password1", "consent": True},
    )
    client.cookies.clear()
    client.post(
        f"/api/v1/courses/{course.id}/invitations", headers=as_user(teacher), json={"emails": ["cs26mt077@iitdh.ac.in"]}
    )
    token = _token_for(db, "cs26mt077@iitdh.ac.in")
    r = client.patch(
        f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user("cs26mt077@iitdh.ac.in")
    )
    assert r.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_cancel_and_decline_and_dashboard_list(client, db):
    teacher, student = make_user(db, "teacher"), make_user(db)
    c1, c2 = make_course(db, teacher), make_course(db, teacher)
    inv1 = client.post(
        f"/api/v1/courses/{c1.id}/invitations", headers=as_user(teacher), json={"emails": [student.email]}
    ).json()["created"][0]
    client.post(f"/api/v1/courses/{c2.id}/invitations", headers=as_user(teacher), json={"emails": [student.email]})
    mine = client.get("/api/v1/users/me/invitations", headers=as_user(student)).json()["items"]
    assert len(mine) == 2
    assert client.delete(f"/api/v1/invitations/{inv1['id']}", headers=as_user(student)).status_code == 403
    assert client.delete(f"/api/v1/invitations/{inv1['id']}", headers=as_user(teacher)).status_code == 204
    other = [i for i in mine if i["id"] != inv1["id"]][0]
    assert (
        client.patch(
            f"/api/v1/invitations/{other['id']}", json={"status": "declined"}, headers=as_user(student)
        ).status_code
        == 200
    )
    assert client.get("/api/v1/users/me/invitations", headers=as_user(student)).json()["items"] == []


def test_staff_invitation_upgrades_student_and_signup_gets_role(client, db):
    admin, student = make_user(db, "admin"), make_user(db)
    r = client.post(
        "/api/v1/admin/staff-invitations", json={"email": student.email, "role": "teacher"}, headers=as_user(admin)
    )
    assert r.status_code == 201
    token = _token_for(db, student.email)
    assert (
        client.patch(
            f"/api/v1/invitation-links/{token}", json={"status": "accepted"}, headers=as_user(student)
        ).status_code
        == 200
    )
    assert client.get("/api/v1/users/me", headers=as_user(student)).json()["role"] == "teacher"

    client.post(
        "/api/v1/admin/staff-invitations", json={"email": "prof@example.com", "role": "admin"}, headers=as_user(admin)
    )
    token = _token_for(db, "prof@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Prof",
            "email": "prof@example.com",
            "password": "password1",
            "consent": True,
            "invitation_token": token,
        },
    )
    assert r.status_code == 201 and r.json()["role"] == "admin" and r.json()["emails"][0]["verified"] is True
    assert db.scalar(select(Invitation).where(Invitation.email == "prof@example.com")).status == "accepted"
