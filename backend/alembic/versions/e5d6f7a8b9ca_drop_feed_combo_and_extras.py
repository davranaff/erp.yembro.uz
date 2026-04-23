"""Drop feed_formula_ingredients table + formula.version + ingredient.supplier_category

The combination table, the formula version column and the supplier
category on ingredients were removed from the domain model — they were
never wired into costing, MRP, or procurement flows, so carrying them
was adding noise to the CRUD surface (see the "Создание записи" forms
where those fields had no clear meaning to users).

The migration also scrubs the permissions, role_permissions and
workspace_resources rows that used to surface the dropped feature.

Revision ID: e5d6f7a8b9ca
Revises: d4c5e6a7b8c9
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "e5d6f7a8b9ca"
down_revision = "d4c5e6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove workspace resource + permissions tied to formula ingredients
    # before dropping the table itself.
    op.execute(
        "DELETE FROM workspace_resources WHERE key = 'formula-ingredients'"
    )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'feed_formula_ingredient.%')"
    )
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'feed_formula_ingredient.%'"
    )

    # Audit logs reference these tables via entity_table / rows — leave
    # historical entries alone (they are append-only), but drop the
    # operational data.
    op.execute("DROP TABLE IF EXISTS feed_formula_ingredients CASCADE")

    # Drop the column-level CHECK before dropping the column, otherwise
    # Alembic complains on some Postgres versions.
    op.execute(
        "ALTER TABLE feed_formulas DROP CONSTRAINT IF EXISTS ck_feed_formula_version_positive"
    )
    op.execute("ALTER TABLE feed_formulas DROP COLUMN IF EXISTS version")

    op.execute(
        "ALTER TABLE feed_ingredients DROP COLUMN IF EXISTS supplier_category"
    )


def downgrade() -> None:
    # One-way clean-up. Recreating the combination table would leave
    # data empty anyway and no upstream code references it any more, so
    # we don't provide a rollback path.
    raise RuntimeError(
        "Downgrade not supported — feed_formula_ingredients / version "
        "/ supplier_category were removed permanently."
    )
