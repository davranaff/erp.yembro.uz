"""Enable dashboard analytics for finance, hr and core modules.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-04-18
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


_MODULE_ANALYTICS = (
    (
        "finance",
        "finance",
        ["expense.read", "cash_account.read", "cash_transaction.read", "client_debt.read", "supplier_debt.read", "debt_payment.read"],
    ),
    (
        "hr",
        "hr",
        ["employee.read", "position.read", "role.read"],
    ),
    (
        "core",
        "core",
        ["client.read", "department.read", "audit_log.read"],
    ),
)


def upgrade() -> None:
    bind = op.get_bind()
    for key, section_key, permissions in _MODULE_ANALYTICS:
        bind.execute(
            sa.text(
                """
                UPDATE department_modules
                SET analytics_section_key = :section_key,
                    analytics_read_permissions = CAST(:permissions AS json)
                WHERE key = :key
                """
            ),
            {
                "section_key": section_key,
                "permissions": json.dumps(permissions),
                "key": key,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    for key, _, _ in _MODULE_ANALYTICS:
        bind.execute(
            sa.text(
                """
                UPDATE department_modules
                SET analytics_section_key = NULL,
                    analytics_read_permissions = CAST('[]' AS json)
                WHERE key = :key
                """
            ),
            {"key": key},
        )
