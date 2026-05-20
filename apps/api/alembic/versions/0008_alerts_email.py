"""Add alert records and email notification attempts.

Revision ID: 0008_alerts_email
Revises: 0007_gateway_command_tables
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0008_alerts_email"
down_revision = "0007_gateway_command_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    alert_severity = postgresql.ENUM(
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        name="alert_severity",
        create_type=False,
    )
    alert_status = postgresql.ENUM(
        "open",
        "acknowledged",
        "resolved",
        name="alert_status",
        create_type=False,
    )
    alert_category = postgresql.ENUM(
        "security",
        "operations",
        "compliance",
        "availability",
        name="alert_category",
        create_type=False,
    )
    alert_notification_status = postgresql.ENUM(
        "pending",
        "sent",
        "failed",
        name="alert_notification_status",
        create_type=False,
    )
    actor_type = postgresql.ENUM(name="actor_type", create_type=False)

    bind = op.get_bind()
    for enum_t in (alert_severity, alert_status, alert_category, alert_notification_status):
        enum_t.create(bind, checkfirst=True)

    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("category", alert_category, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", alert_status, nullable=False, server_default=sa.text("'open'")),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_event_id", sa.BigInteger()),
        sa.Column("resource", sa.String(length=256)),
        sa.Column("actor_type", actor_type),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True)),
        sa.Column("metadata_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column(
            "acknowledged_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "resolved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint("source", "source_event_id", name="uq_alerts_source_event"),
    )
    op.create_index("ix_alerts_status_created_at", "alerts", ["status", "created_at"])
    op.create_index("ix_alerts_severity_created_at", "alerts", ["severity", "created_at"])

    op.create_table(
        "alert_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alerts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.String(length=32), nullable=False, server_default=sa.text("'email'")),
        sa.Column("recipient", sa.String(length=320), nullable=False),
        sa.Column(
            "status",
            alert_notification_status,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(length=256)),
    )
    op.create_index("ix_alert_notifications_alert_id", "alert_notifications", ["alert_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_notifications_alert_id", table_name="alert_notifications")
    op.drop_table("alert_notifications")

    op.drop_index("ix_alerts_severity_created_at", table_name="alerts")
    op.drop_index("ix_alerts_status_created_at", table_name="alerts")
    op.drop_table("alerts")

    bind = op.get_bind()
    for enum_name in (
        "alert_notification_status",
        "alert_category",
        "alert_status",
        "alert_severity",
    ):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
