"""Who may do what in a course.

Permissions are checked in four layers:
1. a session (otherwise 401), see deps.get_current_user;
2. the global role: student, teacher or admin;
3. the role in this course: an active enrolment as teacher or student
   (otherwise 403). Administrators count as teachers of every course, and
   what they do there is written to the audit log with as_admin = true;
4. ownership of the item, for example membership of this team
   (checked in each module's service).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, forbidden, not_found
from app.modules.courses.models import Course, Enrollment
from app.modules.users.models import User


@dataclass
class CourseAccess:
    course: Course
    role: str | None  # "teacher", "student" or None
    as_admin: bool  # True when an admin acts as teacher without being one

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    @property
    def is_member(self) -> bool:
        return self.role is not None


def get_course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise not_found("Course")
    return course


def course_access(db: Session, user: User | None, course_id: int) -> CourseAccess:
    course = get_course(db, course_id)
    if user is None:
        return CourseAccess(course, None, False)
    enrollment = db.scalar(
        select(Enrollment).where(
            Enrollment.course_id == course_id,
            Enrollment.user_id == user.id,
            Enrollment.status == "active",
        )
    )
    if enrollment is not None and enrollment.role == "teacher":
        return CourseAccess(course, "teacher", False)
    if user.role == "admin":
        return CourseAccess(course, "teacher", True)
    if enrollment is not None:
        return CourseAccess(course, "student", False)
    return CourseAccess(course, None, False)


def require_teacher(db: Session, user: User, course_id: int, *, writable: bool = True) -> CourseAccess:
    """The user must teach this course (or be an admin). `writable` also refuses archived courses."""
    access = course_access(db, user, course_id)
    if not access.is_teacher:
        raise forbidden("Only the course's teachers can do this.", "NOT_COURSE_TEACHER")
    if writable:
        require_not_archived(access.course)
    return access


def require_member(db: Session, user: User, course_id: int) -> CourseAccess:
    """The user must be an active student or teacher of the course (or an admin)."""
    access = course_access(db, user, course_id)
    if not access.is_member:
        raise forbidden("Only members of this course can see this.", "NOT_COURSE_MEMBER")
    return access


def require_student(db: Session, user: User, course_id: int) -> CourseAccess:
    access = course_access(db, user, course_id)
    if access.role != "student":
        raise forbidden("Only enrolled students can do this.", "NOT_COURSE_STUDENT")
    require_not_archived(access.course)
    return access


def require_not_archived(course: Course) -> None:
    if course.archived_at is not None:
        raise conflict("COURSE_ARCHIVED", "This course is archived and read-only.")


def teacher_ids(db: Session, course_id: int) -> list[int]:
    """Active teachers of a course (they receive the teachers' notifications)."""
    return list(
        db.scalars(
            select(Enrollment.user_id).where(
                Enrollment.course_id == course_id,
                Enrollment.role == "teacher",
                Enrollment.status == "active",
            )
        )
    )


def student_ids(db: Session, course_id: int) -> list[int]:
    return list(
        db.scalars(
            select(Enrollment.user_id).where(
                Enrollment.course_id == course_id,
                Enrollment.role == "student",
                Enrollment.status == "active",
            )
        )
    )
