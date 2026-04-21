"""F0.10 employee_advances (подотчётные)

Cash handed out to an employee for operational spending. Not an expense
until reconciled against receipts — until then it's a receivable from
the employee. Balance derives from cash_transactions via source_type:
- 'advance' (issue)            → +issued
- 'advance_reconciliation'     → +reconciled (moved into expenses)
- 'advance_return'             → +returned (back to cash)

Revision ID: r9c0d1e2f3a4
Revises: q8b9c0d1e2f3
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r9c0d1e2f3a4"
down_revision = "q8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "employee_advances",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("amount_issued", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=True),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["currency_id"], ["currencies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["employees.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount_issued > 0", name="ck_employee_advances_amount_positive"),
        sa.CheckConstraint(
            "status IN ('open', 'reconciled', 'cancelled')",
            name="ck_employee_advances_status",
        ),
    )
    op.create_index("ix_employee_advances_organization_id", "employee_advances", ["organization_id"])
    op.create_index("ix_employee_advances_department_id", "employee_advances", ["department_id"])
    op.create_index("ix_employee_advances_employee_id", "employee_advances", ["employee_id"])
    op.create_index("ix_employee_advances_issued_on", "employee_advances", ["issued_on"])
    op.create_index("ix_employee_advances_status", "employee_advances", ["status"])


def downgrade() -> None:
    op.drop_index("ix_employee_advances_status", table_name="employee_advances")
    op.drop_index("ix_employee_advances_issued_on", table_name="employee_advances")
    op.drop_index("ix_employee_advances_employee_id", table_name="employee_advances")
    op.drop_index("ix_employee_advances_department_id", table_name="employee_advances")
    op.drop_index("ix_employee_advances_organization_id", table_name="employee_advances")
    op.drop_table("employee_advances")
