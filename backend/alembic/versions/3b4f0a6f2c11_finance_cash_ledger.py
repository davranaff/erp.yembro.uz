"""finance cash ledger

Revision ID: 3b4f0a6f2c11
Revises: 9a5375cdb1af
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "3b4f0a6f2c11"
down_revision = "9a5375cdb1af"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cash_accounts",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="UZS", nullable=False),
        sa.Column("opening_balance", sa.Numeric(precision=16, scale=2), server_default="0", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("opening_balance >= 0", name="ck_cash_account_opening_balance_non_negative"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_cash_account_org_code"),
        sa.UniqueConstraint("organization_id", "department_id", "name", name="uq_cash_account_org_department_name"),
    )
    op.create_index(op.f("ix_cash_accounts_code"), "cash_accounts", ["code"], unique=False)
    op.create_index(op.f("ix_cash_accounts_department_id"), "cash_accounts", ["department_id"], unique=False)
    op.create_index(op.f("ix_cash_accounts_id"), "cash_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_cash_accounts_organization_id"), "cash_accounts", ["organization_id"], unique=False)

    op.create_table(
        "cash_transactions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("cash_account_id", sa.UUID(), nullable=False),
        sa.Column("expense_id", sa.UUID(), nullable=True),
        sa.Column("counterparty_client_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="UZS", nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("reference_no", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_cash_transaction_amount_positive"),
        sa.CheckConstraint(
            "transaction_type IN ('income', 'expense', 'transfer_in', 'transfer_out', 'adjustment')",
            name="ck_cash_transaction_type_allowed",
        ),
        sa.ForeignKeyConstraint(["cash_account_id"], ["cash_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["counterparty_client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cash_transactions_cash_account_id"), "cash_transactions", ["cash_account_id"], unique=False)
    op.create_index(op.f("ix_cash_transactions_counterparty_client_id"), "cash_transactions", ["counterparty_client_id"], unique=False)
    op.create_index(op.f("ix_cash_transactions_created_by"), "cash_transactions", ["created_by"], unique=False)
    op.create_index(op.f("ix_cash_transactions_expense_id"), "cash_transactions", ["expense_id"], unique=False)
    op.create_index(op.f("ix_cash_transactions_id"), "cash_transactions", ["id"], unique=False)
    op.create_index(op.f("ix_cash_transactions_organization_id"), "cash_transactions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_cash_transactions_reference_no"), "cash_transactions", ["reference_no"], unique=False)
    op.create_index(op.f("ix_cash_transactions_transaction_date"), "cash_transactions", ["transaction_date"], unique=False)
    op.create_index(op.f("ix_cash_transactions_transaction_type"), "cash_transactions", ["transaction_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cash_transactions_transaction_type"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_transaction_date"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_reference_no"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_organization_id"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_id"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_expense_id"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_created_by"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_counterparty_client_id"), table_name="cash_transactions")
    op.drop_index(op.f("ix_cash_transactions_cash_account_id"), table_name="cash_transactions")
    op.drop_table("cash_transactions")

    op.drop_index(op.f("ix_cash_accounts_organization_id"), table_name="cash_accounts")
    op.drop_index(op.f("ix_cash_accounts_id"), table_name="cash_accounts")
    op.drop_index(op.f("ix_cash_accounts_department_id"), table_name="cash_accounts")
    op.drop_index(op.f("ix_cash_accounts_code"), table_name="cash_accounts")
    op.drop_table("cash_accounts")
