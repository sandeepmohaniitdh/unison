"""Notifications and the email outbox.

Every event in the app calls notify() inside the same database transaction
as the change. notify() writes one in-app notification per recipient and,
after checking the course's email rule and each person's email switch, one
outbox row per email. The worker sends the outbox later (send_outbox), so an
email exists only if the change was really saved, and a mail server outage
never blocks the site.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.errors import bad_request, not_found
from app.core.mailer import Mailer
from app.core.pagination import PageParams, paginate
from app.core.permissions import teacher_ids
from app.core.time import Clock
from app.modules.notifications.emails import render
from app.modules.notifications.events import COURSE_RULE_EVENTS, EVENTS, OPTIONAL_EMAIL_EVENTS
from app.modules.notifications.models import EmailOutbox, Notification, NotificationPreference, NotificationRule
from app.modules.users.models import User, UserEmail

log = logging.getLogger("unison.notifications")

RETRY_MINUTES = [1, 5, 15, 60]
RESOURCE_BUNDLE_MINUTES = 10


# ---------------------------------------------------------------- writing


def notify(
    db: Session,
    event: str,
    user_ids: list[int] | set[int],
    title: str,
    link: str,
    now: datetime,
    *,
    course_id: int | None = None,
    send_email: bool = True,
) -> None:
    """Notify these users about an event (in the app, and by email if allowed).

    send_email=False is for callers that queue their own email (resources are bundled).
    """
    info = EVENTS[event]
    recipients = sorted(set(user_ids))
    if not recipients:
        return
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(recipients), User.status == "active"))}
    teachers = set(teacher_ids(db, course_id)) if course_id else set()
    rule = db.get(NotificationRule, (course_id, event)) if course_id else None
    for user_id in recipients:
        user = users.get(user_id)
        if user is None:
            continue
        note = Notification(
            user_id=user_id, course_id=course_id, event_type=event, title=title[:200], link=link, created_at=now
        )
        db.add(note)
        db.flush()  # gives note.id for the email's dedup key
        if info.in_app_only or not send_email:
            continue
        if rule is not None and not info.always_email:
            allowed = rule.email_teachers if user_id in teachers else rule.email_members
            if not allowed:
                continue
        if not info.always_email and not email_enabled(db, user_id, event):
            continue
        email = primary_email(db, user_id)
        if email:
            queue_email(
                db,
                to=email,
                user_id=user_id,
                template="notification",
                payload={"name": user.name, "title": title, "link": link},
                dedup_key=f"notification:{note.id}",
                now=now,
            )


def queue_email(
    db: Session,
    *,
    to: str,
    template: str,
    payload: dict,
    dedup_key: str,
    now: datetime,
    user_id: int | None = None,
    send_after: datetime | None = None,
) -> None:
    """Add an email to the outbox. The same dedup_key is never queued twice."""
    exists = db.scalar(select(EmailOutbox.id).where(EmailOutbox.dedup_key == dedup_key))
    if exists:
        return
    db.add(
        EmailOutbox(
            user_id=user_id,
            to_email=to,
            template=template,
            payload=payload,
            dedup_key=dedup_key[:120],
            status="pending",
            attempts=0,
            send_after=send_after or now,
        )
    )


def queue_resource_email(db: Session, user: User, course, titles: list[str], now: datetime) -> None:
    """Resources published within 10 minutes reach each student as one email.

    If this student already has a waiting email for this course, the new
    titles are added to it; otherwise a new email waits 10 minutes.
    """
    if not email_enabled(db, user.id, "resources_published"):
        return
    rule = db.get(NotificationRule, (course.id, "resources_published"))
    if rule is not None and not rule.email_members:
        return
    waiting = db.scalar(
        select(EmailOutbox).where(
            EmailOutbox.user_id == user.id,
            EmailOutbox.template == "resources_published",
            EmailOutbox.status == "pending",
            EmailOutbox.send_after > now,
            EmailOutbox.dedup_key.like(f"resources:{course.id}:{user.id}:%"),
        )
    )
    if waiting is not None:
        payload = dict(waiting.payload)
        payload["titles"] = payload["titles"] + titles
        waiting.payload = payload  # a new dict, so SQLAlchemy sees the change
        return
    email = primary_email(db, user.id)
    if not email:
        return
    queue_email(
        db,
        to=email,
        user_id=user.id,
        template="resources_published",
        payload={
            "name": user.name,
            "course": f"{course.code} {course.title}",
            "titles": titles,
            "link": f"/courses/{course.id}",
        },
        dedup_key=f"resources:{course.id}:{user.id}:{now:%Y%m%d%H%M%S%f}",
        now=now,
        send_after=now + timedelta(minutes=RESOURCE_BUNDLE_MINUTES),
    )


def primary_email(db: Session, user_id: int) -> str | None:
    return db.scalar(select(UserEmail.email).where(UserEmail.user_id == user_id, UserEmail.is_primary))


def email_enabled(db: Session, user_id: int, event: str) -> bool:
    pref = db.get(NotificationPreference, (user_id, event))
    return pref is None or pref.email_enabled


# ---------------------------------------------------------------- reading


def notification_item(n: Notification) -> dict:
    return {
        "id": n.id,
        "event_type": n.event_type,
        "title": n.title,
        "link": n.link,
        "course_id": n.course_id,
        "read": n.read_at is not None,
        "created_at": n.created_at,
    }


def list_notifications(db: Session, user: User, params: PageParams, unread_only: bool) -> dict:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
    return paginate(db, stmt, params, notification_item)


def unread_count(db: Session, user: User) -> int:
    return db.scalar(select(func.count()).where(Notification.user_id == user.id, Notification.read_at.is_(None))) or 0


def mark_read(db: Session, user: User, notification_id: int, clock: Clock) -> None:
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise not_found("Notification")
    if note.read_at is None:
        note.read_at = clock.now()
        db.commit()


def mark_all_read(db: Session, user: User, clock: Clock) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=clock.now())
    )
    db.commit()
    return result.rowcount or 0


# ---------------------------------------------------------------- preferences and course rules


def get_preferences(db: Session, user: User) -> list[dict]:
    stored = {
        p.event_type: p.email_enabled
        for p in db.scalars(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
    }
    return [
        {"event_type": key, "label": EVENTS[key].label, "email_enabled": stored.get(key, True)}
        for key in OPTIONAL_EMAIL_EVENTS
    ]


def set_preferences(db: Session, user: User, items: list[dict]) -> list[dict]:
    for item in items:
        event = item["event_type"]
        if event not in OPTIONAL_EMAIL_EVENTS:
            raise bad_request("UNKNOWN_EVENT_TYPE", f"{event} has no email switch.")
        pref = db.get(NotificationPreference, (user.id, event))
        if pref is None:
            db.add(NotificationPreference(user_id=user.id, event_type=event, email_enabled=item["email_enabled"]))
        else:
            pref.email_enabled = item["email_enabled"]
    db.commit()
    return get_preferences(db, user)


def get_course_rules(db: Session, course_id: int) -> list[dict]:
    stored = {
        r.event_type: r for r in db.scalars(select(NotificationRule).where(NotificationRule.course_id == course_id))
    }
    out = []
    for key in COURSE_RULE_EVENTS:
        rule = stored.get(key)
        out.append(
            {
                "event_type": key,
                "label": EVENTS[key].label,
                "email_members": rule.email_members if rule else True,
                "email_teachers": rule.email_teachers if rule else True,
            }
        )
    return out


def set_course_rules(db: Session, course_id: int, items: list[dict]) -> list[dict]:
    for item in items:
        event = item["event_type"]
        if event not in COURSE_RULE_EVENTS:
            raise bad_request("UNKNOWN_EVENT_TYPE", f"{event} has no email rule.")
        rule = db.get(NotificationRule, (course_id, event))
        if rule is None:
            rule = NotificationRule(course_id=course_id, event_type=event)
            db.add(rule)
        rule.email_members = item["email_members"]
        rule.email_teachers = item["email_teachers"]
    db.commit()
    return get_course_rules(db, course_id)


# ---------------------------------------------------------------- worker job


def send_outbox(db: Session, mailer: Mailer, clock: Clock, batch: int = 50) -> int:
    """Send due emails. Failures are retried after 1, 5, 15 and 60 minutes, then given up.

    SKIP LOCKED lets two workers run without sending the same email twice.
    """
    now = clock.now()
    rows = db.scalars(
        select(EmailOutbox)
        .where(EmailOutbox.status == "pending", EmailOutbox.send_after <= now)
        .order_by(EmailOutbox.send_after, EmailOutbox.id)
        .limit(batch)
        .with_for_update(skip_locked=True)
    ).all()
    sent = 0
    for row in rows:
        subject, body = render(row.template, row.payload)
        try:
            mailer.send(row.to_email, subject, body)
        except Exception as exc:  # noqa: BLE001 - any SMTP problem means "try later"
            row.attempts += 1
            row.last_error = str(exc)[:300]
            if row.attempts > len(RETRY_MINUTES):
                row.status = "failed"
            else:
                row.send_after = now + timedelta(minutes=RETRY_MINUTES[row.attempts - 1])
            log.warning("Email %s failed (attempt %s): %s", row.id, row.attempts, exc)
            continue
        row.status = "sent"
        row.sent_at = now
        row.attempts += 1
        if "token" in row.payload:
            # The raw link token is needed only to send; don't keep it.
            row.payload = {**row.payload, "token": "(removed after sending)"}
        sent += 1
    db.commit()
    return sent
