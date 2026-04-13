"""add part_name to slaughter semi products

Revision ID: d4b7a1f03e22
Revises: c91c0f4bdb2a
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d4b7a1f03e22"
down_revision = "c91c0f4bdb2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("slaughter_semi_products", sa.Column("part_name", sa.String(length=120), nullable=True))
    op.create_index(
        op.f("ix_slaughter_semi_products_part_name"),
        "slaughter_semi_products",
        ["part_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_slaughter_semi_products_part_name"), table_name="slaughter_semi_products")
    op.drop_column("slaughter_semi_products", "part_name")
