"""Link factory_flocks to their source chick_arrivals.

Revision ID: f5a6b7c8d9e0
Revises: e3f4a5b6c7d8
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f5a6b7c8d9e0"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "factory_flocks",
        sa.Column("chick_arrival_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_factory_flocks_chick_arrival_id",
        "factory_flocks",
        "chick_arrivals",
        ["chick_arrival_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_factory_flocks_chick_arrival_id",
        "factory_flocks",
        ["chick_arrival_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_factory_flocks_chick_arrival_id", table_name="factory_flocks")
    op.drop_constraint(
        "fk_factory_flocks_chick_arrival_id",
        "factory_flocks",
        type_="foreignkey",
    )
    op.drop_column("factory_flocks", "chick_arrival_id")
