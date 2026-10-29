"""Synthetic demo data: `python -m app.seed.run` (the init service runs it on every start).

Safe to re-run: if the database already has departments, it does nothing.

Everything is invented: departments and courses from data.py, people from
Faker (en_IN) with example.com emails, so no seeded email can reach a real
inbox. A fixed random seed gives every fresh clone the same data; only the
dates move, so that open assignments are always in the future.

Every seeded account has the password "unison-demo", hashed with Argon2 for
each account like a real sign-up (each hash has its own salt).

Sizes: 5 departments, 20 courses, 300 students, 15 teachers, 2 admins,
1,200 enrolments + 60 join requests, 60 assignments, about 380 group teams
and 1,440 teams of one, about 3,300 placeholder PDFs, about 1,270 released
reviews, about 400 invitations, 100 resources and 1,500 notifications.
"""

import logging
import random
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pdf import text_pdf
from app.core.security import hash_password, new_token
from app.core.storage import LocalStorage
from app.core.time import utcnow
from app.modules.assignments.models import Assignment, RubricCriterion
from app.modules.courses.models import Course, Department, Enrollment
from app.modules.invitations.models import Invitation
from app.modules.notifications.models import Notification
from app.modules.resources.models import Resource
from app.modules.reviews.models import MemberAdjustment, Review, ReviewScore
from app.modules.submissions.models import FinalSubmission, Submission, SubmissionFile, SubmissionVersion
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User, UserEmail
from app.seed.data import (
    COURSES,
    DEMO_ADMIN,
    DEMO_PASSWORD,
    DEMO_STUDENTS,
    DEMO_TEACHER,
    DEPARTMENTS,
    GROUP_RUBRIC,
    INDIVIDUAL_RUBRIC,
    RESOURCE_TITLES,
    TEAM_NOUNS,
    TEAM_WORDS,
    TERM,
)

log = logging.getLogger("unison.seed")

SEED = 2026
STUDENTS = 300
TEACHERS = 15


class Seeder:
    def __init__(self, db: Session, storage: LocalStorage, now: datetime):
        self.db = db
        self.storage = storage
        self.now = now
        self.rng = random.Random(SEED)
        self.fake = Faker("en_IN")
        self.fake.seed_instance(SEED)
        self.emails_used: set[str] = set()
        self.counts: dict[str, int] = {}

    def count(self, key: str, n: int = 1) -> None:
        self.counts[key] = self.counts.get(key, 0) + n

    def days(self, n: float) -> datetime:
        return self.now + timedelta(days=n)

    # ---------------------------------------------------------------- people

    def _email_for(self, name: str) -> str:
        base = re.sub(r"[^a-z.]", "", name.lower().replace("dr. ", "").replace(" ", "."))[:30].strip(".") or "user"
        email, n = f"{base}@example.com", 1
        while email in self.emails_used:
            n += 1
            email = f"{base}{n}@example.com"
        return email

    def person(self, name: str, role: str, email: str | None = None) -> User:
        email = email or self._email_for(name)
        self.emails_used.add(email)
        created = self.days(-60)
        user = User(
            name=name,
            role=role,
            status="active",
            password_hash=hash_password(DEMO_PASSWORD),
            must_change_password=False,
            consent_at=created,
            created_at=created,
        )
        self.db.add(user)
        self.db.flush()
        self.db.add(UserEmail(user_id=user.id, email=email, is_primary=True, verified_at=created, created_at=created))
        self.count(f"{role}s")
        return user

    # ---------------------------------------------------------------- files

    def pdf(self, title: str, lines: list[str]) -> tuple[str, int, str]:
        data = text_pdf(["\n".join([title, *lines, "", "Placeholder text for the Unison demo data."])])
        stored = self.storage.save_bytes(data, "report.pdf", "application/pdf")
        self.count("files")
        return stored.key, stored.size_bytes, stored.sha256

    def draft(
        self, sub: Submission, number: int, uploader: User, when: datetime, title: str, two_files: bool
    ) -> SubmissionVersion:
        version = SubmissionVersion(
            submission_id=sub.id,
            number=number,
            uploaded_by=uploader.id,
            idempotency_key=str(self.rng_uuid()),
            created_at=when,
        )
        self.db.add(version)
        self.db.flush()
        names = ["report.pdf", "slides.pdf"] if two_files else ["report.pdf"]
        for name in names:
            key, size, sha = self.pdf(f"{title} - v{number}", [f"Uploaded by {uploader.name}", f"File: {name}"])
            self.db.add(
                SubmissionFile(
                    version_id=version.id,
                    file_name=name,
                    storage_key=key,
                    mime_type="application/pdf",
                    size_bytes=size,
                    sha256=sha,
                )
            )
        self.count("drafts")
        return version

    def rng_uuid(self) -> str:
        """A repeatable UUID (from the seeded random generator) for idempotency keys."""
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def final(
        self,
        sub: Submission,
        version: SubmissionVersion,
        by: User | None,
        when: datetime,
        kind: str = "manual",
        below_min: bool = False,
    ) -> FinalSubmission:
        final = FinalSubmission(
            version_id=version.id,
            submitted_by=by.id if by else None,
            kind=kind,
            below_min_size=below_min,
            idempotency_key=self.rng_uuid() if by else None,
            submitted_at=when,
        )
        self.db.add(final)
        self.db.flush()
        sub.current_final_id = final.id
        self.count("finals")
        return final

    def review(
        self,
        final: FinalSubmission,
        criteria: list[RubricCriterion],
        reviewer: User,
        when: datetime,
        fixed: list[Decimal] | None = None,
    ) -> Review:
        review = Review(
            final_id=final.id,
            reviewer_id=reviewer.id,
            status="released",
            released_at=when,
            overall_comment=self.rng.choice(
                [
                    "Good work overall.",
                    "Clear and well organised.",
                    "Solid, but the testing needs more depth.",
                    "Meets the brief; see comments per criterion.",
                ]
            ),
            updated_at=when,
        )
        self.db.add(review)
        self.db.flush()
        for i, c in enumerate(criteria):
            points = (
                fixed[i] if fixed else Decimal(self.rng.randint(int(c.max_points * 5), int(c.max_points * 10))) / 10
            )
            self.db.add(
                ReviewScore(
                    review_id=review.id,
                    criterion_id=c.id,
                    points=points,
                    comment=self.rng.choice(["Well done.", "Could be clearer.", "Good effort.", None]),
                )
            )
        self.count("reviews")
        return review

    # ---------------------------------------------------------------- main

    def run(self) -> dict:
        db = self.db

        admin = self.person(DEMO_ADMIN[0], "admin", DEMO_ADMIN[1])
        teachers = [self.person(DEMO_TEACHER[0], "teacher", DEMO_TEACHER[1])]
        while len(teachers) < TEACHERS:
            teachers.append(self.person("Dr. " + self.fake.name(), "teacher"))

        demo_students = [self.person(n, "student", e) for n, e in DEMO_STUDENTS]
        others = [self.person(self.fake.name(), "student") for _ in range(STUDENTS - len(demo_students))]
        # Slot s takes courses s%20, (s+5)%20, (s+10)%20, (s+15)%20: 4 courses each, 60 per course.
        # The demo students sit in slots 0, 20, 40, 60, so all four are in CS301.
        slots: list[User | None] = [None] * STUDENTS
        for i, s in enumerate(demo_students):
            slots[i * 20] = s
        rest = iter(others)
        slots = [s if s is not None else next(rest) for s in slots]

        departments = {}
        for code, name in DEPARTMENTS:
            d = Department(code=code, name=name)
            db.add(d)
            departments[code] = d
        db.flush()
        self.count("departments", len(departments))

        for index, (dept, code, title) in enumerate(COURSES):
            self.course(index, departments[dept], code, title, teachers, slots, admin)
            db.flush()
        db.commit()
        log.info("Seed data loaded: %s", self.counts)
        return self.counts

    def course(
        self, index: int, dept: Department, code: str, title: str, teachers: list[User], slots: list[User], admin: User
    ) -> None:
        db, rng = self.db, self.rng
        teacher = teachers[index % TEACHERS]
        course = Course(
            department_id=dept.id,
            code=code,
            term=TERM,
            title=title,
            description=f"{title}: lectures, assignments and a team project. Invented demo course.",
            join_requests_open=True,
            created_by=admin.id,
            created_at=self.days(-50),
        )
        db.add(course)
        db.flush()
        self.count("courses")
        db.add(
            Enrollment(
                course_id=course.id,
                user_id=teacher.id,
                role="teacher",
                status="active",
                decided_by=admin.id,
                decided_at=self.days(-50),
                created_at=self.days(-50),
            )
        )
        if index >= TEACHERS:  # the last five courses get a second teacher
            co = teachers[(index + 7) % TEACHERS]
            db.add(
                Enrollment(
                    course_id=course.id,
                    user_id=co.id,
                    role="teacher",
                    status="active",
                    decided_by=admin.id,
                    decided_at=self.days(-50),
                    created_at=self.days(-50),
                )
            )

        members = [
            s
            for i, s in enumerate(slots)
            if i % 20 in {index % 20, (index - 5) % 20, (index - 10) % 20, (index - 15) % 20}
        ]
        for s in members:
            db.add(
                Enrollment(
                    course_id=course.id,
                    user_id=s.id,
                    role="student",
                    status="active",
                    decided_by=teacher.id,
                    decided_at=self.days(-45),
                    created_at=self.days(-46),
                )
            )
        self.count("enrolments", len(members))
        outsiders = [s for s in slots if s not in members]
        for s in rng.sample(outsiders, 3):
            db.add(
                Enrollment(
                    course_id=course.id,
                    user_id=s.id,
                    role="student",
                    status="requested",
                    requested_at=self.days(-rng.uniform(0.2, 3)),
                    created_at=self.days(-3),
                )
            )
            self.count("join_requests")

        self.course_invitations(course, teacher, members)
        self.resources(course, teacher)
        self.group_assignment(index, course, teacher, members)
        self.individual_closed(index, course, teacher, members)
        self.individual_open(course, teacher, members)
        for s in members:
            db.add(
                Notification(
                    user_id=s.id,
                    course_id=course.id,
                    event_type="assignment_published",
                    title=f"New assignment in {course.code}: Problem set 2",
                    link=f"/courses/{course.id}",
                    read_at=self.days(-9) if rng.random() < 0.5 else None,
                    created_at=self.days(-10),
                )
            )
        self.count("notifications", len(members))

    def course_invitations(self, course: Course, teacher: User, members: list[User]) -> None:
        for s in self.rng.sample(members, 9):
            self._invitation("course", self._email_of(s), course.id, None, teacher, "accepted", s)
        for n in range(4 if course.id % 2 else 3):
            status = "pending" if n % 2 == 0 else "expired"
            email = f"invitee.{course.code.lower()}.{n}@example.com"
            self._invitation("course", email, course.id, None, teacher, status, None)

    def _email_of(self, user: User) -> str:
        return self.db.query(UserEmail.email).filter(UserEmail.user_id == user.id).scalar()

    def _invitation(self, kind, email, course_id, team_id, by, status, accepted):
        _raw, token_hash = new_token()
        created = self.days(-40 if status != "pending" else -2)
        self.db.add(
            Invitation(
                kind=kind,
                email=email,
                course_id=course_id,
                team_id=team_id,
                role="student",
                invited_by=by.id,
                token_hash=token_hash,
                status=status,
                expires_at=created + timedelta(days=7),
                accepted_user_id=accepted.id if accepted else None,
                responded_at=created + timedelta(days=1) if status in ("accepted",) else None,
                created_at=created,
            )
        )
        self.count("invitations")

    def resources(self, course: Course, teacher: User) -> None:
        for n, title in enumerate(RESOURCE_TITLES):
            published = n < 4
            common = dict(
                course_id=course.id,
                title=title,
                created_by=teacher.id,
                created_at=self.days(-40 + n * 5),
                status="published" if published else "draft",
                published_at=self.days(-40 + n * 5) if published else None,
            )
            if n in (0, 1, 2):
                key, size, _sha = self.pdf(f"{course.code} {title}", [course.title])
                r = Resource(
                    kind="file",
                    storage_key=key,
                    file_name=f"{title.lower().replace(' ', '-')}.pdf",
                    mime_type="application/pdf",
                    size_bytes=size,
                    **common,
                )
            else:
                r = Resource(kind="link", url=f"https://example.com/{course.code.lower()}/{n}", **common)
            self.db.add(r)
            self.count("resources")

    def _assignment(self, course, teacher, title, kind, due, status, rubric, min_team=1, max_team=1):
        a = Assignment(
            course_id=course.id,
            title=title,
            description=f"{title} for {course.code}.",
            kind=kind,
            min_team=min_team,
            max_team=max_team,
            max_files=5,
            requires_pdf=True,
            due_at=due,
            status=status,
            teams_locked=False,
            published_at=due - timedelta(days=21),
            created_by=teacher.id,
        )
        self.db.add(a)
        self.db.flush()
        criteria = []
        for pos, (t, pts) in enumerate(rubric, start=1):
            c = RubricCriterion(assignment_id=a.id, position=pos, title=t, max_points=Decimal(pts))
            self.db.add(c)
            criteria.append(c)
        self.db.flush()
        self.count("assignments")
        return a, criteria

    def _team(self, a: Assignment, name: str, creator: User, people: list[User], when: datetime):
        team = Team(assignment_id=a.id, name=name, created_by=creator.id, created_at=when)
        self.db.add(team)
        self.db.flush()
        for p in people:
            self.db.add(TeamMember(assignment_id=a.id, user_id=p.id, team_id=team.id, status="active", joined_at=when))
        sub = Submission(team_id=team.id, created_at=when)
        self.db.add(sub)
        self.db.flush()
        return team, sub

    def group_assignment(self, index: int, course: Course, teacher: User, members: list[User]) -> None:
        rng, db = self.rng, self.db
        closed = index % 2 == 1
        due = self.days(-5) if closed else self.days(10)
        a, criteria = self._assignment(
            course, teacher, "Course project", "group", due, "closed" if closed else "published", GROUP_RUBRIC, 2, 4
        )
        # In CS301 (the first course) the demo students form the team shown in Figma.
        demo = [m for m in members if m.name in {n for n, _e in DEMO_STUDENTS}] if index == 0 else []
        pool = [m for m in members if m not in demo]
        rng.shuffle(pool)
        groups: list[tuple[str, list[User]]] = []
        if demo:
            by_name = {m.name: m for m in demo}
            groups.append(
                ("Byte Builders", [by_name["Sandeep M"], by_name["Km Shristi Singh"], by_name["Tirtho Paul"]])
            )
            no_team = 2  # Ujjwal Gupta is not in a team: he has a pending invitation to Byte Builders
        else:
            no_team = 3
        pool = pool[: len(pool) - no_team]
        while pool:
            names_taken = {n for n, _ in groups}
            name = f"{rng.choice(TEAM_WORDS)} {rng.choice(TEAM_NOUNS)}"
            while name in names_taken:
                name = f"{rng.choice(TEAM_WORDS)} {rng.choice(TEAM_NOUNS)}"
            groups.append((name, pool[:3]))
            pool = pool[3:]
        at_deadline_done = below_min_done = False
        for g, (name, people) in enumerate(groups):
            created = due - timedelta(days=18)
            team, sub = self._team(a, name, people[0], people, created)
            self.count("group_teams")
            if index in (0, 2, 4, 6) and len(people) > 1:
                for p in people[1:]:
                    self._invitation("team", self._email_of(p), course.id, team.id, people[0], "accepted", p)
            if name == "Byte Builders":
                self._byte_builders(team, sub, people, course, a)
                continue
            n_drafts = rng.randint(1, 4)
            versions = [
                self.draft(
                    sub, n + 1, rng.choice(people), created + timedelta(days=3 + n * 3), f"{course.code} {name}", True
                )
                for n in range(n_drafts)
            ]
            if closed:
                if not at_deadline_done and g == 1:
                    final = self.final(sub, versions[-1], None, due, kind="at_deadline")
                    at_deadline_done = True
                elif not below_min_done and index == 1 and g == 2:
                    for p in people[1:]:  # two members were removed before the deadline
                        db.query(TeamMember).filter_by(assignment_id=a.id, user_id=p.id).update(
                            {"status": "removed", "left_at": due - timedelta(days=2)}
                        )
                    final = self.final(sub, versions[-1], None, due, kind="at_deadline", below_min=True)
                    below_min_done = True
                else:
                    final = self.final(sub, rng.choice(versions), rng.choice(people), due - timedelta(days=1))
                sub.closed_at = due + timedelta(minutes=1)
                review = self.review(final, criteria, teacher, due + timedelta(days=3))
                if g in (3, 7):
                    db.add(
                        MemberAdjustment(
                            review_id=review.id,
                            user_id=people[-1].id,
                            percent=Decimal("-10.0"),
                            reason="Uploaded no drafts and missed meetings.",
                            set_by=teacher.id,
                            set_at=due + timedelta(days=3),
                        )
                    )
                    self.count("adjustments")
            elif rng.random() < 0.58:
                self.final(sub, versions[-1], rng.choice(people), created + timedelta(days=12))

    def _byte_builders(self, team, sub, people, course, a) -> None:
        sandeep, shristi, tirtho = people
        start = a.due_at - timedelta(days=12)
        # As in the Figma screens: drafts v1 to v3, and v2 submitted as the final by Km Shristi Singh.
        self.draft(sub, 1, sandeep, start, "CS301 Byte Builders", True)
        v2 = self.draft(sub, 2, shristi, start + timedelta(days=3), "CS301 Byte Builders", True)
        self.draft(sub, 3, tirtho, start + timedelta(days=5), "CS301 Byte Builders", True)
        self.final(sub, v2, shristi, start + timedelta(days=4))
        ujjwal = self.db.query(User).filter_by(name="Ujjwal Gupta").one()
        self._invitation("team", self._email_of(ujjwal), course.id, team.id, sandeep, "pending", None)
        self.db.query(Invitation).filter_by(team_id=team.id, status="pending").update(
            {"expires_at": self.days(6), "created_at": self.days(-1)}
        )

    def individual_closed(self, index: int, course: Course, teacher: User, members: list[User]) -> None:
        rng = self.rng
        due = self.days(-12)
        a, criteria = self._assignment(course, teacher, "Problem set 1", "individual", due, "closed", INDIVIDUAL_RUBRIC)
        missing = set(rng.sample(range(len(members)), 6))
        for i, s in enumerate(members):
            if i in missing and s.name not in {n for n, _ in DEMO_STUDENTS}:
                continue
            team, sub = self._team(a, f"Individual {s.id}", s, [s], due - timedelta(days=10))
            self.count("individual_teams")
            v = self.draft(sub, 1, s, due - timedelta(days=rng.uniform(1, 6)), f"{course.code} Problem set 1", False)
            final = self.final(sub, v, s, v.created_at + timedelta(minutes=5))
            sub.closed_at = due + timedelta(minutes=1)
            fixed = None
            if s.name == "Sandeep M" and course.code == "CS301":
                fixed = [Decimal("8.5"), Decimal("9.0")]
            self.review(final, criteria, teacher, due + timedelta(days=4), fixed)
            if index < 5 or s.name == "Sandeep M":
                self.db.add(
                    Notification(
                        user_id=s.id,
                        course_id=course.id,
                        event_type="marks_released",
                        title="Marks released for Problem set 1",
                        link=f"/teams/{team.id}/marks",
                        created_at=due + timedelta(days=4),
                    )
                )
                self.count("notifications")

    def individual_open(self, course: Course, teacher: User, members: list[User]) -> None:
        due = self.days(14)
        a, _criteria = self._assignment(
            course, teacher, "Problem set 2", "individual", due, "published", INDIVIDUAL_RUBRIC
        )
        for s in self.rng.sample(members, 18):
            team, sub = self._team(a, f"Individual {s.id}", s, [s], self.days(-2))
            self.count("individual_teams")
            self.draft(sub, 1, s, self.days(-1), f"{course.code} Problem set 2", False)


def already_seeded(db: Session) -> bool:
    return db.scalar(select(Department.id).limit(1)) is not None


def seed(db: Session, storage: LocalStorage, now: datetime | None = None) -> dict:
    """Load the demo data once. Running it again changes nothing and returns {}."""
    if already_seeded(db):
        log.info("Seed data already present; nothing to do.")
        return {}
    return Seeder(db, storage, now or utcnow()).run()


if __name__ == "__main__":
    from app.config import get_settings
    from app.db import get_session_factory

    logging.basicConfig(level=logging.INFO)
    session = get_session_factory()()
    try:
        seed(session, LocalStorage(get_settings().upload_dir))
    finally:
        session.close()
