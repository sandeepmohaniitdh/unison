"""Teams: creating, inviting, accepting, leaving, locking, moving."""

from app.modules.invitations.models import Invitation
from tests.conftest import as_user
from tests.factories import enrol, make_assignment, make_course, make_user


def _setup_group(db, max_team=3, min_team=2):
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    students = [make_user(db) for _ in range(5)]
    for s in students:
        enrol(db, course, s)
    assignment = make_assignment(db, course, teacher, min_team=min_team, max_team=max_team)
    return teacher, course, students, assignment


def test_create_team_invite_and_accept(client, db):
    _teacher, _course, (a, b, c, *_), assignment = _setup_group(db)
    r = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "Byte Builders"}, headers=as_user(a))
    assert r.status_code == 201
    team = r.json()
    assert team["places_left"] == 2 and [m["user"]["id"] for m in team["members"]] == [a.id]
    assert (
        client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "Two"}, headers=as_user(a)).json()[
            "error"
        ]["code"]
        == "ALREADY_IN_TEAM"
    )
    inv = client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": b.email}, headers=as_user(a))
    assert inv.status_code == 201
    r = client.patch(f"/api/v1/invitations/{inv.json()['id']}", json={"status": "accepted"}, headers=as_user(b))
    assert r.status_code == 200 and r.json()["team_id"] == team["id"]
    # Any active member can invite, not only the creator.
    assert (
        client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": c.email}, headers=as_user(b)).status_code
        == 201
    )
    mine = client.get(f"/api/v1/assignments/{assignment.id}/my-team", headers=as_user(b)).json()
    assert mine["id"] == team["id"] and mine["places_left"] == 0


def test_invitations_reserve_places(client, db):
    _teacher, _course, (a, b, c, d, _e), assignment = _setup_group(db, max_team=3)
    team = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "T"}, headers=as_user(a)).json()
    for s in (b, c):
        assert (
            client.post(
                f"/api/v1/teams/{team['id']}/invitations", json={"email": s.email}, headers=as_user(a)
            ).status_code
            == 201
        )
    r = client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": d.email}, headers=as_user(a))
    assert r.status_code == 409 and r.json()["error"]["code"] == "TEAM_FULL"


def test_accepting_one_team_declines_the_others(client, db):
    _teacher, _course, (a, b, c, *_), assignment = _setup_group(db)
    t1 = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "One"}, headers=as_user(a)).json()
    t2 = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "Two"}, headers=as_user(b)).json()
    i1 = client.post(f"/api/v1/teams/{t1['id']}/invitations", json={"email": c.email}, headers=as_user(a)).json()
    i2 = client.post(f"/api/v1/teams/{t2['id']}/invitations", json={"email": c.email}, headers=as_user(b)).json()
    client.patch(f"/api/v1/invitations/{i1['id']}", json={"status": "accepted"}, headers=as_user(c))
    assert db.get(Invitation, i2["id"]).status == "declined"


def test_cannot_invite_non_members_or_people_in_teams(client, db):
    _teacher, _course, (a, b, *_), assignment = _setup_group(db)
    outsider = make_user(db)
    team = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "T"}, headers=as_user(a)).json()
    r = client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": outsider.email}, headers=as_user(a))
    assert r.json()["error"]["code"] == "NOT_ENROLLED"
    client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "B team"}, headers=as_user(b))
    r = client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": b.email}, headers=as_user(a))
    assert r.json()["error"]["code"] == "ALREADY_IN_TEAM"
    # Non-members do not learn that the team exists.
    assert client.get(f"/api/v1/teams/{team['id']}", headers=as_user(b)).status_code == 404


def test_leave_team_and_last_member_closes_it(client, db):
    _teacher, _course, (a, b, *_), assignment = _setup_group(db)
    team = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "T"}, headers=as_user(a)).json()
    inv = client.post(f"/api/v1/teams/{team['id']}/invitations", json={"email": b.email}, headers=as_user(a)).json()
    assert client.delete(f"/api/v1/teams/{team['id']}/members/me", headers=as_user(a)).status_code == 204
    # b can still accept: one member left -> room
    assert (
        client.patch(f"/api/v1/invitations/{inv['id']}", json={"status": "accepted"}, headers=as_user(b)).status_code
        == 409
    )  # team closed
    assert client.get(f"/api/v1/assignments/{assignment.id}/my-team", headers=as_user(a)).status_code == 404


def test_teams_locked_and_teacher_move_and_remove(client, db):
    teacher, _course, (a, b, c, d, _e), assignment = _setup_group(db)
    t1 = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "One"}, headers=as_user(a)).json()
    t2 = client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "Two"}, headers=as_user(b)).json()
    i = client.post(f"/api/v1/teams/{t1['id']}/invitations", json={"email": c.email}, headers=as_user(a)).json()
    client.patch(f"/api/v1/invitations/{i['id']}", json={"status": "accepted"}, headers=as_user(c))
    r = client.patch(f"/api/v1/assignments/{assignment.id}", json={"teams_locked": True}, headers=as_user(teacher))
    assert r.json()["teams_locked"] is True
    assert (
        client.delete(f"/api/v1/teams/{t1['id']}/members/me", headers=as_user(c)).json()["error"]["code"]
        == "TEAMS_LOCKED"
    )
    r = client.patch(f"/api/v1/teams/{t1['id']}/members/{c.id}", json={"team_id": t2["id"]}, headers=as_user(teacher))
    assert r.status_code == 200 and {m["user"]["id"] for m in r.json()["members"]} == {b.id, c.id}
    assert client.delete(f"/api/v1/teams/{t2['id']}/members/{c.id}", headers=as_user(teacher)).status_code == 204
    all_teams = client.get(f"/api/v1/assignments/{assignment.id}/teams", headers=as_user(teacher)).json()
    assert all_teams["total"] == 2
    assert client.get(f"/api/v1/assignments/{assignment.id}/teams", headers=as_user(d)).status_code == 403


def test_individual_assignment_team_of_one(client, db):
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    s = make_user(db)
    enrol(db, course, s)
    assignment = make_assignment(db, course, teacher, kind="individual")
    r = client.get(f"/api/v1/assignments/{assignment.id}/my-team", headers=as_user(s))
    assert r.status_code == 200 and r.json()["kind"] == "individual" and len(r.json()["members"]) == 1
    assert client.get(f"/api/v1/assignments/{assignment.id}/my-team", headers=as_user(s)).json()["id"] == r.json()["id"]
    assert (
        client.post(f"/api/v1/assignments/{assignment.id}/teams", json={"name": "X"}, headers=as_user(s)).json()[
            "error"
        ]["code"]
        == "NOT_GROUP"
    )
