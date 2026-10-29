"""The synthetic dataset."""

from sqlalchemy import func, select

from app.modules.courses.models import Course, Enrollment
from app.modules.reviews.models import Review
from app.modules.teams.models import Team
from app.modules.users.models import User
from app.seed.run import seed


def test_seed_data(db, storage, clock):
    counts = seed(db, storage, clock.now())
    assert (counts["students"], counts["teachers"], counts["courses"], counts["enrolments"]) == (300, 15, 20, 1200)
    assert counts["join_requests"] == 60 and counts["assignments"] == 60 and counts["group_teams"] == 380
    assert db.scalar(select(func.count()).where(Review.status == "released")) > 1200
    cs301 = db.scalar(select(Course).where(Course.code == "CS301"))
    teacher = db.scalar(
        select(User)
        .join(Enrollment, Enrollment.user_id == User.id)
        .where(Enrollment.course_id == cs301.id, Enrollment.role == "teacher")
    )
    assert teacher.name == "Dr. Kavya Menon"
    assert db.scalar(select(Team).where(Team.name == "Byte Builders")) is not None

    # Passwords are hashed one by one, like real sign-ups (each hash has its own salt).
    hashes = db.scalars(select(User.password_hash).limit(5)).all()
    assert all(h.startswith("$argon2") for h in hashes)
    assert len(set(hashes)) == len(hashes)

    # Safe to re-run: the second run changes nothing.
    users = db.scalar(select(func.count()).select_from(User))
    assert seed(db, storage, clock.now()) == {}
    assert db.scalar(select(func.count()).select_from(User)) == users
