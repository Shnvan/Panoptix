"""Add visitor access requests.

Revision ID: 0013_visitor_access_requests
Revises: 0012_gateway_discovery_runs
Create Date: 2026-06-01
"""

from __future__ import annotations

from alembic import op


revision = "0013_visitor_access_requests"
down_revision = "0012_gateway_discovery_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use PostgreSQL SQL directly so this migration can be retried after a
    # partial production attempt that already created the enum, table, or indexes.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE visitor_access_request_status AS ENUM (
                'pending', 'approved', 'rejected', 'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS visitor_access_requests (
            id                   UUID PRIMARY KEY,
            visitor_visit_id     UUID REFERENCES visitor_visits(id) ON DELETE SET NULL,
            applicant_name       VARCHAR(255) NOT NULL,
            email                VARCHAR(320) NOT NULL,
            organization         VARCHAR(255),
            reason               TEXT NOT NULL,
            requested_role       VARCHAR(64) NOT NULL,
            status               visitor_access_request_status NOT NULL DEFAULT 'pending',
            requester_ip         INET,
            requester_ua         VARCHAR(512),
            request_context      JSONB NOT NULL DEFAULT '{}',
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_at           TIMESTAMPTZ,
            decided_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
            decision_note        TEXT,
            github_invitation_id INTEGER,
            github_org           VARCHAR(255),
            github_invite_status VARCHAR(64)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_visitor_access_requests_status_created
        ON visitor_access_requests (status, created_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_visitor_access_requests_email_status
        ON visitor_access_requests (email, status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_visitor_access_requests_visitor_visit_id
        ON visitor_access_requests (visitor_visit_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_visitor_access_requests_visitor_visit_id")
    op.execute("DROP INDEX IF EXISTS ix_visitor_access_requests_email_status")
    op.execute("DROP INDEX IF EXISTS ix_visitor_access_requests_status_created")
    op.execute("DROP TABLE IF EXISTS visitor_access_requests")
    op.execute("DROP TYPE IF EXISTS visitor_access_request_status")
