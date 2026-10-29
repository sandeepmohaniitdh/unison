"""Every event that notifies someone, and how it is delivered.

in_app_only: never emailed (draft uploads, team changes).
always_email: cannot be switched off (people may not have a dashboard yet).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    label: str
    in_app_only: bool = False
    always_email: bool = False


EVENTS: dict[str, Event] = {
    "course_invitation": Event("Invitation to a course", always_email=True),
    "team_invitation": Event("Invitation to a team", always_email=True),
    "staff_invitation": Event("Invitation to join as staff", always_email=True),
    "join_request_received": Event("Join request received"),
    "enrolment_approved": Event("Join request approved"),
    "enrolment_rejected": Event("Join request rejected"),
    "resources_published": Event("New resources published"),
    "assignment_published": Event("New assignment published"),
    "deadline_extended": Event("Deadline extended"),
    "draft_uploaded": Event("Draft uploaded by a teammate", in_app_only=True),
    "team_member_joined": Event("Someone joined your team", in_app_only=True),
    "team_member_left": Event("Someone left your team", in_app_only=True),
    "final_submitted": Event("Final submitted"),
    "final_replaced": Event("Final replaced"),
    "final_at_deadline": Event("Final submitted at the deadline"),
    "marks_released": Event("Marks released"),
    "removed_from_course": Event("Removed from a course"),
    "account_deletion_requested": Event("A member deleted their account"),
}

# Event types a user can switch email off for, on the profile page.
OPTIONAL_EMAIL_EVENTS = [key for key, ev in EVENTS.items() if not ev.in_app_only and not ev.always_email]
# Event types a teacher can set email rules for, per course.
COURSE_RULE_EVENTS = OPTIONAL_EMAIL_EVENTS
