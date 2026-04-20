"""Link feed_consumptions to feed_production_batches.

Adds ``production_batch_id`` (nullable, SET NULL). Без этой связи нельзя
привязать фактическое потребление корма к конкретной произведённой
партии — блокирует FEFO/FIFO-учёт, отзыв по партии и point-in-time
себестоимость корма.

Nullable потому, что исторические feed_consumptions и строки из
``factory_daily_logs.feed_consumed_kg`` (ещё не мигрированы по L7)
не знают конкретную партию.

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feed_consumptions",
        sa.Column("production_batch_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_consumptions_production_batch_id",
        "feed_consumptions",
        "feed_production_batches",
        ["production_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_consumptions_production_batch_id",
        "feed_consumptions",
        ["production_batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feed_consumptions_production_batch_id",
        table_name="feed_consumptions",
    )
    op.drop_constraint(
        "fk_feed_consumptions_production_batch_id",
        "feed_consumptions",
        type_="foreignkey",
    )
    op.drop_column("feed_consumptions", "production_batch_id")
