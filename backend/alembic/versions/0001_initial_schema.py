"""initial schema: all 29 tables

Revision ID: 0001
Revises:
Create Date: 2026-10-25 14:11:33.102001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# The column types are the shared ones from app/core/types.py (BIGINT UNSIGNED ids, DATETIME(3), ...).
from app.core.types import ID, IP_ADDRESS, SMALL_UINT, TIMESTAMP, TINY_UINT, UINT

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", ID, nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("code", name=op.f("uq_departments_code")),
        sa.UniqueConstraint("name", name=op.f("uq_departments_name")),
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", ID, nullable=False),
        sa.Column("kind", sa.Enum("login", "signup", name="login_attempt_kind"), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("ip", IP_ADDRESS, nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_attempts")),
    )
    op.create_index(
        "ix_login_attempts_email_ip_created_at", "login_attempts", ["email", "ip", "created_at"], unique=False
    )
    op.create_index("ix_login_attempts_ip_created_at", "login_attempts", ["ip", "created_at"], unique=False)
    op.create_table(
        "users",
        sa.Column("id", ID, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.Enum("student", "teacher", "admin", name="user_role"), nullable=False),
        sa.Column(
            "status", sa.Enum("active", "suspended", "deactivated", "deleted", name="user_status"), nullable=False
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("consent_at", TIMESTAMP, nullable=False),
        sa.Column("deletion_requested_at", TIMESTAMP, nullable=True),
        sa.Column("deleted_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "courses",
        sa.Column("id", ID, nullable=False),
        sa.Column("department_id", ID, nullable=False),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("term", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("join_requests_open", sa.Boolean(), nullable=False),
        sa.Column("created_by", ID, nullable=False),
        sa.Column("archived_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_courses_created_by"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], name=op.f("fk_courses_department_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("code", "term", name=op.f("uq_courses_code_term")),
    )
    op.create_index(
        "ix_courses_code_title_fulltext", "courses", ["code", "title"], unique=False, mysql_prefix="FULLTEXT"
    )
    op.create_index(op.f("ix_courses_created_by"), "courses", ["created_by"], unique=False)
    op.create_index(op.f("ix_courses_department_id"), "courses", ["department_id"], unique=False)
    op.create_table(
        "email_outbox",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=True),
        sa.Column("to_email", sa.String(length=254), nullable=False),
        sa.Column("template", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("dedup_key", sa.String(length=120), nullable=False),
        sa.Column(
            "status", sa.Enum("pending", "sending", "sent", "failed", name="email_outbox_status"), nullable=False
        ),
        sa.Column("attempts", TINY_UINT, nullable=False),
        sa.Column("send_after", TIMESTAMP, nullable=False),
        sa.Column("sent_at", TIMESTAMP, nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_email_outbox_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_outbox")),
        sa.UniqueConstraint("dedup_key", name=op.f("uq_email_outbox_dedup_key")),
    )
    op.create_index("ix_email_outbox_status_send_after", "email_outbox", ["status", "send_after"], unique=False)
    op.create_index(op.f("ix_email_outbox_user_id"), "email_outbox", ["user_id"], unique=False)
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", ID, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_notification_preferences_user_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("user_id", "event_type", name=op.f("pk_notification_preferences")),
    )
    op.create_table(
        "oauth_identities",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("provider", sa.Enum("google", name="oauth_provider"), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_oauth_identities_user_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_identities")),
        sa.UniqueConstraint("provider", "subject", name=op.f("uq_oauth_identities_provider_subject")),
    )
    op.create_index(op.f("ix_oauth_identities_user_id"), "oauth_identities", ["user_id"], unique=False)
    op.create_table(
        "platform_settings",
        sa.Column("setting_key", sa.String(length=60), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", ID, nullable=True),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name=op.f("fk_platform_settings_updated_by"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("setting_key", name=op.f("pk_platform_settings")),
    )
    op.create_index(op.f("ix_platform_settings_updated_by"), "platform_settings", ["updated_by"], unique=False)
    op.create_table(
        "sessions",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("last_seen_at", TIMESTAMP, nullable=False),
        sa.Column("revoked_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_sessions_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_table(
        "user_emails",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column(
            "primary_user_id",
            ID,
            sa.Computed("CASE WHEN is_primary THEN user_id ELSE NULL END", persisted=True),
            nullable=True,
        ),
        sa.Column("verified_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_emails_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_emails")),
        sa.UniqueConstraint("email", name=op.f("uq_user_emails_email")),
    )
    op.create_index(op.f("ix_user_emails_user_id"), "user_emails", ["user_id"], unique=False)
    op.create_index("uq_user_emails_primary_user_id", "user_emails", ["primary_user_id"], unique=True)
    op.create_table(
        "assignments",
        sa.Column("id", ID, nullable=False),
        sa.Column("course_id", ID, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.Enum("individual", "group", name="assignment_kind"), nullable=False),
        sa.Column("min_team", TINY_UINT, nullable=False),
        sa.Column("max_team", TINY_UINT, nullable=False),
        sa.Column("max_files", TINY_UINT, nullable=False),
        sa.Column("requires_pdf", sa.Boolean(), nullable=False),
        sa.Column("due_at", TIMESTAMP, nullable=False),
        sa.Column("status", sa.Enum("draft", "published", "closed", name="assignment_status"), nullable=False),
        sa.Column("teams_locked", sa.Boolean(), nullable=False),
        sa.Column("published_at", TIMESTAMP, nullable=True),
        sa.Column("created_by", ID, nullable=False),
        sa.CheckConstraint("max_team >= min_team", name=op.f("ck_assignments_team_size")),
        sa.CheckConstraint("min_team >= 1", name=op.f("ck_assignments_min_team_positive")),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_assignments_course_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_assignments_created_by"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
    )
    op.create_index(
        "ix_assignments_course_id_status_due_at", "assignments", ["course_id", "status", "due_at"], unique=False
    )
    op.create_index(op.f("ix_assignments_created_by"), "assignments", ["created_by"], unique=False)
    op.create_index("ix_assignments_status_due_at", "assignments", ["status", "due_at"], unique=False)
    op.create_table(
        "audit_log",
        sa.Column("id", ID, nullable=False),
        sa.Column("actor_id", ID, nullable=False),
        sa.Column("as_admin", sa.Boolean(), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", ID, nullable=False),
        sa.Column("course_id", ID, nullable=True),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_audit_log_actor_id"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_audit_log_course_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_actor_id_created_at", "audit_log", ["actor_id", "created_at"], unique=False)
    op.create_index(op.f("ix_audit_log_course_id"), "audit_log", ["course_id"], unique=False)
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], unique=False)
    op.create_index("ix_audit_log_target_type_target_id", "audit_log", ["target_type", "target_id"], unique=False)
    op.create_table(
        "email_tokens",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("user_email_id", ID, nullable=True),
        sa.Column("purpose", sa.Enum("verify_email", "reset_password", name="email_token_purpose"), nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("used_at", TIMESTAMP, nullable=True),
        sa.ForeignKeyConstraint(
            ["user_email_id"], ["user_emails.id"], name=op.f("fk_email_tokens_user_email_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_email_tokens_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_email_tokens_token_hash")),
    )
    op.create_index(op.f("ix_email_tokens_user_email_id"), "email_tokens", ["user_email_id"], unique=False)
    op.create_index(op.f("ix_email_tokens_user_id"), "email_tokens", ["user_id"], unique=False)
    op.create_table(
        "enrollments",
        sa.Column("id", ID, nullable=False),
        sa.Column("course_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("role", sa.Enum("student", "teacher", name="enrollment_role"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("requested", "active", "rejected", "removed", "left", name="enrollment_status"),
            nullable=False,
        ),
        sa.Column("requested_at", TIMESTAMP, nullable=True),
        sa.Column("decided_by", ID, nullable=True),
        sa.Column("decided_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_enrollments_course_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["users.id"], name=op.f("fk_enrollments_decided_by"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_enrollments_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enrollments")),
        sa.UniqueConstraint("course_id", "user_id", name=op.f("uq_enrollments_course_id_user_id")),
    )
    op.create_index("ix_enrollments_course_id_status", "enrollments", ["course_id", "status"], unique=False)
    op.create_index(op.f("ix_enrollments_decided_by"), "enrollments", ["decided_by"], unique=False)
    op.create_index("ix_enrollments_user_id_status", "enrollments", ["user_id", "status"], unique=False)
    op.create_table(
        "notification_rules",
        sa.Column("course_id", ID, nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("email_members", sa.Boolean(), nullable=False),
        sa.Column("email_teachers", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_notification_rules_course_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("course_id", "event_type", name=op.f("pk_notification_rules")),
    )
    op.create_table(
        "notifications",
        sa.Column("id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("course_id", ID, nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("link", sa.String(length=300), nullable=False),
        sa.Column("read_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_notifications_course_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_notifications_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_course_id"), "notifications", ["course_id"], unique=False)
    op.create_index(
        "ix_notifications_user_id_read_at_created_at",
        "notifications",
        ["user_id", "read_at", "created_at"],
        unique=False,
    )
    op.create_table(
        "resources",
        sa.Column("id", ID, nullable=False),
        sa.Column("course_id", ID, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kind", sa.Enum("file", "link", name="resource_kind"), nullable=False),
        sa.Column("storage_key", sa.CHAR(length=32), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", UINT, nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.Enum("draft", "published", name="resource_status"), nullable=False),
        sa.Column("published_at", TIMESTAMP, nullable=True),
        sa.Column("created_by", ID, nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_resources_course_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_resources_created_by"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_resources_storage_key")),
    )
    op.create_index(
        "ix_resources_course_id_status_published_at", "resources", ["course_id", "status", "published_at"], unique=False
    )
    op.create_index(op.f("ix_resources_created_by"), "resources", ["created_by"], unique=False)
    op.create_table(
        "rubric_criteria",
        sa.Column("id", ID, nullable=False),
        sa.Column("assignment_id", ID, nullable=False),
        sa.Column("position", TINY_UINT, nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("max_points", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.CheckConstraint("max_points > 0", name=op.f("ck_rubric_criteria_max_points_positive")),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], name=op.f("fk_rubric_criteria_assignment_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rubric_criteria")),
        sa.UniqueConstraint("assignment_id", "position", name=op.f("uq_rubric_criteria_assignment_id_position")),
    )
    op.create_table(
        "teams",
        sa.Column("id", ID, nullable=False),
        sa.Column("assignment_id", ID, nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("created_by", ID, nullable=False),
        sa.Column("closed_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], name=op.f("fk_teams_assignment_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_teams_created_by"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teams")),
        sa.UniqueConstraint("assignment_id", "name", name=op.f("uq_teams_assignment_id_name")),
        sa.UniqueConstraint("id", "assignment_id", name=op.f("uq_teams_id_assignment_id")),
    )
    op.create_index(op.f("ix_teams_created_by"), "teams", ["created_by"], unique=False)
    op.create_table(
        "invitations",
        sa.Column("id", ID, nullable=False),
        sa.Column("kind", sa.Enum("course", "team", "staff", name="invitation_kind"), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("course_id", ID, nullable=True),
        sa.Column("team_id", ID, nullable=True),
        sa.Column("role", sa.Enum("student", "teacher", "admin", name="invitation_role"), nullable=False),
        sa.Column("invited_by", ID, nullable=False),
        sa.Column("token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "declined", "cancelled", "expired", name="invitation_status"),
            nullable=False,
        ),
        sa.Column("expires_at", TIMESTAMP, nullable=False),
        sa.Column("accepted_user_id", ID, nullable=True),
        sa.Column("responded_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"], ["users.id"], name=op.f("fk_invitations_accepted_user_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["course_id"], ["courses.id"], name=op.f("fk_invitations_course_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by"], ["users.id"], name=op.f("fk_invitations_invited_by"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_invitations_team_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitations")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invitations_token_hash")),
    )
    op.create_index(op.f("ix_invitations_accepted_user_id"), "invitations", ["accepted_user_id"], unique=False)
    op.create_index(op.f("ix_invitations_course_id"), "invitations", ["course_id"], unique=False)
    op.create_index("ix_invitations_email_status", "invitations", ["email", "status"], unique=False)
    op.create_index(op.f("ix_invitations_invited_by"), "invitations", ["invited_by"], unique=False)
    op.create_index("ix_invitations_team_id_status", "invitations", ["team_id", "status"], unique=False)
    op.create_table(
        "submissions",
        sa.Column("id", ID, nullable=False),
        sa.Column("team_id", ID, nullable=False),
        sa.Column("current_final_id", ID, nullable=True),
        sa.Column("closed_at", TIMESTAMP, nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], name=op.f("fk_submissions_team_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
        sa.UniqueConstraint("team_id", name=op.f("uq_submissions_team_id")),
    )
    op.create_index(op.f("ix_submissions_current_final_id"), "submissions", ["current_final_id"], unique=False)
    op.create_table(
        "team_members",
        sa.Column("assignment_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("team_id", ID, nullable=False),
        sa.Column("status", sa.Enum("active", "left", "removed", "former", name="team_member_status"), nullable=False),
        sa.Column("joined_at", TIMESTAMP, nullable=False),
        sa.Column("left_at", TIMESTAMP, nullable=True),
        sa.ForeignKeyConstraint(
            ["team_id", "assignment_id"],
            ["teams.id", "teams.assignment_id"],
            name=op.f("fk_team_members_team_id_assignment_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_team_members_user_id"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("assignment_id", "user_id", name=op.f("pk_team_members")),
    )
    op.create_index("ix_team_members_team_id_status", "team_members", ["team_id", "status"], unique=False)
    op.create_index(op.f("ix_team_members_user_id"), "team_members", ["user_id"], unique=False)
    op.create_table(
        "submission_versions",
        sa.Column("id", ID, nullable=False),
        sa.Column("submission_id", ID, nullable=False),
        sa.Column("number", SMALL_UINT, nullable=False),
        sa.Column("uploaded_by", ID, nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=36), nullable=False),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_id"],
            ["submissions.id"],
            name=op.f("fk_submission_versions_submission_id"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name=op.f("fk_submission_versions_uploaded_by"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission_versions")),
        sa.UniqueConstraint("submission_id", "number", name=op.f("uq_submission_versions_submission_id_number")),
        sa.UniqueConstraint(
            "uploaded_by", "idempotency_key", name=op.f("uq_submission_versions_uploaded_by_idempotency_key")
        ),
    )
    op.create_table(
        "final_submissions",
        sa.Column("id", ID, nullable=False),
        sa.Column("version_id", ID, nullable=False),
        sa.Column("submitted_by", ID, nullable=True),
        sa.Column("kind", sa.Enum("manual", "at_deadline", name="final_kind"), nullable=False),
        sa.Column("below_min_size", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.CHAR(length=36), nullable=True),
        sa.Column("submitted_at", TIMESTAMP, nullable=False),
        sa.Column("replaced_at", TIMESTAMP, nullable=True),
        sa.ForeignKeyConstraint(
            ["submitted_by"], ["users.id"], name=op.f("fk_final_submissions_submitted_by"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["submission_versions.id"],
            name=op.f("fk_final_submissions_version_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_final_submissions")),
        sa.UniqueConstraint(
            "submitted_by", "idempotency_key", name=op.f("uq_final_submissions_submitted_by_idempotency_key")
        ),
    )
    op.create_index(op.f("ix_final_submissions_version_id"), "final_submissions", ["version_id"], unique=False)
    op.create_table(
        "submission_files",
        sa.Column("id", ID, nullable=False),
        sa.Column("version_id", ID, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.CHAR(length=32), nullable=False),
        sa.Column(
            "mime_type", sa.Enum("application/pdf", "application/zip", name="submission_file_mime"), nullable=False
        ),
        sa.Column("size_bytes", UINT, nullable=False),
        sa.Column("sha256", sa.CHAR(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["version_id"], ["submission_versions.id"], name=op.f("fk_submission_files_version_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submission_files")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_submission_files_storage_key")),
    )
    op.create_index("ix_submission_files_version_id", "submission_files", ["version_id"], unique=False)
    op.create_table(
        "ai_feedback",
        sa.Column("id", ID, nullable=False),
        sa.Column("final_id", ID, nullable=False),
        sa.Column("file_id", ID, nullable=False),
        sa.Column("requested_by", ID, nullable=False),
        sa.Column("status", sa.Enum("queued", "running", "ready", "failed", name="ai_feedback_status"), nullable=False),
        sa.Column("model", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=20), nullable=False),
        sa.Column("cache_key", sa.CHAR(length=64), nullable=False),
        sa.Column("chars_read", UINT, nullable=True),
        sa.Column("chars_total", UINT, nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("created_at", TIMESTAMP, nullable=False),
        sa.Column("finished_at", TIMESTAMP, nullable=True),
        sa.ForeignKeyConstraint(
            ["file_id"], ["submission_files.id"], name=op.f("fk_ai_feedback_file_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["final_id"], ["final_submissions.id"], name=op.f("fk_ai_feedback_final_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_ai_feedback_requested_by"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_feedback")),
    )
    op.create_index("ix_ai_feedback_cache_key_status", "ai_feedback", ["cache_key", "status"], unique=False)
    op.create_index(op.f("ix_ai_feedback_file_id"), "ai_feedback", ["file_id"], unique=False)
    op.create_index("ix_ai_feedback_final_id_created_at", "ai_feedback", ["final_id", "created_at"], unique=False)
    op.create_index(op.f("ix_ai_feedback_requested_by"), "ai_feedback", ["requested_by"], unique=False)
    op.create_table(
        "reviews",
        sa.Column("id", ID, nullable=False),
        sa.Column("final_id", ID, nullable=False),
        sa.Column("reviewer_id", ID, nullable=False),
        sa.Column("overall_comment", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("draft", "released", name="review_status"), nullable=False),
        sa.Column("released_at", TIMESTAMP, nullable=True),
        sa.Column("updated_at", TIMESTAMP, nullable=False),
        sa.ForeignKeyConstraint(
            ["final_id"], ["final_submissions.id"], name=op.f("fk_reviews_final_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"], ["users.id"], name=op.f("fk_reviews_reviewer_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reviews")),
        sa.UniqueConstraint("final_id", name=op.f("uq_reviews_final_id")),
    )
    op.create_index(op.f("ix_reviews_reviewer_id"), "reviews", ["reviewer_id"], unique=False)
    op.create_table(
        "member_adjustments",
        sa.Column("review_id", ID, nullable=False),
        sa.Column("user_id", ID, nullable=False),
        sa.Column("percent", sa.Numeric(precision=4, scale=1), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("set_by", ID, nullable=False),
        sa.Column("set_at", TIMESTAMP, nullable=False),
        sa.CheckConstraint("percent BETWEEN -20 AND 10", name=op.f("ck_member_adjustments_percent_range")),
        sa.ForeignKeyConstraint(
            ["review_id"], ["reviews.id"], name=op.f("fk_member_adjustments_review_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["set_by"], ["users.id"], name=op.f("fk_member_adjustments_set_by"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_member_adjustments_user_id"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("review_id", "user_id", name=op.f("pk_member_adjustments")),
    )
    op.create_index(op.f("ix_member_adjustments_set_by"), "member_adjustments", ["set_by"], unique=False)
    op.create_index(op.f("ix_member_adjustments_user_id"), "member_adjustments", ["user_id"], unique=False)
    op.create_table(
        "review_scores",
        sa.Column("review_id", ID, nullable=False),
        sa.Column("criterion_id", ID, nullable=False),
        sa.Column("points", sa.Numeric(precision=5, scale=1), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["criterion_id"], ["rubric_criteria.id"], name=op.f("fk_review_scores_criterion_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["reviews.id"], name=op.f("fk_review_scores_review_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("review_id", "criterion_id", name=op.f("pk_review_scores")),
    )
    op.create_index(op.f("ix_review_scores_criterion_id"), "review_scores", ["criterion_id"], unique=False)

    # submissions and final_submissions point at each other, so this foreign key
    # can only be added once both tables exist.
    op.create_foreign_key(
        op.f("fk_submissions_current_final_id"),
        "submissions",
        "final_submissions",
        ["current_final_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Dropping a table also drops its indexes. The circular foreign key goes first.
    op.drop_constraint(op.f("fk_submissions_current_final_id"), "submissions", type_="foreignkey")
    op.drop_table("review_scores")
    op.drop_table("member_adjustments")
    op.drop_table("reviews")
    op.drop_table("ai_feedback")
    op.drop_table("submission_files")
    op.drop_table("final_submissions")
    op.drop_table("submission_versions")
    op.drop_table("team_members")
    op.drop_table("submissions")
    op.drop_table("invitations")
    op.drop_table("teams")
    op.drop_table("rubric_criteria")
    op.drop_table("resources")
    op.drop_table("notifications")
    op.drop_table("notification_rules")
    op.drop_table("enrollments")
    op.drop_table("email_tokens")
    op.drop_table("audit_log")
    op.drop_table("assignments")
    op.drop_table("user_emails")
    op.drop_table("sessions")
    op.drop_table("platform_settings")
    op.drop_table("oauth_identities")
    op.drop_table("notification_preferences")
    op.drop_table("email_outbox")
    op.drop_table("courses")
    op.drop_table("users")
    op.drop_table("login_attempts")
    op.drop_table("departments")
