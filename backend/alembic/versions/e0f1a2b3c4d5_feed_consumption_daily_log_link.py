"""Link feed_consumptions to factory_daily_logs for auto-derived rows.

Adds ``daily_log_id`` (nullable, CASCADE delete) and a unique constraint
``uq_feed_consumption_daily_log_id`` so that a daily log has at most one
derived ``feed_consumptions`` row. Legacy standalone rows keep
``daily_log_id = NULL`` (PostgreSQL allows duplicate NULLs under
UNIQUE), so nothing breaks.

Why: ``factory_daily_logs.feed_consumed_kg`` and ``feed_consumptions``
were independent inputs — users or cron could populate one without the
other, and monthly analytics double-counted. With this FK plus the
service-layer sync in ``FactoryDailyLogService`` we collapse the two
into a single source of truth: the daily log.

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e0f1a2b3c4d5"
down_revision = "d9e0f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feed_consumptions",
        sa.Column("daily_log_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_consumptions_daily_log_id",
        "feed_consumptions",
        "factory_daily_logs",
        ["daily_log_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_feed_consumptions_daily_log_id",
        "feed_consumptions",
        ["daily_log_id"],
    )
    op.create_unique_constraint(
        "uq_feed_consumption_daily_log_id",
        "feed_consumptions",
        ["daily_log_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_feed_consumption_daily_log_id",
        "feed_consumptions",
        type_="unique",
    )
    op.drop_index(
        "ix_feed_consumptions_daily_log_id",
        table_name="feed_consumptions",
    )
    op.drop_constraint(
        "fk_feed_consumptions_daily_log_id",
        "feed_consumptions",
        type_="foreignkey",
    )
    op.drop_column("feed_consumptions", "daily_log_id")
