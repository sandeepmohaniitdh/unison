"""Course resources: files (from the allowlist, up to 25 MB) and links.

Resources start as drafts that only the course's teachers see. Publishing
makes them visible to enrolled students and notifies them; several published
together give one notification, and emails within 10 minutes are bundled.
"""

from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import conflict, not_found
from app.core.pagination import PageParams, paginate
from app.core.permissions import require_member, require_teacher, student_ids
from app.core.storage import MB, RESOURCE_EXTENSIONS, LocalStorage
from app.core.time import Clock
from app.modules.admin.service import audit
from app.modules.notifications.service import notify, queue_resource_email
from app.modules.resources.models import Resource
from app.modules.users.models import User

MAX_RESOURCE_BYTES = 25 * MB


def item(db: Session, r: Resource) -> dict:
    author = db.get(User, r.created_by)
    return {
        "id": r.id,
        "course_id": r.course_id,
        "title": r.title,
        "description": r.description,
        "kind": r.kind,
        "file_name": r.file_name,
        "mime_type": r.mime_type,
        "size_bytes": r.size_bytes,
        "url": r.url,
        "status": r.status,
        "published_at": r.published_at,
        "created_by": {"id": author.id, "name": author.name},
        "created_at": r.created_at,
    }


def _get(db: Session, resource_id: int) -> Resource:
    r = db.get(Resource, resource_id)
    if r is None:
        raise not_found("Resource")
    return r


def list_for_course(db: Session, user: User, course_id: int, params: PageParams, status: str | None) -> dict:
    access = require_member(db, user, course_id)
    stmt = select(Resource).where(Resource.course_id == course_id)
    if not access.is_teacher:
        stmt = stmt.where(Resource.status == "published")
    elif status:
        stmt = stmt.where(Resource.status == status)
    stmt = stmt.order_by(Resource.status.desc(), Resource.published_at.desc(), Resource.id.desc())
    return paginate(db, stmt, params, lambda r: item(db, r))


def add_file(
    db: Session,
    user: User,
    course_id: int,
    title: str,
    description: str | None,
    upload: BinaryIO,
    file_name: str | None,
    storage: LocalStorage,
    clock: Clock,
) -> dict:
    access = require_teacher(db, user, course_id)
    stored = storage.save(upload, file_name, RESOURCE_EXTENSIONS, MAX_RESOURCE_BYTES)
    r = Resource(
        course_id=course_id,
        title=title.strip(),
        description=description,
        kind="file",
        storage_key=stored.key,
        file_name=stored.file_name,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        status="draft",
        created_by=user.id,
        created_at=clock.now(),
    )
    db.add(r)
    db.flush()
    if access.as_admin:
        audit(db, user, "resource_added", "resources", r.id, course_id=course_id, as_admin=True)
    db.commit()
    return item(db, r)


def add_link(
    db: Session, user: User, course_id: int, title: str, description: str | None, url: str, clock: Clock
) -> dict:
    access = require_teacher(db, user, course_id)
    r = Resource(
        course_id=course_id,
        title=title.strip(),
        description=description,
        kind="link",
        url=url,
        status="draft",
        created_by=user.id,
        created_at=clock.now(),
    )
    db.add(r)
    db.flush()
    if access.as_admin:
        audit(db, user, "resource_added", "resources", r.id, course_id=course_id, as_admin=True)
    db.commit()
    return item(db, r)


def update(db: Session, user: User, resource_id: int, data: dict) -> dict:
    r = _get(db, resource_id)
    require_teacher(db, user, r.course_id)
    if "url" in data and data["url"] is not None:
        if r.kind != "link":
            raise conflict("NOT_A_LINK", "Only link resources have a URL.")
        data["url"] = str(data["url"])
    for key, value in data.items():
        if value is not None or key == "description":
            setattr(r, key, value)
    db.commit()
    return item(db, r)


def remove(db: Session, user: User, resource_id: int, storage: LocalStorage) -> None:
    r = _get(db, resource_id)
    access = require_teacher(db, user, r.course_id)
    if access.as_admin:
        audit(
            db,
            user,
            "resource_deleted",
            "resources",
            r.id,
            course_id=r.course_id,
            as_admin=True,
            before={"title": r.title},
        )
    key = r.storage_key
    db.delete(r)
    db.commit()
    if key:
        storage.delete(key)


def publish(db: Session, user: User, course_id: int, resource_ids: list[int], send: bool, clock: Clock) -> list[dict]:
    access = require_teacher(db, user, course_id)
    now = clock.now()
    rows = db.scalars(select(Resource).where(Resource.id.in_(resource_ids), Resource.course_id == course_id)).all()
    if len(rows) != len(set(resource_ids)):
        raise not_found("Resource")
    newly = [r for r in rows if r.status == "draft"]
    for r in newly:
        r.status = "published"
        r.published_at = now
    if newly and send:
        course = access.course
        titles = [r.title for r in newly]
        title = (
            f"New in {course.code}: {titles[0]}"
            if len(titles) == 1
            else f"{len(titles)} new resources in {course.code}"
        )
        students = student_ids(db, course_id)
        # In-app now; emails wait 10 minutes so close publishes become one email.
        notify(
            db,
            "resources_published",
            students,
            title,
            f"/courses/{course_id}#resources",
            now,
            course_id=course_id,
            send_email=False,
        )
        for student in db.scalars(select(User).where(User.id.in_(students or [0]), User.status == "active")):
            queue_resource_email(db, student, course, titles, now)
    if access.as_admin:
        audit(
            db,
            user,
            "resources_published",
            "courses",
            course_id,
            course_id=course_id,
            as_admin=True,
            after={"resource_ids": [r.id for r in newly]},
        )
    db.commit()
    return [item(db, r) for r in rows]


def download(db: Session, user: User, resource_id: int, storage: LocalStorage):
    r = _get(db, resource_id)
    access = require_member(db, user, r.course_id)
    if r.status != "published" and not access.is_teacher:
        raise not_found("Resource")
    if r.kind != "file":
        raise conflict("RESOURCE_IS_LINK", "This resource is a link, not a file.", {"url": r.url})
    return storage.path(r.storage_key), r.file_name, r.mime_type
