"""Link medicine_consumptions to factory_flocks.

Adds ``factory_flock_id`` (nullable, SET NULL) so ветеринарные назначения
конкретного стада остаются прослеживаемыми. Без этой связки нельзя
построить per-flock medicine cost или mortality-vs-treatment отчёты.

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "medicine_consumptions",
        sa.Column("factory_flock_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_medicine_consumptions_factory_flock_id",
        "medicine_consumptions",
        "factory_flocks",
        ["factory_flock_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_medicine_consumptions_factory_flock_id",
        "medicine_consumptions",
        ["factory_flock_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_medicine_consumptions_factory_flock_id",
        table_name="medicine_consumptions",
    )
    op.drop_constraint(
        "fk_medicine_consumptions_factory_flock_id",
        "medicine_consumptions",
        type_="foreignkey",
    )
    op.drop_column("medicine_consumptions", "factory_flock_id")
