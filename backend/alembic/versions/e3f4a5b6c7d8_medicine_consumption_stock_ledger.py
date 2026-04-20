"""Backfill stock_movements for medicine_consumptions and sync remaining_quantity.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO stock_movements (
                id,
                organization_id,
                department_id,
                warehouse_id,
                item_type,
                item_key,
                movement_kind,
                quantity,
                unit,
                occurred_on,
                reference_table,
                reference_id,
                note,
                created_at,
                updated_at
            )
            SELECT
                gen_random_uuid() AS id,
                mc.organization_id,
                mc.department_id,
                mb.warehouse_id,
                'medicine' AS item_type,
                'medicine_batch:' || mc.batch_id::text AS item_key,
                'outgoing' AS movement_kind,
                mc.quantity,
                COALESCE(mc.unit, mb.unit, 'pcs') AS unit,
                mc.consumed_on AS occurred_on,
                'medicine_consumptions' AS reference_table,
                mc.id AS reference_id,
                mc.purpose AS note,
                NOW() AS created_at,
                NOW() AS updated_at
            FROM medicine_consumptions AS mc
            JOIN medicine_batches AS mb ON mb.id = mc.batch_id
            WHERE mb.warehouse_id IS NOT NULL
              AND mc.quantity > 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM stock_movements AS sm
                  WHERE sm.reference_table = 'medicine_consumptions'
                    AND sm.reference_id = mc.id
                    AND sm.movement_kind = 'outgoing'
                    AND sm.item_type = 'medicine'
                    AND sm.item_key = 'medicine_batch:' || mc.batch_id::text
              )
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE medicine_batches AS mb
            SET remaining_quantity = GREATEST(
                mb.received_quantity - COALESCE(
                    (
                        SELECT SUM(quantity)
                        FROM medicine_consumptions
                        WHERE batch_id = mb.id
                    ),
                    0
                ),
                0
            )
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM stock_movements
            WHERE reference_table = 'medicine_consumptions'
            """
        )
    )

    bind.execute(
        sa.text(
            """
            UPDATE medicine_batches
            SET remaining_quantity = received_quantity
            """
        )
    )
