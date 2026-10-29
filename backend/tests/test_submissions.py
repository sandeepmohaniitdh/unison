"""Drafts, the final, the deadline rule and downloads."""

import io

from sqlalchemy import select

from app.modules.notifications.models import Notification
from app.modules.submissions.service import apply_due_deadlines
from tests.conftest import as_user
from tests.factories import PDF_BYTES
from tests.submission_helpers import files, key, team_of, upload


def test_drafts_are_team_only_and_idempotent(client, db):
    teacher, _a, team_id, (s1, s2, s3, _s4) = team_of(client, db)
    k = key()
    r = upload(client, team_id, s1, "report.pdf", "code.zip", k=k)
    assert r.status_code == 201 and r.json()["number"] == 1 and len(r.json()["files"]) == 2
    again = upload(client, team_id, s1, "report.pdf", k=k)
    assert again.json()["id"] == r.json()["id"]  # a repeated click returns the first draft
    assert upload(client, team_id, s2, "v2.pdf").json()["number"] == 2
    drafts = client.get(f"/api/v1/teams/{team_id}/submission/drafts", headers=as_user(s1)).json()["items"]
    assert [d["number"] for d in drafts] == [2, 1]
    # Teachers and outsiders never see drafts
    assert client.get(f"/api/v1/teams/{team_id}/submission/drafts", headers=as_user(teacher)).status_code == 404
    assert client.get(f"/api/v1/teams/{team_id}/submission/drafts", headers=as_user(s3)).status_code == 404
    # Teammate got an in-app notification
    assert db.scalar(
        select(Notification).where(Notification.user_id == s2.id, Notification.event_type == "draft_uploaded")
    )


def test_draft_rules(client, db):
    _t, _a, team_id, (s1, *_rest) = team_of(client, db)
    bad = client.post(
        f"/api/v1/teams/{team_id}/submission/drafts",
        headers={**as_user(s1), **key()},
        files=[("files", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert bad.json()["error"]["code"] == "FILE_TYPE_NOT_ALLOWED"
    fake = client.post(
        f"/api/v1/teams/{team_id}/submission/drafts",
        headers={**as_user(s1), **key()},
        files=[("files", ("report.pdf", io.BytesIO(b"not a pdf"), "application/pdf"))],
    )
    assert fake.json()["error"]["code"] == "FILE_TYPE_MISMATCH"
    too_many = upload(client, team_id, s1, *[f"f{i}.pdf" for i in range(6)])
    assert too_many.json()["error"]["code"] == "TOO_MANY_FILES"
    no_key = client.post(f"/api/v1/teams/{team_id}/submission/drafts", headers=as_user(s1), files=files("a.pdf"))
    assert no_key.status_code == 422
    not_uuid = client.post(
        f"/api/v1/teams/{team_id}/submission/drafts",
        headers={**as_user(s1), "Idempotency-Key": "click-1"},
        files=files("a.pdf"),
    )
    assert not_uuid.json()["error"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_submit_final_replace_and_conflicts(client, db):
    teacher, _a, team_id, (s1, s2, *_rest) = team_of(client, db)
    v1 = upload(client, team_id, s1, "v1.pdf").json()
    v2 = upload(client, team_id, s2, "v2.pdf").json()
    r = client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s1), **key()},
        json={"version_id": v1["id"], "expected_final_id": None},
    )
    assert r.status_code == 201
    first = r.json()
    assert first["submitted_by"]["id"] == s1.id and first["version_number"] == 1
    # s2 still thinks there is no final: refused, and told what the final is now
    stale = client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s2), **key()},
        json={"version_id": v2["id"], "expected_final_id": None},
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "FINAL_CHANGED"
    assert stale.json()["error"]["details"]["current_final"]["id"] == first["id"]
    r = client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s2), **key()},
        json={"version_id": v2["id"], "expected_final_id": first["id"]},
    )
    assert r.status_code == 201
    finals = client.get(f"/api/v1/teams/{team_id}/submission/finals", headers=as_user(s1)).json()["items"]
    assert [f["version_number"] for f in finals] == [2, 1] and finals[1]["replaced_at"] is not None
    # Teacher sees only the current final, and is notified
    view = client.get(f"/api/v1/teams/{team_id}/submission", headers=as_user(teacher)).json()
    assert (
        view["current_final"]["version_number"] == 2 and view["drafts_count"] is None and view["replaced_finals"] == 1
    )
    events = set(db.scalars(select(Notification.event_type).where(Notification.user_id == teacher.id)))
    assert {"final_submitted", "final_replaced"} <= events


def test_final_needs_minimum_size_and_pdf(client, db):
    _t, _a, team_id, (s1, *_rest) = team_of(client, db, size=1, min_team=2)
    v = upload(client, team_id, s1, "code.zip").json()
    r = client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s1), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    assert r.json()["error"]["code"] == "TEAM_BELOW_MIN_SIZE"
    _t, _a, team2, (p1, *_r) = team_of(client, db, size=2, requires_pdf=True)
    v = upload(client, team2, p1, "code.zip").json()
    r = client.post(
        f"/api/v1/teams/{team2}/submission/finals",
        headers={**as_user(p1), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    assert r.json()["error"]["code"] == "PDF_REQUIRED"


def test_deadline_auto_submits_latest_draft_even_below_minimum(client, db, clock):
    teacher, assignment, team_id, (s1, s2, *_r) = team_of(client, db)
    upload(client, team_id, s1, "v1.pdf")
    upload(client, team_id, s2, "v2.pdf")
    clock.advance(days=4)
    assert upload(client, team_id, s1, "late.pdf").json()["error"]["code"] == "DEADLINE_PASSED"
    view = client.get(f"/api/v1/teams/{team_id}/submission", headers=as_user(s1)).json()
    assert view["state"] == "submitted_at_deadline"
    assert view["current_final"]["kind"] == "at_deadline" and view["current_final"]["submitted_by"] is None
    assert view["current_final"]["version_number"] == 2 and view["closed_at"] is not None


def test_worker_applies_deadline_and_no_drafts_means_not_submitted(client, db, clock):
    teacher, assignment, team_id, (s1, *_r) = team_of(client, db, size=1, min_team=1)
    clock.advance(days=4)
    assert apply_due_deadlines(db, clock) == 1
    assert client.get(f"/api/v1/teams/{team_id}/submission", headers=as_user(s1)).json()["state"] == "not_submitted"
    assert apply_due_deadlines(db, clock) == 0  # already applied


def test_downloads(client, db, clock):
    teacher, _a, team_id, (s1, s2, s3, _s4) = team_of(client, db)
    v1 = upload(client, team_id, s1, "v1.pdf").json()
    v2 = upload(client, team_id, s1, "v2.pdf").json()
    client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s1), **key()},
        json={"version_id": v2["id"], "expected_final_id": None},
    )
    f1, f2 = v1["files"][0]["id"], v2["files"][0]["id"]
    r = client.get(f"/api/v1/submission-files/{f1}/content", headers=as_user(s2))
    assert r.status_code == 200 and r.content == PDF_BYTES
    assert (
        r.headers["content-disposition"].startswith("attachment") and r.headers["x-content-type-options"] == "nosniff"
    )
    assert client.get(f"/api/v1/submission-files/{f2}/content", headers=as_user(teacher)).status_code == 200
    assert client.get(f"/api/v1/submission-files/{f1}/content", headers=as_user(teacher)).status_code == 404
    assert client.get(f"/api/v1/submission-files/{f1}/content", headers=as_user(s3)).status_code == 404


def test_after_first_final_members_cannot_leave(client, db):
    teacher, assignment, team_id, (s1, s2, *_r) = team_of(client, db)
    v = upload(client, team_id, s1, "report.pdf").json()
    client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(s1), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    assert (
        client.delete(f"/api/v1/teams/{team_id}/members/me", headers=as_user(s2)).json()["error"]["code"]
        == "TEAM_HAS_FINAL"
    )


def test_removed_student_before_and_after_final(client, db):
    teacher, assignment, team_id, (s1, s2, *_r) = team_of(client, db)
    course_id = assignment.course_id
    client.delete(f"/api/v1/courses/{course_id}/members/{s2.id}", headers=as_user(teacher))
    team = client.get(f"/api/v1/teams/{team_id}", headers=as_user(s1)).json()
    assert [m["user"]["id"] for m in team["members"]] == [s1.id]  # before a final: they simply left

    teacher2, a2, team2, (p1, p2, *_r2) = team_of(client, db)
    v = upload(client, team2, p1, "r.pdf").json()
    client.post(
        f"/api/v1/teams/{team2}/submission/finals",
        headers={**as_user(p1), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    client.delete(f"/api/v1/courses/{a2.course_id}/members/{p2.id}", headers=as_user(teacher2))
    team = client.get(f"/api/v1/teams/{team2}", headers=as_user(p1)).json()
    assert {m["user"]["id"]: m["status"] for m in team["members"]}[p2.id] == "removed"
