"""Add waste_kg and net_meat_kg to slaughter_processings

Operators asked for two additional weights at processing time:

* ``waste_kg`` — total offal/waste coming off the carcass (heads, feet,
  feathers, blood, discarded offal).
* ``net_meat_kg`` — total net/commercial meat output (the part that
  actually goes on sale as semi-products).

Both are nullable ``Numeric(16, 3)`` with a ``>= 0`` CHECK, matching
the existing per-sort weight columns.

Revision ID: c1b2c3d4e5f6
Revises: b9a0c1d2e3f4
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "c1b2c3d4e5f6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE slaughter_processings
        ADD COLUMN IF NOT EXISTS waste_kg numeric(16, 3)
        """
    )
    op.execute(
        """
        ALTER TABLE slaughter_processings
        ADD COLUMN IF NOT EXISTS net_meat_kg numeric(16, 3)
        """
    )
    op.execute(
        """
        ALTER TABLE slaughter_processings
        ADD CONSTRAINT ck_slaughter_processing_waste_kg_non_negative
        CHECK (waste_kg IS NULL OR waste_kg >= 0)
        """
    )
    op.execute(
        """
        ALTER TABLE slaughter_processings
        ADD CONSTRAINT ck_slaughter_processing_net_meat_kg_non_negative
        CHECK (net_meat_kg IS NULL OR net_meat_kg >= 0)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE slaughter_processings DROP CONSTRAINT IF EXISTS "
        "ck_slaughter_processing_waste_kg_non_negative"
    )
    op.execute(
        "ALTER TABLE slaughter_processings DROP CONSTRAINT IF EXISTS "
        "ck_slaughter_processing_net_meat_kg_non_negative"
    )
    op.execute("ALTER TABLE slaughter_processings DROP COLUMN IF EXISTS waste_kg")
    op.execute("ALTER TABLE slaughter_processings DROP COLUMN IF EXISTS net_meat_kg")
