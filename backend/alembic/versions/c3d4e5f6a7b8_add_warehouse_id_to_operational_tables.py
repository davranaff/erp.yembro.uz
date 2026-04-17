"""add warehouse_id to operational tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-17 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

TABLES = [
    "medicine_batches",
    "feed_production_batches",
    "feed_product_shipments",
    "slaughter_semi_products",
    "slaughter_semi_product_shipments",
    "incubation_runs",
    "incubation_batches",
    "chick_shipments",
    "egg_production",
    "egg_shipments",
]


def upgrade() -> None:
    for table_name in TABLES:
        op.add_column(
            table_name,
            sa.Column("warehouse_id", sa.UUID(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table_name}_warehouse_id",
            table_name,
            "warehouses",
            ["warehouse_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            op.f(f"ix_{table_name}_warehouse_id"),
            table_name,
            ["warehouse_id"],
            unique=False,
        )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_index(op.f(f"ix_{table_name}_warehouse_id"), table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_warehouse_id", table_name, type_="foreignkey")
        op.drop_column(table_name, "warehouse_id")
