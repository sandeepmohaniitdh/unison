"""Helpers for tests that need a team with drafts and finals."""

import io
import uuid
from datetime import timedelta

from tests.conftest import START, as_user
from tests.factories import PDF_BYTES, ZIP_BYTES, enrol, make_assignment, make_course, make_user


def key() -> dict:
    return {"Idempotency-Key": str(uuid.uuid4())}


def files(*names):
    out = []
    for name in names:
        data, mime = (PDF_BYTES, "application/pdf") if name.endswith(".pdf") else (ZIP_BYTES, "application/zip")
        out.append(("files", (name, io.BytesIO(data), mime)))
    return out


def team_of(client, db, size=2, **kw):
    """A teacher, a group assignment and one team with `size` members."""
    teacher = make_user(db, "teacher")
    course = make_course(db, teacher)
    students = [make_user(db) for _ in range(4)]
    for s in students:
        enrol(db, course, s)
    assignment = make_assignment(db, course, teacher, due_at=START + timedelta(days=3), **kw)
    lead = students[0]
    team = client.post(
        f"/api/v1/assignments/{assignment.id}/teams", json={"name": "Byte Builders"}, headers=as_user(lead)
    ).json()
    for s in students[1:size]:
        inv = client.post(
            f"/api/v1/teams/{team['id']}/invitations", json={"email": s.email}, headers=as_user(lead)
        ).json()
        client.patch(f"/api/v1/invitations/{inv['id']}", json={"status": "accepted"}, headers=as_user(s))
    return teacher, assignment, team["id"], students


def upload(client, team_id, person, *names, k=None):
    return client.post(
        f"/api/v1/teams/{team_id}/submission/drafts", files=files(*names), headers={**as_user(person), **(k or key())}
    )


def closed_team_with_final(client, db, clock):
    teacher, assignment, team_id, students = team_of(client, db, size=3)
    v = upload(client, team_id, students[0], "report.pdf").json()
    client.post(
        f"/api/v1/teams/{team_id}/submission/finals",
        headers={**as_user(students[1]), **key()},
        json={"version_id": v["id"], "expected_final_id": None},
    )
    clock.advance(days=4)
    return teacher, assignment, team_id, students
