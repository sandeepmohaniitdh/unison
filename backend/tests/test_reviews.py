"""Reviews, marks, adjustments and releasing marks."""

from tests.conftest import as_user
from tests.submission_helpers import closed_team_with_final, key, team_of, upload


def test_review_marks_adjustment_and_release(client, db, clock):
    teacher, assignment, team_id, (s1, s2, s3, _s4) = closed_team_with_final(client, db, clock)
    sheet = client.get(f"/api/v1/teams/{team_id}/review", headers=as_user(teacher)).json()
    assert sheet["status"] == "none" and sheet["max_mark"] == "30.0"
    contrib = {c["user"]["id"]: c for c in sheet["contribution"]}
    assert contrib[s1.id]["drafts_uploaded"] == 1 and contrib[s2.id]["submitted_current_final"] is True
    crit = [c["criterion_id"] for c in sheet["rubric"]]
    r = client.put(
        f"/api/v1/teams/{team_id}/review",
        headers=as_user(teacher),
        json={"overall_comment": "Good work", "scores": [{"criterion_id": crit[0], "points": "8.5"}]},
    )
    assert r.json()["team_mark"] is None  # not every criterion scored yet
    assert (
        client.patch(f"/api/v1/teams/{team_id}/review", json={"status": "released"}, headers=as_user(teacher)).json()[
            "error"
        ]["code"]
        == "REVIEW_INCOMPLETE"
    )
    over = client.put(
        f"/api/v1/teams/{team_id}/review",
        headers=as_user(teacher),
        json={"scores": [{"criterion_id": crit[1], "points": "25"}]},
    )
    assert over.json()["error"]["code"] == "POINTS_OUT_OF_RANGE"
    r = client.put(
        f"/api/v1/teams/{team_id}/review",
        headers=as_user(teacher),
        json={"scores": [{"criterion_id": crit[1], "points": "16", "comment": "Tests missing"}]},
    )
    assert r.json()["team_mark"] == "24.5"
    bad = client.put(
        f"/api/v1/teams/{team_id}/review/adjustments/{s3.id}",
        headers=as_user(teacher),
        json={"percent": "-25", "reason": "x"},
    )
    assert bad.status_code == 422
    r = client.put(
        f"/api/v1/teams/{team_id}/review/adjustments/{s3.id}",
        headers=as_user(teacher),
        json={"percent": "-20", "reason": "Did not contribute to the code"},
    )
    marks = {m["user"]["id"]: m["mark"] for m in r.json()["members"]}
    assert marks[s3.id] == "19.6" and marks[s1.id] == "24.5"
    assert client.get(f"/api/v1/teams/{team_id}/marks", headers=as_user(s1)).status_code == 404  # not released yet
    r = client.patch(f"/api/v1/teams/{team_id}/review", json={"status": "released"}, headers=as_user(teacher))
    assert r.json()["status"] == "released"
    mine = client.get(f"/api/v1/teams/{team_id}/marks", headers=as_user(s3)).json()
    assert mine["my_mark"] == "19.6" and mine["adjustment_reason"] == "Did not contribute to the code"
    other = client.get(f"/api/v1/teams/{team_id}/marks", headers=as_user(s1)).json()
    assert other["my_mark"] == "24.5" and other["adjustment_percent"] is None  # others' adjustments stay private
    assert (
        client.put(f"/api/v1/teams/{team_id}/review", headers=as_user(teacher), json={"overall_comment": "x"}).json()[
            "error"
        ]["code"]
        == "REVIEW_RELEASED"
    )
    assert client.get(f"/api/v1/teams/{team_id}/submission", headers=as_user(s1)).json()["state"] == "marks_released"


def test_review_waits_for_deadline_and_overview(client, db, clock):
    teacher, assignment, team_id, (s1, *_r) = team_of(client, db)
    v = upload(client, team_id, s1, "report.pdf").json()
    client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s1), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    r = client.put(f"/api/v1/teams/{team_id}/review", headers=as_user(teacher), json={"overall_comment": "early"})
    assert r.json()["error"]["code"] == "SUBMISSION_OPEN"
    rows = client.get(f"/api/v1/assignments/{assignment.id}/reviews", headers=as_user(teacher)).json()
    assert rows["total"] == 1 and rows["items"][0]["state"] == "final_submitted"
    assert client.get(f"/api/v1/assignments/{assignment.id}/reviews", headers=as_user(s1)).status_code == 403


def test_bulk_release(client, db, clock):
    teacher, assignment, team_id, _students = closed_team_with_final(client, db, clock)
    sheet = client.get(f"/api/v1/teams/{team_id}/review", headers=as_user(teacher)).json()
    client.put(
        f"/api/v1/teams/{team_id}/review",
        headers=as_user(teacher),
        json={"scores": [{"criterion_id": c["criterion_id"], "points": "5"} for c in sheet["rubric"]]},
    )
    r = client.patch(
        f"/api/v1/assignments/{assignment.id}/reviews", json={"status": "released"}, headers=as_user(teacher)
    )
    assert r.json() == {"released": 1, "skipped": []}
