"""Add public visitor collector visits.

Revision ID: 0010_visitor_visits
Revises: 0009_login_baselines
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, JSONB

revision = "0010_visitor_visits"
down_revision = "0009_login_baselines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visitor_visits",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("page_path", sa.String(512), nullable=False),
        sa.Column("notice_version", sa.String(64), nullable=False),
        sa.Column("ip", INET),
        sa.Column("ua", sa.String(512)),
        sa.Column("screen_width", sa.Integer),
        sa.Column("screen_height", sa.Integer),
        sa.Column("browser_timezone", sa.String(128)),
        sa.Column("browser_language", sa.String(64)),
        sa.Column("ip_enrichment_status", sa.String(32), nullable=False),
        sa.Column("ip_enrichment_provider", sa.String(64)),
        sa.Column("ip_enrichment", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("session_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="SET NULL"), unique=True),
        sa.Column("logged_in_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_visitor_visits_collected_at", "visitor_visits", ["collected_at"])
    op.create_index("ix_visitor_visits_user_id", "visitor_visits", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_visitor_visits_user_id", table_name="visitor_visits")
    op.drop_index("ix_visitor_visits_collected_at", table_name="visitor_visits")
    op.drop_table("visitor_visits")
