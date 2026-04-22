"""Drop the expenses table + cash_transactions.expense_id column

The operator-facing Расходы screen was removed (cash_transactions
with transaction_type='expense' already covers the "money went out"
flow). The rollup dashboard queries now aggregate directly from
``cash_transactions`` + ``expense_categories``, so the standalone
``expenses`` table no longer earns its keep.

Migration steps:

1. Drop the FK / column ``cash_transactions.expense_id``. It was
   nullable — no risk of orphaning live rows.
2. Drop ``DELETE`` every leftover ``workspace_resources`` row with
   ``key='expenses'`` (they were already deactivated by the earlier
   hide-expenses-menu migration).
3. ``DROP TABLE IF EXISTS expenses CASCADE`` — takes down the table
   and any still-referenced indexes / sequences.

Downgrade is a no-op; restore from a pre-drop backup if the table
ever needs to come back.

Revision ID: y6d7e8f9a0b1
Revises: x5c6d7e8f9a0
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "y6d7e8f9a0b1"
down_revision = "x5c6d7e8f9a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE cash_transactions
        DROP COLUMN IF EXISTS expense_id
        """
    )

    op.execute(
        """
        DELETE FROM workspace_resources
        WHERE key = 'expenses'
        """
    )

    op.execute('DROP TABLE IF EXISTS "expenses" CASCADE')


def downgrade() -> None:
    # Intentionally a no-op — the data model and fixture pipeline are
    # gone. Restore from a pre-drop backup if you really need the
    # expenses table back.
    pass
