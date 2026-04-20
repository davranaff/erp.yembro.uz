"""Rewrite feed_product stock_movements to key by production_batch_id.

Historically the item_key was ``feed_product:<feed_type_id>`` which aggregated
batches together and made FIFO/FEFO and recall tracing impossible. For stock
rows that unambiguously originate from a single batch we rewrite to
``feed_product:<production_batch_id>``:

* ``feed_production_batches`` — reference_id IS the batch id.
* ``feed_product_shipments`` — join to the shipment and use its
  production_batch_id, when present.

Rows that cannot be attributed to a batch (legacy shipments without a batch
link, ``factory_daily_logs`` feed consumption) are intentionally left with the
feed-type key; fixing those requires schema additions handled elsewhere.

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a6b7c8d9e0f1"
down_revision = "f5a6b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET item_key = 'feed_product:' || sm.reference_id::text
            WHERE sm.reference_table = 'feed_production_batches'
              AND sm.item_type = 'feed'
              AND sm.item_key LIKE 'feed_product:%'
              AND sm.item_key <> 'feed_product:' || sm.reference_id::text
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET item_key = 'feed_product:' || fps.production_batch_id::text
            FROM feed_product_shipments AS fps
            WHERE sm.reference_id = fps.id
              AND sm.reference_table = 'feed_product_shipments'
              AND sm.item_type = 'feed'
              AND sm.item_key LIKE 'feed_product:%'
              AND fps.production_batch_id IS NOT NULL
              AND sm.item_key <> 'feed_product:' || fps.production_batch_id::text
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET item_key = 'feed_product:' || ff.feed_type_id::text
            FROM feed_production_batches AS pb
            JOIN feed_formulas AS ff ON ff.id = pb.formula_id
            WHERE sm.reference_id = pb.id
              AND sm.reference_table = 'feed_production_batches'
              AND sm.item_type = 'feed'
              AND sm.item_key LIKE 'feed_product:%'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET item_key = 'feed_product:' || fps.feed_type_id::text
            FROM feed_product_shipments AS fps
            WHERE sm.reference_id = fps.id
              AND sm.reference_table = 'feed_product_shipments'
              AND sm.item_type = 'feed'
              AND sm.item_key LIKE 'feed_product:%'
            """
        )
    )
