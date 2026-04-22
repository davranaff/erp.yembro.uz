"""Drop destination_department_id from slaughter_semi_product_shipments

Operators stopped recording a destination department on semi-product
shipments — the receiving side is always an external client now. Drop
the column along with its index/FK.

Revision ID: e4f5a6b7c8d9
Revises: c1b2c3d4e5f6
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "e4f5a6b7c8d9"
down_revision = "c1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE slaughter_semi_product_shipments "
        "DROP COLUMN IF EXISTS destination_department_id"
    )


def downgrade() -> None:
    pass
