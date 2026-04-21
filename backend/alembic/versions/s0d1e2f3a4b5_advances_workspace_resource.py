"""F0.10 frontend — advances workspace resource + finance implicit perms

Adds the `/advances` resource to the finance module menu and lets every
finance-scoped user read it alongside cash-transactions.

Revision ID: s0d1e2f3a4b5
Revises: r9c0d1e2f3a4
Create Date: 2026-04-22
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "s0d1e2f3a4b5"
down_revision = "r9c0d1e2f3a4"
branch_labels = None
depends_on = None


workspace_resources_table = sa.table(
    "workspace_resources",
    sa.column("id", sa.UUID()),
    sa.column("module_key", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("path", sa.String()),
    sa.column("description", sa.String()),
    sa.column("permission_prefix", sa.String()),
    sa.column("api_module_key", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_head_visible", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
)

department_modules_table = sa.table(
    "department_modules",
    sa.column("key", sa.String()),
    sa.column("implicit_read_permissions", sa.JSON()),
)


ADVANCE_RESOURCE: dict[str, object] = {
    "id": "32000000-0000-0000-0000-000000000401",
    "module_key": "finance",
    "key": "advances",
    "name": "Подотчётные",
    "path": "advances",
    "description": "Наличные, выданные сотрудникам под отчёт",
    "permission_prefix": "employee_advance",
    "api_module_key": "finance",
    "sort_order": 50,
    "is_head_visible": False,
    "is_active": True,
}

FINANCE_IMPLICIT_ADDITIONS = ("employee_advance.read",)


def _normalize_codes(raw_value: object | None) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return []
        try:
            parsed = json.loads(candidate)
        except Exception:
            parsed = [candidate]
    elif isinstance(raw_value, (list, tuple, set)):
        parsed = list(raw_value)
    else:
        parsed = [raw_value]
    normalized: list[str] = []
    for item in parsed:
        code = str(item or "").strip().lower()
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def _merge_codes(existing: object | None, additions: tuple[str, ...]) -> list[str]:
    merged = _normalize_codes(existing)
    for code in additions:
        c = code.strip().lower()
        if c and c not in merged:
            merged.append(c)
    return merged


def _strip_codes(existing: object | None, removals: tuple[str, ...]) -> list[str]:
    current = _normalize_codes(existing)
    remove = {c.strip().lower() for c in removals}
    return [code for code in current if code not in remove]


def upgrade() -> None:
    bind = op.get_bind()

    payload = {
        "module_key": ADVANCE_RESOURCE["module_key"],
        "key": ADVANCE_RESOURCE["key"],
        "name": ADVANCE_RESOURCE["name"],
        "path": ADVANCE_RESOURCE["path"],
        "description": ADVANCE_RESOURCE["description"],
        "permission_prefix": ADVANCE_RESOURCE["permission_prefix"],
        "api_module_key": ADVANCE_RESOURCE["api_module_key"],
        "sort_order": int(ADVANCE_RESOURCE["sort_order"]),
        "is_head_visible": bool(ADVANCE_RESOURCE["is_head_visible"]),
        "is_active": bool(ADVANCE_RESOURCE["is_active"]),
    }
    existing_id = bind.execute(
        sa.select(workspace_resources_table.c.id).where(
            workspace_resources_table.c.module_key == ADVANCE_RESOURCE["module_key"],
            workspace_resources_table.c.key == ADVANCE_RESOURCE["key"],
        )
    ).scalar()
    if existing_id is None:
        bind.execute(
            workspace_resources_table.insert().values(
                id=UUID(str(ADVANCE_RESOURCE["id"])),
                **payload,
            )
        )
    else:
        bind.execute(
            workspace_resources_table.update()
            .where(workspace_resources_table.c.id == existing_id)
            .values(**payload)
        )

    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "finance")
    ).mappings().first()
    if row is not None:
        merged = _merge_codes(row.get("implicit_read_permissions"), FINANCE_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "finance")
            .values(implicit_read_permissions=merged)
        )


def downgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "finance")
    ).mappings().first()
    if row is not None:
        stripped = _strip_codes(row.get("implicit_read_permissions"), FINANCE_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "finance")
            .values(implicit_read_permissions=stripped)
        )
    bind.execute(
        workspace_resources_table.delete().where(
            workspace_resources_table.c.module_key == "finance",
            workspace_resources_table.c.key == "advances",
        )
    )
