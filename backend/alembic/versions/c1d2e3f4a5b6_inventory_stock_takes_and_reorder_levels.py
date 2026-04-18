"""Inventory stock takes and reorder levels.

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c1d2e3f4a5b6"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_takes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reference_no", sa.String(length=64), nullable=False),
        sa.Column("counted_on", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "performed_by_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "finalized_by_employee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("employees.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("organization_id", "reference_no", name="uq_stock_take_org_reference"),
        sa.CheckConstraint(
            "status IN ('draft', 'finalized', 'cancelled')",
            name="ck_stock_take_status_allowed",
        ),
    )
    op.create_index(op.f("ix_stock_takes_id"), "stock_takes", ["id"])
    op.create_index(op.f("ix_stock_takes_organization_id"), "stock_takes", ["organization_id"])
    op.create_index(op.f("ix_stock_takes_department_id"), "stock_takes", ["department_id"])
    op.create_index(op.f("ix_stock_takes_warehouse_id"), "stock_takes", ["warehouse_id"])
    op.create_index(op.f("ix_stock_takes_reference_no"), "stock_takes", ["reference_no"])
    op.create_index(op.f("ix_stock_takes_counted_on"), "stock_takes", ["counted_on"])
    op.create_index(op.f("ix_stock_takes_status"), "stock_takes", ["status"])
    op.create_index(
        op.f("ix_stock_takes_performed_by_employee_id"),
        "stock_takes",
        ["performed_by_employee_id"],
    )

    op.create_table(
        "stock_take_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "stock_take_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("stock_takes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("expected_quantity", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("counted_quantity", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="pcs"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "stock_take_id",
            "item_type",
            "item_key",
            name="uq_stock_take_line_take_item",
        ),
        sa.CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
            name="ck_stock_take_line_item_type_allowed",
        ),
        sa.CheckConstraint("expected_quantity >= 0", name="ck_stock_take_line_expected_non_negative"),
        sa.CheckConstraint("counted_quantity >= 0", name="ck_stock_take_line_counted_non_negative"),
    )
    op.create_index(op.f("ix_stock_take_lines_id"), "stock_take_lines", ["id"])
    op.create_index(op.f("ix_stock_take_lines_stock_take_id"), "stock_take_lines", ["stock_take_id"])
    op.create_index(op.f("ix_stock_take_lines_item_type"), "stock_take_lines", ["item_type"])
    op.create_index(op.f("ix_stock_take_lines_item_key"), "stock_take_lines", ["item_key"])

    op.create_table(
        "stock_reorder_levels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=30), nullable=False),
        sa.Column("item_key", sa.String(length=160), nullable=False),
        sa.Column("min_quantity", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("max_quantity", sa.Numeric(16, 3), nullable=True),
        sa.Column("reorder_quantity", sa.Numeric(16, 3), nullable=True),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="pcs"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "organization_id",
            "warehouse_id",
            "item_type",
            "item_key",
            name="uq_stock_reorder_level_scope_item",
        ),
        sa.CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
            name="ck_stock_reorder_level_item_type_allowed",
        ),
        sa.CheckConstraint("min_quantity >= 0", name="ck_stock_reorder_level_min_non_negative"),
        sa.CheckConstraint(
            "max_quantity IS NULL OR max_quantity >= min_quantity",
            name="ck_stock_reorder_level_max_gte_min",
        ),
        sa.CheckConstraint(
            "reorder_quantity IS NULL OR reorder_quantity >= 0",
            name="ck_stock_reorder_level_reorder_non_negative",
        ),
    )
    op.create_index(op.f("ix_stock_reorder_levels_id"), "stock_reorder_levels", ["id"])
    op.create_index(op.f("ix_stock_reorder_levels_organization_id"), "stock_reorder_levels", ["organization_id"])
    op.create_index(op.f("ix_stock_reorder_levels_department_id"), "stock_reorder_levels", ["department_id"])
    op.create_index(op.f("ix_stock_reorder_levels_warehouse_id"), "stock_reorder_levels", ["warehouse_id"])
    op.create_index(op.f("ix_stock_reorder_levels_item_type"), "stock_reorder_levels", ["item_type"])
    op.create_index(op.f("ix_stock_reorder_levels_item_key"), "stock_reorder_levels", ["item_key"])


def downgrade() -> None:
    op.drop_table("stock_reorder_levels")
    op.drop_table("stock_take_lines")
    op.drop_table("stock_takes")
