"""Hide the standalone "Расходы" menu entry — cash transactions cover it

The `expenses` table is the write target of a cash_transaction with
``transaction_type='expense'`` (see CashTransactionService._sync_expense)
and otherwise only receives rows for the corner case "charge accrued
but not yet paid from the register". That corner case is rare in the
current operator flow and caused confusion — two near-duplicate menu
entries ("Расходы" and "Кассовые операции") for the same action.

This migration flips ``is_active`` to false on every
``workspace_resources`` row whose ``key='expenses'`` so the menu no
longer surfaces the standalone tab. The `expenses` table and its
relationships stay fully intact — `cash_transactions` still auto-
creates expense rows, the dashboard still reads them, and operators
can re-enable the resource later with a single UPDATE if the workflow
changes.

Revision ID: u2f3a4b5c6d7
Revises: t1e2f3a4b5c6
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "u2f3a4b5c6d7"
down_revision = "t1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE workspace_resources
        SET is_active = false
        WHERE key = 'expenses'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE workspace_resources
        SET is_active = true
        WHERE key = 'expenses'
        """
    )
