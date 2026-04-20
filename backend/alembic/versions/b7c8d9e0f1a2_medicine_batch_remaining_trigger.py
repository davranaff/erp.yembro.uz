"""Make medicine_batches.remaining_quantity a ledger-derived column via DB trigger.

Before this change, ``remaining_quantity`` was a denormalized field updated
from two independent code paths (MedicineBatchService edits and
MedicineConsumptionService._recompute_batch_remaining). Either path could be
skipped by direct SQL writes, letting ``remaining_quantity`` and
``stock_movements`` drift apart.

This migration installs a pair of Postgres helpers that keep the field in
lock-step with ``medicine_consumptions``:

* ``fn_medicine_batch_recompute_remaining(batch_id)`` — recomputes
  ``remaining_quantity = max(received_quantity - SUM(consumptions.quantity), 0)``
  for a single batch.
* ``trg_medicine_consumption_recompute_remaining`` — fires AFTER
  INSERT/UPDATE/DELETE on ``medicine_consumptions`` and invokes the helper for
  the affected batch(es).

A one-time recompute at the end normalizes historical rows.

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-04-19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b7c8d9e0f1a2"
down_revision = "a6b7c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_medicine_batch_recompute_remaining(p_batch_id UUID)
        RETURNS VOID AS $$
        BEGIN
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
            WHERE mb.id = p_batch_id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_medicine_consumption_after_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                PERFORM fn_medicine_batch_recompute_remaining(OLD.batch_id);
                RETURN OLD;
            ELSIF TG_OP = 'UPDATE' THEN
                IF OLD.batch_id IS DISTINCT FROM NEW.batch_id THEN
                    PERFORM fn_medicine_batch_recompute_remaining(OLD.batch_id);
                END IF;
                PERFORM fn_medicine_batch_recompute_remaining(NEW.batch_id);
                RETURN NEW;
            ELSE
                PERFORM fn_medicine_batch_recompute_remaining(NEW.batch_id);
                RETURN NEW;
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_medicine_consumption_recompute_remaining
        ON medicine_consumptions
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_medicine_consumption_recompute_remaining
        AFTER INSERT OR UPDATE OR DELETE ON medicine_consumptions
        FOR EACH ROW
        EXECUTE FUNCTION fn_medicine_consumption_after_change()
        """
    )

    op.execute(
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


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_medicine_consumption_recompute_remaining "
        "ON medicine_consumptions"
    )
    op.execute("DROP FUNCTION IF EXISTS fn_medicine_consumption_after_change()")
    op.execute("DROP FUNCTION IF EXISTS fn_medicine_batch_recompute_remaining(UUID)")
