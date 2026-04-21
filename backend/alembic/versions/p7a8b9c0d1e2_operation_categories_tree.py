"""F0.7 step 1 — tree-ify expense_categories + link cash_transactions.category_id FK

Adds the bones of a hierarchical operation-categories tree on the existing
`expense_categories` table (keeping the name for now, to avoid churn in
the service layer). Concretely:

- expense_categories.parent_id (UUID, self-FK, nullable)
- expense_categories.flow_type (VARCHAR(16), NOT NULL, default 'expense',
  CHECK IN ('income', 'expense'))
- cash_transactions.category_id → FK expense_categories.id (loose: allows
  non-leaf nodes today, service-layer validation handles leaf-only on
  future writes).

Does not restructure existing rows (they stay as top-level leaves).
Does not seed canonical roots — that happens when the owner reorganizes.

Revision ID: p7a8b9c0d1e2
Revises: n6a7b8c9d0e1
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "p7a8b9c0d1e2"
down_revision = "n6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column("parent_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_expense_categories_parent_id",
        "expense_categories",
        "expense_categories",
        ["parent_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_expense_categories_parent_id",
        "expense_categories",
        ["parent_id"],
    )

    op.add_column(
        "expense_categories",
        sa.Column(
            "flow_type",
            sa.String(16),
            nullable=False,
            server_default="expense",
        ),
    )
    op.create_check_constraint(
        "ck_expense_categories_flow_type",
        "expense_categories",
        "flow_type IN ('income', 'expense')",
    )
    op.create_index(
        "ix_expense_categories_flow_type",
        "expense_categories",
        ["flow_type"],
    )

    # Link cash_transactions.category_id as a real FK (nullable).
    op.create_foreign_key(
        "fk_cash_transactions_category_id",
        "cash_transactions",
        "expense_categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cash_transactions_category_id", "cash_transactions", type_="foreignkey")

    op.drop_index("ix_expense_categories_flow_type", table_name="expense_categories")
    op.drop_constraint("ck_expense_categories_flow_type", "expense_categories", type_="check")
    op.drop_column("expense_categories", "flow_type")

    op.drop_index("ix_expense_categories_parent_id", table_name="expense_categories")
    op.drop_constraint("fk_expense_categories_parent_id", "expense_categories", type_="foreignkey")
    op.drop_column("expense_categories", "parent_id")
