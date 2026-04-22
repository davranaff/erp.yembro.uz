"""Strip source/counterparty fields the operator no longer fills in

The operator-facing forms for factory, slaughter, medicine and feed
stopped asking for upstream/downstream counterparties and some paper-
trail fields. The DB keeps pace: FKs and text columns that nobody
populates anymore are dropped instead of lingering as always-null
noise.

Dropped columns:

* ``factory_flocks.source_client_id`` — the parent flock is no longer
  tied to a supplier client.
* ``factory_shipments.destination_department_id`` — the receiver-department
  field is gone from the form.
* ``slaughter_arrivals.source_type`` / ``factory_shipment_id`` /
  ``supplier_client_id`` / ``arrival_invoice_no`` — slaughter arrivals
  no longer split on factory-vs-external, no longer link to the shipping
  side, and the receipt invoice column is gone.
* ``medicine_arrivals.supplier_client_id`` — plus the supplier-based
  uniqueness constraint.
* ``medicine_batches.supplier_client_id`` — same reasoning.
* ``feed_arrivals.supplier_client_id`` / ``invoice_no`` — plus the
  composite uniqueness.
* ``feed_raw_arrivals.supplier_client_id`` / ``invoice_no`` /
  ``lot_no`` — plus the composite uniqueness.
* ``feed_product_shipments.destination_department_id`` — receiver-department
  column dropped from the form.

Downgrade is a no-op.

Revision ID: b9a0c1d2e3f4
Revises: a8f9b0c1d2e3
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "b9a0c1d2e3f4"
down_revision = "a8f9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------- slaughter_arrivals: drop CHECK constraints first -------
    op.execute(
        "ALTER TABLE slaughter_arrivals "
        "DROP CONSTRAINT IF EXISTS ck_slaughter_arrival_source_exactly_one"
    )
    op.execute(
        "ALTER TABLE slaughter_arrivals "
        "DROP CONSTRAINT IF EXISTS ck_slaughter_arrival_source_type"
    )

    # ------- uniqueness constraints referencing soon-to-drop columns -------
    op.execute(
        "ALTER TABLE medicine_arrivals DROP CONSTRAINT IF EXISTS uq_medicine_arrival_invoice"
    )
    op.execute(
        "ALTER TABLE feed_arrivals DROP CONSTRAINT IF EXISTS uq_feed_arrival_invoice"
    )
    op.execute(
        "ALTER TABLE feed_raw_arrivals DROP CONSTRAINT IF EXISTS uq_feed_raw_arrival_invoice"
    )

    # ------- column drops -------
    op.execute("ALTER TABLE factory_flocks DROP COLUMN IF EXISTS source_client_id")
    op.execute(
        "ALTER TABLE factory_shipments DROP COLUMN IF EXISTS destination_department_id"
    )

    op.execute("ALTER TABLE slaughter_arrivals DROP COLUMN IF EXISTS factory_shipment_id")
    op.execute("ALTER TABLE slaughter_arrivals DROP COLUMN IF EXISTS supplier_client_id")
    op.execute("ALTER TABLE slaughter_arrivals DROP COLUMN IF EXISTS arrival_invoice_no")
    op.execute("ALTER TABLE slaughter_arrivals DROP COLUMN IF EXISTS source_type")

    op.execute("ALTER TABLE medicine_arrivals DROP COLUMN IF EXISTS supplier_client_id")
    op.execute("ALTER TABLE medicine_batches DROP COLUMN IF EXISTS supplier_client_id")

    op.execute("ALTER TABLE feed_arrivals DROP COLUMN IF EXISTS supplier_client_id")
    op.execute("ALTER TABLE feed_arrivals DROP COLUMN IF EXISTS invoice_no")

    op.execute("ALTER TABLE feed_raw_arrivals DROP COLUMN IF EXISTS supplier_client_id")
    op.execute("ALTER TABLE feed_raw_arrivals DROP COLUMN IF EXISTS invoice_no")
    op.execute("ALTER TABLE feed_raw_arrivals DROP COLUMN IF EXISTS lot_no")

    op.execute(
        "ALTER TABLE feed_product_shipments DROP COLUMN IF EXISTS destination_department_id"
    )


def downgrade() -> None:
    # Intentionally a no-op — the forms no longer know how to collect
    # this data. Restore from a pre-drop backup if needed.
    pass
