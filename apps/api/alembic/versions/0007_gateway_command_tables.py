"""Add gateway command queue and camera publish state tables.

Revision ID: 0007_gateway_command_tables
Revises: 0006_audit_log_metadata
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0007_gateway_command_tables"
down_revision = "0006_audit_log_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    command_status = postgresql.ENUM(
        "pending",
        "accepted",
        "rejected",
        "expired",
        "cancelled",
        name="command_status",
        create_type=False,
    )
    camera_publish_status = postgresql.ENUM(
        "idle",
        "starting",
        "publishing",
        "stop_pending",
        name="camera_publish_status",
        create_type=False,
    )

    bind = op.get_bind()
    for enum_t in (command_status, camera_publish_status):
        enum_t.create(bind, checkfirst=True)

    op.create_table(
        "gateway_command_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "gateway_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("edge_gateways.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", command_status, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acked_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(length=512)),
    )
    op.create_index(
        "ix_gateway_command_queue_gateway_status",
        "gateway_command_queue",
        ["gateway_id", "status"],
    )

    op.create_table(
        "camera_publish_states",
        sa.Column(
            "camera_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cameras.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("gateway_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("edge_gateways.id")),
        sa.Column("room", sa.String(length=64), nullable=False),
        sa.Column("status", camera_publish_status, nullable=False, server_default=sa.text("'idle'")),
        sa.Column("last_viewer_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("stop_requested_at", sa.DateTime(timezone=True)),
        sa.Column("stop_due_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_camera_publish_states_status_due",
        "camera_publish_states",
        ["status", "stop_due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_camera_publish_states_status_due", table_name="camera_publish_states")
    op.drop_table("camera_publish_states")

    op.drop_index("ix_gateway_command_queue_gateway_status", table_name="gateway_command_queue")
    op.drop_table("gateway_command_queue")

    bind = op.get_bind()
    for enum_name in ("camera_publish_status", "command_status"):
        postgresql.ENUM(name=enum_name).drop(bind, checkfirst=True)
