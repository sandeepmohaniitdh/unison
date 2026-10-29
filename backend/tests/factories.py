"""Small helpers that create test data directly in the database."""

import itertools
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.assignments.models import Assignment, RubricCriterion
from app.modules.courses.models import Course, Department, Enrollment
from app.modules.users import service as users
from app.modules.users.models import User

_n = itertools.count(1)

PDF_BYTES = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
ZIP_BYTES = b"PK\x05\x06" + b"\x00" * 18


@dataclass
class Person:
    id: int
    email: str
    name: str
    user: User


def make_user(
    db: Session,
    role: str = "student",
    name: str | None = None,
    email: str | None = None,
    password: str | None = None,
    now: datetime | None = None,
) -> Person:
    n = next(_n)
    name = name or f"{role.title()} {n}"
    email = email or f"{role}{n}@iitdh.ac.in"
    user = users.create_user(
        db, name=name, email=email, role=role, password=password, now=now or datetime(2026, 10, 1), verified=True
    )
    db.commit()
    return Person(user.id, email, name, user)


def make_course(db: Session, teacher: Person | None = None, code: str | None = None, **kw) -> Course:
    n = next(_n)
    dept = db.query(Department).filter_by(code="TST").one_or_none()
    if dept is None:
        dept = Department(code="TST", name="Testing Department")
        db.add(dept)
        db.flush()
    course = Course(
        department_id=dept.id,
        code=code or f"TS{n:03d}",
        term="Jul-Nov 2026",
        title=kw.pop("title", f"Test Course {n}"),
        join_requests_open=kw.pop("join_requests_open", True),
        created_by=teacher.id if teacher else 1,
        created_at=datetime(2026, 10, 1),
        **kw,
    )
    db.add(course)
    db.flush()
    if teacher:
        enrol(db, course, teacher, "teacher")
    db.commit()
    return course


def enrol(db: Session, course: Course, person: Person, role: str = "student") -> None:
    db.add(
        Enrollment(course_id=course.id, user_id=person.id, role=role, status="active", created_at=datetime(2026, 10, 1))
    )
    db.commit()


def make_assignment(
    db: Session,
    course: Course,
    creator: Person,
    *,
    kind: str = "group",
    min_team: int = 2,
    max_team: int = 3,
    due_at: datetime | None = None,
    status: str = "published",
    requires_pdf: bool = False,
    rubric=(("Report", 10), ("Code", 20)),
) -> Assignment:
    if kind == "individual":
        min_team = max_team = 1
    a = Assignment(
        course_id=course.id,
        title=f"Assignment {next(_n)}",
        description="Write a report.",
        kind=kind,
        min_team=min_team,
        max_team=max_team,
        max_files=5,
        requires_pdf=requires_pdf,
        due_at=due_at or datetime(2026, 11, 10, 18, 29, 59),
        status=status,
        teams_locked=False,
        published_at=datetime(2026, 10, 20) if status != "draft" else None,
        created_by=creator.id,
    )
    db.add(a)
    db.flush()
    for pos, (title, points) in enumerate(rubric, start=1):
        db.add(RubricCriterion(assignment_id=a.id, position=pos, title=title, max_points=Decimal(points)))
    db.commit()
    return a


class NoCloseSession:
    """Lets code that opens and closes its own sessions use the test's session."""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    def __getattr__(self, name):
        return getattr(self.db, name)

    def close(self):
        pass
