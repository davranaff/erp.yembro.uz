"""Allow 'feed_raw' item_type in stock_movements check constraint.

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op


revision = "b1c2d3e4f5a6"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_stock_movement_item_type_allowed", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movement_item_type_allowed",
        "stock_movements",
        "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stock_movement_item_type_allowed", "stock_movements", type_="check")
    op.create_check_constraint(
        "ck_stock_movement_item_type_allowed",
        "stock_movements",
        "item_type IN ('egg', 'chick', 'feed', 'medicine', 'semi_product')",
    )
