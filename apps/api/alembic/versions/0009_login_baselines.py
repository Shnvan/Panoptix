"""Add login_baselines table for suspicious login detection.

Revision ID: 0009_login_baselines
Revises: 0008_alerts_email
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_login_baselines"
down_revision = "0008_alerts_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "login_baselines",
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("known_ips", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("known_countries", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("known_user_agents", JSONB, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("usual_hours_start", sa.Integer, nullable=False, server_default=sa.text("6")),
        sa.Column("usual_hours_end", sa.Integer, nullable=False, server_default=sa.text("23")),
        sa.Column("last_login_ip", sa.String(45)),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("last_login_country", sa.String(2)),
        sa.Column("login_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("login_baselines")
