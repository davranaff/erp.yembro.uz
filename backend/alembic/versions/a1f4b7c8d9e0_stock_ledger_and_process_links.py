"""stock ledger and process links

Revision ID: a1f4b7c8d9e0
Revises: 9d1e2f3a4b5c
Create Date: 2026-03-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a1f4b7c8d9e0"
down_revision = "9d1e2f3a4b5c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("incubation_batches", sa.Column("production_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_incubation_batches_production_id"), "incubation_batches", ["production_id"], unique=False)
    op.create_foreign_key(
        "fk_incubation_batches_production_id",
        "incubation_batches",
        "egg_production",
        ["production_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("chick_arrivals", sa.Column("run_id", sa.UUID(), nullable=True))
    op.add_column("chick_arrivals", sa.Column("chick_shipment_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_chick_arrivals_run_id"), "chick_arrivals", ["run_id"], unique=False)
    op.create_index(op.f("ix_chick_arrivals_chick_shipment_id"), "chick_arrivals", ["chick_shipment_id"], unique=False)
    op.create_foreign_key(
        "fk_chick_arrivals_run_id",
        "chick_arrivals",
        "incubation_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_chick_arrivals_chick_shipment_id",
        "chick_arrivals",
        "chick_shipments",
        ["chick_shipment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("slaughter_arrivals", sa.Column("chick_arrival_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_slaughter_arrivals_chick_arrival_id"), "slaughter_arrivals", ["chick_arrival_id"], unique=False)
    op.create_foreign_key(
        "fk_slaughter_arrivals_chick_arrival_id",
        "slaughter_arrivals",
        "chick_arrivals",
        ["chick_arrival_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "stock_movements",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("counterparty_department_id", sa.UUID(), nullable=True),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("movement_kind", sa.String(length=30), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="pcs", nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reference_table", sa.String(length=64), nullable=False),
        sa.Column("reference_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_movement_quantity_positive"),
        sa.CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'medicine', 'semi_product')",
            name="ck_stock_movement_item_type_allowed",
        ),
        sa.CheckConstraint(
            "movement_kind IN ('incoming', 'outgoing', 'transfer_in', 'transfer_out', 'adjustment_in', 'adjustment_out')",
            name="ck_stock_movement_kind_allowed",
        ),
        sa.ForeignKeyConstraint(["counterparty_department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_table",
            "reference_id",
            "movement_kind",
            "department_id",
            "item_type",
            "item_key",
            name="uq_stock_movement_reference_kind_scope",
        ),
    )
    op.create_index(op.f("ix_stock_movements_organization_id"), "stock_movements", ["organization_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_department_id"), "stock_movements", ["department_id"], unique=False)
    op.create_index(
        op.f("ix_stock_movements_counterparty_department_id"),
        "stock_movements",
        ["counterparty_department_id"],
        unique=False,
    )
    op.create_index(op.f("ix_stock_movements_item_type"), "stock_movements", ["item_type"], unique=False)
    op.create_index(op.f("ix_stock_movements_item_key"), "stock_movements", ["item_key"], unique=False)
    op.create_index(op.f("ix_stock_movements_movement_kind"), "stock_movements", ["movement_kind"], unique=False)
    op.create_index(op.f("ix_stock_movements_occurred_on"), "stock_movements", ["occurred_on"], unique=False)
    op.create_index(op.f("ix_stock_movements_reference_table"), "stock_movements", ["reference_table"], unique=False)
    op.create_index(op.f("ix_stock_movements_reference_id"), "stock_movements", ["reference_id"], unique=False)
    op.create_index(op.f("ix_stock_movements_id"), "stock_movements", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_movements_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_reference_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_reference_table"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_occurred_on"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_movement_kind"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_item_key"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_item_type"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_counterparty_department_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_department_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_organization_id"), table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_constraint("fk_slaughter_arrivals_chick_arrival_id", "slaughter_arrivals", type_="foreignkey")
    op.drop_index(op.f("ix_slaughter_arrivals_chick_arrival_id"), table_name="slaughter_arrivals")
    op.drop_column("slaughter_arrivals", "chick_arrival_id")

    op.drop_constraint("fk_chick_arrivals_chick_shipment_id", "chick_arrivals", type_="foreignkey")
    op.drop_constraint("fk_chick_arrivals_run_id", "chick_arrivals", type_="foreignkey")
    op.drop_index(op.f("ix_chick_arrivals_chick_shipment_id"), table_name="chick_arrivals")
    op.drop_index(op.f("ix_chick_arrivals_run_id"), table_name="chick_arrivals")
    op.drop_column("chick_arrivals", "chick_shipment_id")
    op.drop_column("chick_arrivals", "run_id")

    op.drop_constraint("fk_incubation_batches_production_id", "incubation_batches", type_="foreignkey")
    op.drop_index(op.f("ix_incubation_batches_production_id"), table_name="incubation_batches")
    op.drop_column("incubation_batches", "production_id")
