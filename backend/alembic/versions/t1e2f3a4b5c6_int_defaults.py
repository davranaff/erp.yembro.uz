"""Add SQL-level DEFAULT 0 to integer counters that had only Python-side defaults

Models declared ``default=0`` at the SQLAlchemy level for a number of
non-nullable integer counter columns (eggs_broken, birds_received,
mortality_count, etc.). Python-side defaults only apply when writing
through the ORM — the raw asyncpg INSERTs used by our CRUD layer
bypass them entirely, so any payload that omits one of these fields
hits ``NOT NULL violation`` and surfaces to the operator as
``Field "X" has an invalid value.``

This migration sets ``DEFAULT 0`` at the SQL level so the DB fills the
value when the INSERT leaves the column out. No data change — the
columns were already ``NOT NULL`` with no NULLs present.

Revision ID: t1e2f3a4b5c6
Revises: s0d1e2f3a4b5
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "t1e2f3a4b5c6"
down_revision = "s0d1e2f3a4b5"
branch_labels = None
depends_on = None


DEFAULTS: dict[str, tuple[str, ...]] = {
    "egg_shipments": ("eggs_broken",),
    "egg_monthly_analytics": (
        "produced_count",
        "broken_count",
        "shipped_count",
        "rejected_count",
    ),
    "egg_production": (
        "eggs_collected",
        "eggs_broken",
        "eggs_rejected",
        "total_shelled",
    ),
    "slaughter_arrivals": ("birds_received",),
    "slaughter_monthly_analytics": (
        "birds_received",
        "birds_processed",
        "first_sort_count",
        "second_sort_count",
        "bad_count",
    ),
    "slaughter_processings": (
        "birds_processed",
        "first_sort_count",
        "second_sort_count",
        "bad_count",
    ),
    "factory_daily_logs": ("mortality_count", "sick_count", "healthy_count"),
    "incubation_runs": (
        "grade_1_count",
        "grade_2_count",
        "bad_eggs_count",
        "chicks_hatched",
        "chicks_destroyed",
    ),
    "chick_arrivals": ("chicks_count",),
    "factory_monthly_analytics": ("chicks_arrived",),
    "incubation_monthly_analytics": (
        "eggs_arrived",
        "grade1_count",
        "grade2_count",
        "bad_eggs_count",
        "chicks_hatched",
        "chicks_shipped",
    ),
}


def upgrade() -> None:
    for table, columns in DEFAULTS.items():
        for column in columns:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT 0')


def downgrade() -> None:
    for table, columns in DEFAULTS.items():
        for column in columns:
            op.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT')
