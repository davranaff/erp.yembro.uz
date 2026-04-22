"""Replace every free-text `currency` column with a hard FK `currency_id`

Seventeen business tables stored an ISO-like code (e.g. ``UZS``) in a
``VARCHAR(8)`` column instead of pointing at the ``currencies`` catalog.
That left the price-bearing rows only loosely coupled to the catalog —
rename a catalog row, change its default flag, etc., and existing rows
silently went stale.

This migration tightens the link: every table with a free-text
``currency`` column gets a ``currency_id`` UUID FK to ``currencies(id)``
with ``ON DELETE RESTRICT``. The code is backfilled via
``(organization_id, code)`` matching, then the old text column is
dropped.

The two tables that already carried a nullable ``currency_id`` alongside
the text column (``cash_transactions``, ``employee_advances``) are
tightened too — backfill any remaining NULLs, mark the column NOT NULL,
and drop the legacy text column.

Downgrade is a no-op (restore from a pre-migration backup if ever
needed).

Revision ID: z7e8f9a0b1c2
Revises: y6d7e8f9a0b1
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "z7e8f9a0b1c2"
down_revision = "y6d7e8f9a0b1"
branch_labels = None
depends_on = None


# (table, text_column, fk_column, nullable)
_TARGETS = [
    ("egg_shipments", "currency", "currency_id", False),
    ("feed_arrivals", "currency", "currency_id", False),
    ("feed_raw_arrivals", "currency", "currency_id", False),
    ("feed_product_shipments", "currency", "currency_id", False),
    ("medicine_arrivals", "currency", "currency_id", False),
    ("medicine_batches", "currency", "currency_id", False),
    ("slaughter_arrivals", "arrival_currency", "arrival_currency_id", True),
    ("slaughter_semi_product_shipments", "currency", "currency_id", False),
    ("chick_arrivals", "currency", "currency_id", False),
    ("chick_shipments", "currency", "currency_id", False),
    ("factory_shipments", "currency", "currency_id", False),
    ("client_debts", "currency", "currency_id", False),
    ("supplier_debts", "currency", "currency_id", False),
    ("debt_payments", "currency", "currency_id", False),
    ("cash_accounts", "currency", "currency_id", False),
]


def upgrade() -> None:
    # 1. Add nullable FK columns + backfill from the text code.
    for table, text_col, fk_col, _ in _TARGETS:
        op.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN IF NOT EXISTS {fk_col} uuid
                REFERENCES currencies (id) ON DELETE RESTRICT
            """
        )
        op.execute(
            f"""
            UPDATE {table} t
            SET {fk_col} = c.id
            FROM currencies c
            WHERE c.organization_id = t.organization_id
              AND UPPER(TRIM(t.{text_col})) = c.code
              AND t.{fk_col} IS NULL
              AND t.{text_col} IS NOT NULL
            """
        )

    # 2. Close the loop on the two tables that already shipped a
    #    nullable currency_id side-by-side with a text column.
    for legacy_table in ("cash_transactions", "employee_advances"):
        op.execute(
            f"""
            UPDATE {legacy_table} t
            SET currency_id = c.id
            FROM currencies c
            WHERE c.organization_id = t.organization_id
              AND UPPER(TRIM(t.currency)) = c.code
              AND t.currency_id IS NULL
              AND t.currency IS NOT NULL
            """
        )

    # 3. Promote FK to NOT NULL where the old text column was NOT NULL,
    #    then drop the legacy text column.
    for table, text_col, fk_col, nullable in _TARGETS:
        if not nullable:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {fk_col} SET NOT NULL"
            )
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {text_col}")

    op.execute(
        "ALTER TABLE cash_transactions ALTER COLUMN currency_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE employee_advances ALTER COLUMN currency_id SET NOT NULL"
    )
    op.execute("ALTER TABLE cash_transactions DROP COLUMN IF EXISTS currency")
    op.execute("ALTER TABLE employee_advances DROP COLUMN IF EXISTS currency")


def downgrade() -> None:
    # Intentionally a no-op — the codebase no longer knows how to
    # serialize the plain-text currency column. Restore from a
    # pre-migration backup if the column must come back.
    pass
