"""create core tables

Revision ID: 0001_create_core_tables
Revises:
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_create_core_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


monitor_method = postgresql.ENUM("GET", "HEAD", name="monitor_method", create_type=False)
monitor_status = postgresql.ENUM("active", "paused", name="monitor_status", create_type=False)
job_status = postgresql.ENUM(
    "pending",
    "processing",
    "done",
    "failed",
    "dead",
    name="job_status",
    create_type=False,
)
alert_type = postgresql.ENUM("down", "recovery", name="alert_type", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    monitor_method.create(bind, checkfirst=True)
    monitor_status.create(bind, checkfirst=True)
    job_status.create(bind, checkfirst=True)
    alert_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "monitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("target_url", sa.String(length=2048), nullable=False),
        sa.Column("method", monitor_method, server_default="GET", nullable=False),
        sa.Column("check_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("consecutive_failure_threshold", sa.Integer(), server_default="2", nullable=False),
        sa.Column("status", monitor_status, server_default="active", nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monitors_user_id"), "monitors", ["user_id"], unique=False)

    op.create_table(
        "check_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", job_status, server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_check_jobs_monitor_id"), "check_jobs", ["monitor_id"], unique=False)
    op.create_index(op.f("ix_check_jobs_scheduled_at"), "check_jobs", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_check_jobs_status"), "check_jobs", ["status"], unique=False)

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_incidents_monitor_id"), "incidents", ["monitor_id"], unique=False)
    op.create_index(
        "uq_incidents_one_open_per_monitor",
        "incidents",
        ["monitor_id"],
        unique=True,
        postgresql_where=sa.text("resolved_at IS NULL"),
    )

    op.create_table(
        "alert_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", alert_type, nullable=False),
        sa.Column("status", job_status, server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("locked_by", sa.String(length=255), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_alert_jobs_incident_id"), "alert_jobs", ["incident_id"], unique=False)
    op.create_index(op.f("ix_alert_jobs_status"), "alert_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alert_jobs_status"), table_name="alert_jobs")
    op.drop_index(op.f("ix_alert_jobs_incident_id"), table_name="alert_jobs")
    op.drop_table("alert_jobs")

    op.drop_index("uq_incidents_one_open_per_monitor", table_name="incidents", postgresql_where=sa.text("resolved_at IS NULL"))
    op.drop_index(op.f("ix_incidents_monitor_id"), table_name="incidents")
    op.drop_table("incidents")

    op.drop_index(op.f("ix_check_jobs_status"), table_name="check_jobs")
    op.drop_index(op.f("ix_check_jobs_scheduled_at"), table_name="check_jobs")
    op.drop_index(op.f("ix_check_jobs_monitor_id"), table_name="check_jobs")
    op.drop_table("check_jobs")

    op.drop_index(op.f("ix_monitors_user_id"), table_name="monitors")
    op.drop_table("monitors")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    alert_type.drop(bind, checkfirst=True)
    job_status.drop(bind, checkfirst=True)
    monitor_status.drop(bind, checkfirst=True)
    monitor_method.drop(bind, checkfirst=True)
