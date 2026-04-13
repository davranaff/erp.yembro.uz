"""add department icon

Revision ID: e7f8c2a41b55
Revises: d4b7a1f03e22
Create Date: 2026-03-19 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e7f8c2a41b55"
down_revision = "d4b7a1f03e22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("icon", sa.String(length=48), nullable=True))


def downgrade() -> None:
    op.drop_column("departments", "icon")
