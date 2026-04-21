"""factory feed-consumption + drop stock-takes/reorder-levels from menus

Revision ID: i2c3d4e5f6a7
Revises: h1b2c3d4e5f6
Create Date: 2026-04-20
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "i2c3d4e5f6a7"
down_revision = "h1b2c3d4e5f6"
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


DROP_RESOURCE_KEYS: tuple[str, ...] = ("stock-takes", "reorder-levels")

AFFECTED_MODULES: tuple[str, ...] = (
    "egg",
    "incubation",
    "factory",
    "feed",
    "medicine",
    "slaughter",
)

REMOVED_IMPLICIT_PERMISSIONS: tuple[str, ...] = (
    "stock_take.read",
    "stock_reorder_level.read",
)


FACTORY_FEED_CONSUMPTION_RESOURCE: dict[str, object] = {
    "id": "32000000-0000-0000-0000-000000000207",
    "module_key": "factory",
    "key": "feed-consumptions",
    "name": "Расход корма",
    "path": "feed-consumptions",
    "description": "Расход корма по партиям птенцов",
    "permission_prefix": "feed_consumption",
    "api_module_key": "factory",
    "sort_order": 26,
    "is_head_visible": True,
    "is_active": True,
}

FACTORY_IMPLICIT_ADDITIONS: tuple[str, ...] = ("feed_consumption.read",)

DOWNGRADE_STOCK_OPS_RESOURCES: tuple[dict[str, object], ...] = (
    {
        "id": "320000c1-0000-0000-0000-000000000001",
        "module_key": "egg",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 56,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000001",
        "module_key": "egg",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 57,
    },
    {
        "id": "320000c1-0000-0000-0000-000000000002",
        "module_key": "incubation",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 38,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000002",
        "module_key": "incubation",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 39,
    },
    {
        "id": "320000c1-0000-0000-0000-000000000003",
        "module_key": "factory",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 36,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000003",
        "module_key": "factory",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 37,
    },
    {
        "id": "320000c1-0000-0000-0000-000000000004",
        "module_key": "feed",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 76,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000004",
        "module_key": "feed",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 77,
    },
    {
        "id": "320000c1-0000-0000-0000-000000000005",
        "module_key": "medicine",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 56,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000005",
        "module_key": "medicine",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 57,
    },
    {
        "id": "320000c1-0000-0000-0000-000000000006",
        "module_key": "slaughter",
        "key": "stock-takes",
        "name": "Инвентаризация",
        "path": "stock-takes",
        "description": "Инвентаризация и сверка остатков",
        "permission_prefix": "stock_take",
        "api_module_key": "inventory",
        "sort_order": 46,
    },
    {
        "id": "320000d1-0000-0000-0000-000000000006",
        "module_key": "slaughter",
        "key": "reorder-levels",
        "name": "Точки заказа",
        "path": "reorder-levels",
        "description": "Минимальные запасы и точки заказа",
        "permission_prefix": "stock_reorder_level",
        "api_module_key": "inventory",
        "sort_order": 47,
    },
)


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


def _strip_codes(existing: object | None, removals: tuple[str, ...]) -> list[str]:
    current = _normalize_codes(existing)
    removal = {code.strip().lower() for code in removals}
    return [code for code in current if code not in removal]


def upgrade() -> None:
    bind = op.get_bind()

    for module_key in AFFECTED_MODULES:
        for resource_key in DROP_RESOURCE_KEYS:
            bind.execute(
                workspace_resources_table.delete().where(
                    workspace_resources_table.c.module_key == module_key,
                    workspace_resources_table.c.key == resource_key,
                )
            )

    for module_key in AFFECTED_MODULES:
        row = bind.execute(
            sa.select(
                department_modules_table.c.key,
                department_modules_table.c.implicit_read_permissions,
            ).where(department_modules_table.c.key == module_key)
        ).mappings().first()
        if row is None:
            continue
        next_codes = _strip_codes(row.get("implicit_read_permissions"), REMOVED_IMPLICIT_PERMISSIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == module_key)
            .values(implicit_read_permissions=next_codes)
        )

    resource = FACTORY_FEED_CONSUMPTION_RESOURCE
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
        merged = _merge_codes(row.get("implicit_read_permissions"), FACTORY_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "factory")
            .values(implicit_read_permissions=merged)
        )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        workspace_resources_table.delete().where(
            workspace_resources_table.c.module_key == "factory",
            workspace_resources_table.c.key == "feed-consumptions",
        )
    )
    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "factory")
    ).mappings().first()
    if row is not None:
        next_codes = _strip_codes(row.get("implicit_read_permissions"), FACTORY_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "factory")
            .values(implicit_read_permissions=next_codes)
        )

    for resource in DOWNGRADE_STOCK_OPS_RESOURCES:
        existing_id = bind.execute(
            sa.select(workspace_resources_table.c.id).where(
                workspace_resources_table.c.module_key == resource["module_key"],
                workspace_resources_table.c.key == resource["key"],
            )
        ).scalar()
        if existing_id is not None:
            continue
        bind.execute(
            workspace_resources_table.insert().values(
                id=UUID(str(resource["id"])),
                module_key=resource["module_key"],
                key=resource["key"],
                name=resource["name"],
                path=resource["path"],
                description=resource["description"],
                permission_prefix=resource["permission_prefix"],
                api_module_key=resource["api_module_key"],
                sort_order=int(resource["sort_order"]),
                is_head_visible=True,
                is_active=True,
            )
        )

    for module_key in AFFECTED_MODULES:
        row = bind.execute(
            sa.select(
                department_modules_table.c.key,
                department_modules_table.c.implicit_read_permissions,
            ).where(department_modules_table.c.key == module_key)
        ).mappings().first()
        if row is None:
            continue
        merged = _merge_codes(row.get("implicit_read_permissions"), REMOVED_IMPLICIT_PERMISSIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == module_key)
            .values(implicit_read_permissions=merged)
        )
