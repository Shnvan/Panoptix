"""Rename cameras.name to cameras.display_name (API contract alignment).

Revision ID: 0002_camera_display_name
Revises: 0001_initial_schema
Create Date: 2026-05-08
"""

from __future__ import annotations

from alembic import op


revision = "0002_camera_display_name"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("cameras", "name", new_column_name="display_name")


def downgrade() -> None:
    op.alter_column("cameras", "display_name", new_column_name="name")

