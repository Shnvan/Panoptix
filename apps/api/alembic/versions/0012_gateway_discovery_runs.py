"""Add gateway discovery run snapshots.

Revision ID: 0012_gateway_discovery_runs
Revises: 0011_visitor_expanded_signals
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0012_gateway_discovery_runs"
down_revision = "0011_visitor_expanded_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gateway_discovery_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "gateway_id",
            UUID(as_uuid=True),
            sa.ForeignKey("edge_gateways.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("approved_ranges", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("ports", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("scanned_host_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("findings", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("agent_version", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_gateway_discovery_runs_gateway_started",
        "gateway_discovery_runs",
        ["gateway_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gateway_discovery_runs_gateway_started", table_name="gateway_discovery_runs")
    op.drop_table("gateway_discovery_runs")
