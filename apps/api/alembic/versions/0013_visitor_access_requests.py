"""Add visitor access requests.

Revision ID: 0013_visitor_access_requests
Revises: 0012_gateway_discovery_runs
Create Date: 2026-06-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID


revision = "0013_visitor_access_requests"
down_revision = "0012_gateway_discovery_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = sa.Enum(
        "pending",
        "approved",
        "rejected",
        "cancelled",
        name="visitor_access_request_status",
    )
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "visitor_access_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "visitor_visit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("visitor_visits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("applicant_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("organization", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_role", sa.String(length=64), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default=sa.text("'pending'")),
        sa.Column("requester_ip", INET(), nullable=True),
        sa.Column("requester_ua", sa.String(length=512), nullable=True),
        sa.Column("request_context", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("github_invitation_id", sa.Integer(), nullable=True),
        sa.Column("github_org", sa.String(length=255), nullable=True),
        sa.Column("github_invite_status", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_visitor_access_requests_status_created",
        "visitor_access_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_visitor_access_requests_email_status",
        "visitor_access_requests",
        ["email", "status"],
    )
    op.create_index(
        "ix_visitor_access_requests_visitor_visit_id",
        "visitor_access_requests",
        ["visitor_visit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_visitor_access_requests_visitor_visit_id", table_name="visitor_access_requests")
    op.drop_index("ix_visitor_access_requests_email_status", table_name="visitor_access_requests")
    op.drop_index("ix_visitor_access_requests_status_created", table_name="visitor_access_requests")
    op.drop_table("visitor_access_requests")
    sa.Enum(name="visitor_access_request_status").drop(op.get_bind(), checkfirst=True)
