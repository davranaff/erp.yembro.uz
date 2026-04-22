"""Consolidate shared catalogs in their owning module menus

Each operational module (egg, incubation, factory, feed, medicine,
slaughter) duplicated the same reference resources in its dropdown:
Склады (warehouses), Клиенты (clients), Сотрудники (employees),
Категории расходов (expense-categories) and Кассы (cash-accounts).
Operators saw six "Склады" entries — one per module — and had no way
to tell they pointed at the same underlying tables.

This migration keeps each shared catalog in exactly one place:

  warehouses          → core   (Справочник)
  clients             → core   (Справочник)
  employees           → hr     (Сотрудники)
  expense-categories  → finance + core
  cash-accounts       → finance

And flips ``is_active = false`` on every other copy.

Nothing changes at the table / API level — the same tables are used,
the same permissions apply, and operators can still open records
inside the owning module. The per-module stock-movements, cash-
transactions and client-debts entries stay intact because they are
operational journals that need the department context.

Revision ID: w4b5c6d7e8f9
Revises: v3a4b5c6d7e8
Create Date: 2026-04-22
"""

from __future__ import annotations

from alembic import op


revision = "w4b5c6d7e8f9"
down_revision = "v3a4b5c6d7e8"
branch_labels = None
depends_on = None


# Map of resource key -> modules where the resource should stay visible.
# Rows with that key in any other module get is_active = false.
KEEP_IN: dict[str, tuple[str, ...]] = {
    "warehouses": ("core",),
    "clients": ("core",),
    "employees": ("hr",),
    "expense-categories": ("core", "finance"),
    "cash-accounts": ("finance",),
}


def upgrade() -> None:
    for key, owners in KEEP_IN.items():
        owners_sql = ", ".join(f"'{owner}'" for owner in owners)
        op.execute(
            f"""
            UPDATE workspace_resources
            SET is_active = false
            WHERE key = '{key}'
              AND module_key NOT IN ({owners_sql})
            """
        )


def downgrade() -> None:
    for key, owners in KEEP_IN.items():
        owners_sql = ", ".join(f"'{owner}'" for owner in owners)
        op.execute(
            f"""
            UPDATE workspace_resources
            SET is_active = true
            WHERE key = '{key}'
              AND module_key NOT IN ({owners_sql})
            """
        )
