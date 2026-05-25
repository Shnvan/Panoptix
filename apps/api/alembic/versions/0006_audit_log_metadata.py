"""Add severity, outcome, category, session_id columns to audit_log.

Revision ID: 0006_audit_log_metadata
Revises: 0005_seed_roles
Create Date: 2026-05-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0006_audit_log_metadata"
down_revision = "0005_seed_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    event_severity = postgresql.ENUM(
        "informational", "low", "medium", "high", "critical",
        name="event_severity",
        create_type=False,
    )
    event_outcome = postgresql.ENUM(
        "success", "failure", "denied", "error",
        name="event_outcome",
        create_type=False,
    )
    event_category = postgresql.ENUM(
        "authentication", "authorization", "data_access", "admin", "system", "compliance",
        name="event_category",
        create_type=False,
    )

    bind = op.get_bind()
    for enum_t in (event_severity, event_outcome, event_category):
        enum_t.create(bind, checkfirst=True)

    op.add_column("audit_log", sa.Column("event_severity", event_severity))
    op.add_column("audit_log", sa.Column("event_outcome", event_outcome))
    op.add_column("audit_log", sa.Column("event_category", event_category))
    op.add_column("audit_log", sa.Column("session_id", postgresql.UUID(as_uuid=True)))

    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_category_severity", "audit_log", ["event_category", "event_severity"])
    op.create_index("ix_audit_log_session_id", "audit_log", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_session_id", table_name="audit_log")
    op.drop_index("ix_audit_log_category_severity", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")

    op.drop_column("audit_log", "session_id")
    op.drop_column("audit_log", "event_category")
    op.drop_column("audit_log", "event_outcome")
    op.drop_column("audit_log", "event_severity")

    bind = op.get_bind()
    for enum_name in ("event_category", "event_outcome", "event_severity"):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
