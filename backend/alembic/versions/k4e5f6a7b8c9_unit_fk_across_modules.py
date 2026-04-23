"""units as FK everywhere (21 tables) — FK + denormalized unit mirror

Adds `measurement_unit_id UUID NOT NULL FK` next to existing `unit VARCHAR`
on 21 production tables. Existing `unit` varchar stays as a denormalized
mirror synced by a DB trigger: writes to `measurement_unit_id` auto-refresh
`unit = measurement_units.code`.

This lets us enforce FK integrity without breaking the 50+ service-layer
call sites that read `entity["unit"]`. Future work can drop the varchar
once all consumers migrate to the FK.

Revision ID: k4e5f6a7b8c9
Revises: j3d4e5f6a7b8
Create Date: 2026-04-21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "k4e5f6a7b8c9"
down_revision = "j3d4e5f6a7b8"
branch_labels = None
depends_on = None


# (table, old_column) — the column that stores the free-form unit string today
TABLES: tuple[tuple[str, str], ...] = (
    ("egg_shipments", "unit"),
    ("client_debts", "unit"),
    ("feed_arrivals", "unit"),
    ("feed_consumptions", "unit"),
    ("feed_ingredients", "unit"),
    ("feed_types", "unit"),
    ("feed_formula_ingredients", "unit"),
    ("feed_raw_consumptions", "unit"),
    ("feed_production_batches", "unit"),
    ("feed_product_shipments", "unit"),
    ("feed_raw_arrivals", "unit"),
    ("stock_reorder_levels", "unit"),
    ("stock_take_lines", "unit"),
    ("stock_movements", "unit"),
    ("medicine_consumptions", "unit"),
    ("medicine_batches", "unit"),
    ("medicine_arrivals", "unit"),
    ("supplier_debts", "unit"),
    ("slaughter_semi_product_shipments", "unit"),
    ("slaughter_semi_products", "unit"),
    ("factory_monthly_analytics", "feed_quantity_unit"),
)


CANONICAL_UNITS: tuple[tuple[str, str, int], ...] = (
    ("kg", "Kilogramm", 10),
    ("g", "Gramm", 20),
    ("tonna", "Tonna", 30),
    ("dona", "Dona", 40),
    ("quti", "Quti", 50),
    ("palet", "Palet", 60),
    ("qop", "Qop", 70),
    ("litr", "Litr", 80),
    ("ml", "Millilitr", 90),
    ("flakon", "Flakon", 100),
    ("doza", "Doza", 110),
)


ALIASES: dict[str, str] = {
    "pcs": "dona",
    "bosh": "dona",
    "l": "litr",
    "kilogram": "kg",
    "kilogramm": "kg",
}


def _alias_case_expr(column: str) -> str:
    """CASE expression that normalizes aliases; column is addressed via alias `t`."""
    cases = " ".join(
        f"WHEN LOWER(t.{column}) = '{alias}' THEN '{canon}'"
        for alias, canon in ALIASES.items()
    )
    return f"CASE {cases} ELSE LOWER(t.{column}) END"


SYNC_TRIGGER_FN = """
CREATE OR REPLACE FUNCTION sync_unit_from_measurement_unit_id() RETURNS trigger AS $$
DECLARE
    unit_col TEXT := TG_ARGV[0];
BEGIN
    IF NEW.measurement_unit_id IS NOT NULL THEN
        EXECUTE format('UPDATE %I SET %I = mu.code FROM measurement_units mu WHERE mu.id = $1 AND %I.id = $2',
                       TG_TABLE_NAME, unit_col, TG_TABLE_NAME)
        USING NEW.measurement_unit_id, NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Seed canonical measurement_units per organization if missing.
    # Handles two flavours of prior state:
    #   (a) An earlier migration (a1b2c3d4e5f6) inserted the same
    #       display name under a *different* code (e.g. code='ton',
    #       name='Tonna'). We normalize its code to the canonical one
    #       so lookups by the canonical code succeed.
    #   (b) Nothing exists for this (org, code) yet — insert fresh.
    for code, name, sort_order in CANONICAL_UNITS:
        bind.execute(
            sa.text(
                """
                UPDATE measurement_units
                SET code = CAST(:code AS VARCHAR),
                    sort_order = :sort_order,
                    updated_at = NOW()
                WHERE name = CAST(:name AS VARCHAR)
                  AND code <> CAST(:code AS VARCHAR)
                  AND NOT EXISTS (
                      SELECT 1 FROM measurement_units peer
                      WHERE peer.organization_id = measurement_units.organization_id
                        AND peer.code = CAST(:code AS VARCHAR)
                  )
                """
            ),
            {"code": code, "name": name, "sort_order": sort_order},
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO measurement_units (id, organization_id, code, name, sort_order, is_active, created_at, updated_at)
                SELECT gen_random_uuid(), o.id, CAST(:code AS VARCHAR), CAST(:name AS VARCHAR), :sort_order, true, NOW(), NOW()
                FROM organizations o
                WHERE NOT EXISTS (
                    SELECT 1 FROM measurement_units mu
                    WHERE mu.organization_id = o.id
                      AND (mu.code = CAST(:code AS VARCHAR) OR mu.name = CAST(:name AS VARCHAR))
                )
                """
            ),
            {"code": code, "name": name, "sort_order": sort_order},
        )

    # 2. Normalize existing varchar unit values per alias map.
    for table, old_col in TABLES:
        alias_expr = _alias_case_expr(old_col)
        bind.execute(sa.text(f"UPDATE {table} t SET {old_col} = {alias_expr}"))

    # 3. For each table: add FK column, backfill, NOT NULL + FK.
    for table, old_col in TABLES:
        op.add_column(
            table,
            sa.Column("measurement_unit_id", sa.UUID(), nullable=True),
        )

        if table == "stock_take_lines":
            # No organization_id — join through parent stock_takes.
            bind.execute(
                sa.text(
                    f"""
                    UPDATE stock_take_lines t
                    SET measurement_unit_id = mu.id
                    FROM measurement_units mu, stock_takes st
                    WHERE st.id = t.stock_take_id
                      AND mu.organization_id = st.organization_id
                      AND mu.code = LOWER(t.{old_col})
                    """
                )
            )
            bind.execute(
                sa.text(
                    """
                    UPDATE stock_take_lines t
                    SET measurement_unit_id = mu.id
                    FROM measurement_units mu, stock_takes st
                    WHERE st.id = t.stock_take_id
                      AND t.measurement_unit_id IS NULL
                      AND mu.organization_id = st.organization_id
                      AND mu.code = 'kg'
                    """
                )
            )
        else:
            bind.execute(
                sa.text(
                    f"""
                    UPDATE {table} t
                    SET measurement_unit_id = mu.id
                    FROM measurement_units mu
                    WHERE mu.organization_id = t.organization_id
                      AND mu.code = LOWER(t.{old_col})
                    """
                )
            )
            bind.execute(
                sa.text(
                    f"""
                    UPDATE {table} t
                    SET measurement_unit_id = mu.id
                    FROM measurement_units mu
                    WHERE t.measurement_unit_id IS NULL
                      AND mu.organization_id = t.organization_id
                      AND mu.code = 'kg'
                    """
                )
            )

        op.alter_column(table, "measurement_unit_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_measurement_unit_id",
            table,
            "measurement_units",
            ["measurement_unit_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            f"ix_{table}_measurement_unit_id",
            table,
            ["measurement_unit_id"],
        )

    # 4. Install trigger to keep `unit` varchar mirrored from measurement_unit_id on write.
    bind.execute(sa.text(SYNC_TRIGGER_FN))
    for table, old_col in TABLES:
        bind.execute(
            sa.text(
                f"""
                CREATE TRIGGER sync_unit_{table}
                AFTER INSERT OR UPDATE OF measurement_unit_id ON {table}
                FOR EACH ROW EXECUTE FUNCTION sync_unit_from_measurement_unit_id('{old_col}')
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop triggers + function
    for table, _ in TABLES:
        bind.execute(sa.text(f"DROP TRIGGER IF EXISTS sync_unit_{table} ON {table}"))
    bind.execute(sa.text("DROP FUNCTION IF EXISTS sync_unit_from_measurement_unit_id()"))

    # Drop FK + index + column
    for table, _ in TABLES:
        op.drop_index(f"ix_{table}_measurement_unit_id", table_name=table)
        op.drop_constraint(f"fk_{table}_measurement_unit_id", table, type_="foreignkey")
        op.drop_column(table, "measurement_unit_id")
