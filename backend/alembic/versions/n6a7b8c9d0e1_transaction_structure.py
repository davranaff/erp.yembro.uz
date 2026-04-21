"""F0.6 structured transaction fields on cash_transactions + stock_movements

Adds fields that make cash_transactions and stock_movements suitable as
a stable transactional log — enough for a future accounting overlay
without a schema rewrite.

cash_transactions gets:
- department_id (FK, backfilled from cash_account.department_id)
- category_id (UUID, no FK yet — waits for F0.7 operation_categories tree)
- counterparty_type + counterparty_id (replaces the single
  counterparty_client_id with a polymorphic pair; old FK stays for
  backcompat and is mirrored)
- source_type + source_id (polymorphic link to what spawned the row)
- status (draft / posted; existing → posted)
- currency_id (FK to currencies, backfilled by code lookup)
- exchange_rate_to_base + amount_in_base (snapshotted at posting time,
  1.0 / amount for legacy rows)

stock_movements gets:
- counterparty_type + counterparty_id (external supplier/client — the
  internal dept-to-dept counterparty columns stay as-is)
- composite index (department_id, occurred_on) for dashboard queries

currencies gets:
- exchange_rate_to_base (NUMERIC(10, 6), default 1.0)

Revision ID: n6a7b8c9d0e1
Revises: m5f6a7b8c9d0
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "n6a7b8c9d0e1"
down_revision = "m5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- currencies.exchange_rate_to_base -----------------------------------
    op.add_column(
        "currencies",
        sa.Column(
            "exchange_rate_to_base",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="1.0",
        ),
    )

    # --- cash_transactions --------------------------------------------------
    op.add_column("cash_transactions", sa.Column("department_id", sa.UUID(), nullable=True))
    op.add_column("cash_transactions", sa.Column("category_id", sa.UUID(), nullable=True))
    op.add_column("cash_transactions", sa.Column("counterparty_type", sa.String(32), nullable=True))
    op.add_column("cash_transactions", sa.Column("counterparty_id", sa.UUID(), nullable=True))
    op.add_column("cash_transactions", sa.Column("source_type", sa.String(64), nullable=True))
    op.add_column("cash_transactions", sa.Column("source_id", sa.UUID(), nullable=True))
    op.add_column(
        "cash_transactions",
        sa.Column("status", sa.String(32), nullable=False, server_default="posted"),
    )
    op.add_column("cash_transactions", sa.Column("currency_id", sa.UUID(), nullable=True))
    op.add_column(
        "cash_transactions",
        sa.Column(
            "exchange_rate_to_base",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="1.0",
        ),
    )
    op.add_column("cash_transactions", sa.Column("amount_in_base", sa.Numeric(16, 2), nullable=True))

    # Backfill department_id from cash_account.department_id
    bind.execute(
        sa.text(
            """
            UPDATE cash_transactions t
            SET department_id = ca.department_id
            FROM cash_accounts ca
            WHERE ca.id = t.cash_account_id
              AND t.department_id IS NULL
            """
        )
    )
    op.alter_column("cash_transactions", "department_id", nullable=False)

    # Backfill counterparty_* from existing client FK
    bind.execute(
        sa.text(
            """
            UPDATE cash_transactions
            SET counterparty_type = 'client',
                counterparty_id = counterparty_client_id
            WHERE counterparty_client_id IS NOT NULL
              AND counterparty_type IS NULL
            """
        )
    )

    # Backfill source_type/source_id from expense link
    bind.execute(
        sa.text(
            """
            UPDATE cash_transactions
            SET source_type = 'expense',
                source_id = expense_id
            WHERE expense_id IS NOT NULL
              AND source_type IS NULL
            """
        )
    )

    # Backfill currency_id by (org, code)
    bind.execute(
        sa.text(
            """
            UPDATE cash_transactions t
            SET currency_id = c.id
            FROM currencies c
            WHERE c.organization_id = t.organization_id
              AND c.code = t.currency
              AND t.currency_id IS NULL
            """
        )
    )

    # Snapshot amount_in_base (= amount × rate, 1.0 for legacy)
    bind.execute(
        sa.text(
            """
            UPDATE cash_transactions
            SET amount_in_base = amount * exchange_rate_to_base
            WHERE amount_in_base IS NULL
            """
        )
    )
    op.alter_column("cash_transactions", "amount_in_base", nullable=False)

    # FKs + constraints
    op.create_foreign_key(
        "fk_cash_transactions_department_id",
        "cash_transactions",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_cash_transactions_currency_id",
        "cash_transactions",
        "currencies",
        ["currency_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_cash_transactions_status",
        "cash_transactions",
        "status IN ('draft', 'posted', 'reversed')",
    )
    op.create_check_constraint(
        "ck_cash_transactions_counterparty_type",
        "cash_transactions",
        "counterparty_type IS NULL OR counterparty_type IN ('client', 'supplier', 'employee')",
    )

    # Indexes
    op.create_index(
        "ix_cash_transactions_department_id_operation_date",
        "cash_transactions",
        ["department_id", "transaction_date"],
    )
    op.create_index(
        "ix_cash_transactions_category_id_operation_date",
        "cash_transactions",
        ["category_id", "transaction_date"],
    )
    op.create_index(
        "ix_cash_transactions_source",
        "cash_transactions",
        ["source_type", "source_id"],
    )
    op.create_index(
        "ix_cash_transactions_counterparty",
        "cash_transactions",
        ["counterparty_type", "counterparty_id"],
    )
    op.create_index("ix_cash_transactions_status", "cash_transactions", ["status"])

    # --- stock_movements ----------------------------------------------------
    op.add_column("stock_movements", sa.Column("counterparty_type", sa.String(32), nullable=True))
    op.add_column("stock_movements", sa.Column("counterparty_id", sa.UUID(), nullable=True))
    op.create_check_constraint(
        "ck_stock_movements_counterparty_type",
        "stock_movements",
        "counterparty_type IS NULL OR counterparty_type IN ('client', 'supplier', 'employee')",
    )
    op.create_index(
        "ix_stock_movements_department_id_occurred_on",
        "stock_movements",
        ["department_id", "occurred_on"],
    )
    op.create_index(
        "ix_stock_movements_counterparty",
        "stock_movements",
        ["counterparty_type", "counterparty_id"],
    )


def downgrade() -> None:
    # stock_movements
    op.drop_index("ix_stock_movements_counterparty", table_name="stock_movements")
    op.drop_index("ix_stock_movements_department_id_occurred_on", table_name="stock_movements")
    op.drop_constraint("ck_stock_movements_counterparty_type", "stock_movements", type_="check")
    op.drop_column("stock_movements", "counterparty_id")
    op.drop_column("stock_movements", "counterparty_type")

    # cash_transactions
    op.drop_index("ix_cash_transactions_status", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_counterparty", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_source", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_category_id_operation_date", table_name="cash_transactions")
    op.drop_index("ix_cash_transactions_department_id_operation_date", table_name="cash_transactions")
    op.drop_constraint("ck_cash_transactions_counterparty_type", "cash_transactions", type_="check")
    op.drop_constraint("ck_cash_transactions_status", "cash_transactions", type_="check")
    op.drop_constraint("fk_cash_transactions_currency_id", "cash_transactions", type_="foreignkey")
    op.drop_constraint("fk_cash_transactions_department_id", "cash_transactions", type_="foreignkey")
    op.drop_column("cash_transactions", "amount_in_base")
    op.drop_column("cash_transactions", "exchange_rate_to_base")
    op.drop_column("cash_transactions", "currency_id")
    op.drop_column("cash_transactions", "status")
    op.drop_column("cash_transactions", "source_id")
    op.drop_column("cash_transactions", "source_type")
    op.drop_column("cash_transactions", "counterparty_id")
    op.drop_column("cash_transactions", "counterparty_type")
    op.drop_column("cash_transactions", "category_id")
    op.drop_column("cash_transactions", "department_id")

    # currencies
    op.drop_column("currencies", "exchange_rate_to_base")
