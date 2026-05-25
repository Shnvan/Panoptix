"""Add expanded visitor entry context.

Revision ID: 0011_visitor_expanded_signals
Revises: 0010_visitor_visits
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011_visitor_expanded_signals"
down_revision = "0010_visitor_visits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column_name in (
        "browser_context",
        "network_context",
        "webrtc_context",
        "timing_context",
        "server_context",
    ):
        op.add_column(
            "visitor_visits",
            sa.Column(column_name, JSONB, nullable=False, server_default=sa.text("'{}'")),
        )


def downgrade() -> None:
    for column_name in (
        "server_context",
        "timing_context",
        "webrtc_context",
        "network_context",
        "browser_context",
    ):
        op.drop_column("visitor_visits", column_name)
