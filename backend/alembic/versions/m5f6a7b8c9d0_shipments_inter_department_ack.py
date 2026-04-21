"""shipments: inter-department transfer fields (destination + acknowledgment)

Adds destination_department_id, acknowledged_at/by, received_quantity,
status ('sent'|'received'|'discrepancy') to 5 shipment tables.

Existing rows → status='received', acknowledged_at = shipped_on + 1 day,
received_quantity mirrors the original shipped quantity.

Revision ID: m5f6a7b8c9d0
Revises: k4e5f6a7b8c9
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "m5f6a7b8c9d0"
down_revision = "k4e5f6a7b8c9"
branch_labels = None
depends_on = None


# (table, original_quantity_column) — used to seed received_quantity for existing rows
TABLES: tuple[tuple[str, str], ...] = (
    ("egg_shipments", "eggs_count"),
    ("chick_shipments", "chicks_count"),
    ("factory_shipments", "birds_count"),
    ("feed_product_shipments", "quantity"),
    ("slaughter_semi_product_shipments", "quantity"),
)

STATUS_VALUES = ("sent", "received", "discrepancy")


def upgrade() -> None:
    bind = op.get_bind()

    for table, qty_col in TABLES:
        op.add_column(
            table,
            sa.Column("destination_department_id", sa.UUID(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("acknowledged_by", sa.UUID(), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("received_quantity", sa.Numeric(16, 3), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("status", sa.String(20), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table}_destination_department_id",
            table,
            "departments",
            ["destination_department_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_foreign_key(
            f"fk_{table}_acknowledged_by",
            table,
            "employees",
            ["acknowledged_by"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{table}_destination_department_id",
            table,
            ["destination_department_id"],
        )
        op.create_index(
            f"ix_{table}_status",
            table,
            ["status"],
        )

        # Backfill existing rows as historically received
        bind.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET status = 'received',
                    received_quantity = {qty_col},
                    acknowledged_at = (shipped_on::timestamptz + INTERVAL '1 day')
                WHERE status IS NULL
                """
            )
        )

        op.alter_column(
            table,
            "status",
            nullable=False,
            server_default="sent",
        )
        op.create_check_constraint(
            f"ck_{table}_status",
            table,
            f"status IN {STATUS_VALUES}",
        )


def downgrade() -> None:
    for table, _ in TABLES:
        op.drop_constraint(f"ck_{table}_status", table, type_="check")
        op.drop_index(f"ix_{table}_status", table_name=table)
        op.drop_index(f"ix_{table}_destination_department_id", table_name=table)
        op.drop_constraint(f"fk_{table}_acknowledged_by", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_destination_department_id", table, type_="foreignkey")
        op.drop_column(table, "status")
        op.drop_column(table, "received_quantity")
        op.drop_column(table, "acknowledged_by")
        op.drop_column(table, "acknowledged_at")
        op.drop_column(table, "destination_department_id")
