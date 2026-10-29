"""Imports every model, so Base.metadata knows all 29 tables.

Alembic and the tests import this module.
"""

from app.db import Base
from app.modules.admin.models import AuditLog, PlatformSetting
from app.modules.ai.models import AiFeedback
from app.modules.assignments.models import Assignment, RubricCriterion
from app.modules.auth.models import EmailToken, LoginAttempt, OAuthIdentity, UserSession
from app.modules.courses.models import Course, Department, Enrollment
from app.modules.invitations.models import Invitation
from app.modules.notifications.models import EmailOutbox, Notification, NotificationPreference, NotificationRule
from app.modules.resources.models import Resource
from app.modules.reviews.models import MemberAdjustment, Review, ReviewScore
from app.modules.submissions.models import FinalSubmission, Submission, SubmissionFile, SubmissionVersion
from app.modules.teams.models import Team, TeamMember
from app.modules.users.models import User, UserEmail

__all__ = [
    "Base",
    "AuditLog",
    "PlatformSetting",
    "AiFeedback",
    "Assignment",
    "RubricCriterion",
    "EmailToken",
    "LoginAttempt",
    "OAuthIdentity",
    "UserSession",
    "Course",
    "Department",
    "Enrollment",
    "Invitation",
    "EmailOutbox",
    "Notification",
    "NotificationPreference",
    "NotificationRule",
    "Resource",
    "MemberAdjustment",
    "Review",
    "ReviewScore",
    "FinalSubmission",
    "Submission",
    "SubmissionFile",
    "SubmissionVersion",
    "Team",
    "TeamMember",
    "User",
    "UserEmail",
]
