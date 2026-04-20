"""factory menu parity: head visibility + monthly analytics resource

Revision ID: h1b2c3d4e5f6
Revises: g0a1b2c3d4e5
Create Date: 2026-04-20
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "h1b2c3d4e5f6"
down_revision = "g0a1b2c3d4e5"
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


HEAD_VISIBLE_FACTORY_RESOURCES: tuple[str, ...] = (
    "flocks",
    "daily-logs",
    "shipments",
    "medicine-usages",
    "vaccination-plans",
)


FACTORY_MONTHLY_ANALYTICS_RESOURCE: dict[str, object] = {
    "id": "32000000-0000-0000-0000-000000000206",
    "module_key": "factory",
    "key": "monthly-analytics",
    "name": "Месячная аналитика",
    "path": "factory-monthly-analytics",
    "description": "Помесячные показатели фабрики",
    "permission_prefix": "factory_monthly_analytics",
    "api_module_key": "incubation",
    "sort_order": 34,
    "is_head_visible": True,
    "is_active": True,
}


FACTORY_IMPLICIT_ADDITIONS: tuple[str, ...] = ("factory_monthly_analytics.read",)


def _normalize_codes(raw_value: object | None) -> list[str]:
    if raw_value is None:
        return []

    parsed: object
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
        normalized_code = code.strip().lower()
        if normalized_code and normalized_code not in merged:
            merged.append(normalized_code)
    return merged


def upgrade() -> None:
    bind = op.get_bind()

    for resource_key in HEAD_VISIBLE_FACTORY_RESOURCES:
        bind.execute(
            workspace_resources_table.update()
            .where(
                workspace_resources_table.c.module_key == "factory",
                workspace_resources_table.c.key == resource_key,
            )
            .values(is_head_visible=True)
        )

    resource = FACTORY_MONTHLY_ANALYTICS_RESOURCE
    payload = {
        "module_key": resource["module_key"],
        "key": resource["key"],
        "name": resource["name"],
        "path": resource["path"],
        "description": resource["description"],
        "permission_prefix": resource["permission_prefix"],
        "api_module_key": resource["api_module_key"],
        "sort_order": int(resource["sort_order"]),
        "is_head_visible": bool(resource["is_head_visible"]),
        "is_active": bool(resource["is_active"]),
    }
    existing_id = bind.execute(
        sa.select(workspace_resources_table.c.id).where(
            workspace_resources_table.c.module_key == resource["module_key"],
            workspace_resources_table.c.key == resource["key"],
        )
    ).scalar()

    if existing_id is None:
        bind.execute(
            workspace_resources_table.insert().values(
                id=UUID(str(resource["id"])),
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
        ).where(department_modules_table.c.key == "factory")
    ).mappings().first()
    if row is not None:
        merged_codes = _merge_codes(row.get("implicit_read_permissions"), FACTORY_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "factory")
            .values(implicit_read_permissions=merged_codes)
        )


def downgrade() -> None:
    bind = op.get_bind()

    for resource_key in HEAD_VISIBLE_FACTORY_RESOURCES:
        bind.execute(
            workspace_resources_table.update()
            .where(
                workspace_resources_table.c.module_key == "factory",
                workspace_resources_table.c.key == resource_key,
            )
            .values(is_head_visible=False)
        )

    bind.execute(
        workspace_resources_table.delete().where(
            workspace_resources_table.c.module_key == "factory",
            workspace_resources_table.c.key == "monthly-analytics",
        )
    )

    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "factory")
    ).mappings().first()
    if row is not None:
        current_codes = _normalize_codes(row.get("implicit_read_permissions"))
        removal = {code.strip().lower() for code in FACTORY_IMPLICIT_ADDITIONS}
        next_codes = [code for code in current_codes if code not in removal]
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "factory")
            .values(implicit_read_permissions=next_codes)
        )
