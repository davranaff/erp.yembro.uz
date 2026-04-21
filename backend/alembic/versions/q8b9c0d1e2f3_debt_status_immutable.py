"""F0.8 posting_status lifecycle on client_debts + supplier_debts

Adds `posting_status` VARCHAR(20) NOT NULL default 'posted' to both debt
tables with CHECK ∈ {draft, posted, reversed}. Existing rows become
'posted' (historical debts treated as immutable).

Named `posting_status` to avoid collision with the existing `status`
column, which tracks payment state (open/partially_paid/closed).

Service-layer enforcement (BaseService.update) rejects user-facing
updates on rows with posting_status = 'posted'. Auto-AR/AP services
bypass this because they manage the parent-shipment state and upsert
while the parent is still in-flight.

Revision ID: q8b9c0d1e2f3
Revises: p7a8b9c0d1e2
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "q8b9c0d1e2f3"
down_revision = "p7a8b9c0d1e2"
branch_labels = None
depends_on = None


TABLES = ("client_debts", "supplier_debts")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column(
                "posting_status",
                sa.String(20),
                nullable=False,
                server_default="posted",
            ),
        )
        op.create_check_constraint(
            f"ck_{table}_posting_status",
            table,
            "posting_status IN ('draft', 'posted', 'reversed')",
        )
        op.create_index(f"ix_{table}_posting_status", table, ["posting_status"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(f"ix_{table}_posting_status", table_name=table)
        op.drop_constraint(f"ck_{table}_posting_status", table, type_="check")
        op.drop_column(table, "posting_status")
