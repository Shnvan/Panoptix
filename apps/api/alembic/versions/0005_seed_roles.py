"""Seed admin and viewer roles.

Revision ID: 0005_seed_roles
Revises: 0004_constraints_and_indexes
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_seed_roles"
down_revision = "0004_constraints_and_indexes"
branch_labels = None
depends_on = None

roles_table = sa.table("roles", sa.column("id", sa.Integer), sa.column("name", sa.String))


def upgrade() -> None:
    op.bulk_insert(roles_table, [{"id": 1, "name": "admin"}, {"id": 2, "name": "viewer"}])


def downgrade() -> None:
    op.execute("DELETE FROM roles WHERE name IN ('admin', 'viewer')")
