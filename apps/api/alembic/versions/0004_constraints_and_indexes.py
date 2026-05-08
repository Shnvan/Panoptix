"""Add schema guardrails and performance indexes (core MVP).

Revision ID: 0004_constraints_and_indexes
Revises: 0003_roles_and_grants
Create Date: 2026-05-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0004_constraints_and_indexes"
down_revision = "0003_roles_and_grants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Performance indexes for common access patterns.
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_user_active",
        "sessions",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_index("ix_cameras_site_id", "cameras", ["site_id"])
    op.create_index("ix_cameras_gateway_id", "cameras", ["gateway_id"])
    op.create_index("ix_edge_gateways_status", "edge_gateways", ["status"])
    op.create_index("ix_edge_gateways_last_seen_at", "edge_gateways", ["last_seen_at"])

    # Schema guardrails for token grants.
    op.create_check_constraint(
        "ck_stream_grants_kind_fields",
        "stream_grants",
        """
        (
          (kind = 'viewer_subscribe' AND user_id IS NOT NULL AND session_id IS NOT NULL AND gateway_id IS NULL)
          OR
          (kind = 'gateway_publish' AND gateway_id IS NOT NULL AND user_id IS NULL AND session_id IS NULL)
        )
        """,
    )


def downgrade() -> None:
    op.drop_constraint("ck_stream_grants_kind_fields", "stream_grants", type_="check")

    op.drop_index("ix_edge_gateways_last_seen_at", table_name="edge_gateways")
    op.drop_index("ix_edge_gateways_status", table_name="edge_gateways")
    op.drop_index("ix_cameras_gateway_id", table_name="cameras")
    op.drop_index("ix_cameras_site_id", table_name="cameras")
    op.drop_index("ix_sessions_user_active", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
