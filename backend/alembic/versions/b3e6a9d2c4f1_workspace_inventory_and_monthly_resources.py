"""workspace inventory and monthly resources

Revision ID: b3e6a9d2c4f1
Revises: a1f4b7c8d9e0
Create Date: 2026-03-30 00:00:00.000000
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "b3e6a9d2c4f1"
down_revision = "a1f4b7c8d9e0"
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


NEW_WORKSPACE_RESOURCES: tuple[dict[str, object], ...] = (
    {
        "id": "32000000-0000-0000-0000-000000000071",
        "module_key": "egg",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 55,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000072",
        "module_key": "incubation",
        "key": "monthly-analytics",
        "name": "Месячная аналитика",
        "path": "monthly-analytics",
        "description": "Помесячные показатели инкубации",
        "permission_prefix": "incubation_monthly_analytics",
        "api_module_key": None,
        "sort_order": 35,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000073",
        "module_key": "incubation",
        "key": "factory-monthly-analytics",
        "name": "Аналитика фабрики",
        "path": "factory-monthly-analytics",
        "description": "Помесячные показатели фабрики",
        "permission_prefix": "factory_monthly_analytics",
        "api_module_key": None,
        "sort_order": 36,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000074",
        "module_key": "incubation",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 37,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000075",
        "module_key": "factory",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 35,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000076",
        "module_key": "feed",
        "key": "types",
        "name": "Типы корма",
        "path": "types",
        "description": "Справочник типов готового корма",
        "permission_prefix": "feed_type",
        "api_module_key": None,
        "sort_order": 5,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000077",
        "module_key": "feed",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 75,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000078",
        "module_key": "medicine",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 55,
        "is_head_visible": False,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000079",
        "module_key": "slaughter",
        "key": "stock-movements",
        "name": "Движения остатков",
        "path": "movements",
        "description": "Движения склада и инвентарный журнал",
        "permission_prefix": "stock_movement",
        "api_module_key": "inventory",
        "sort_order": 45,
        "is_head_visible": False,
        "is_active": True,
    },
)


IMPLICIT_PERMISSION_ADDITIONS: dict[str, tuple[str, ...]] = {
    "egg": ("stock_movement.read",),
    "incubation": (
        "incubation_monthly_analytics.read",
        "factory_monthly_analytics.read",
        "stock_movement.read",
    ),
    "factory": ("stock_movement.read",),
    "feed": ("feed_type.read", "stock_movement.read"),
    "medicine": ("stock_movement.read",),
    "slaughter": ("stock_movement.read",),
}


def _uuid(value: str) -> UUID:
    return UUID(value)


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

    existing_ids_by_pair = {
        (str(row["module_key"]).strip().lower(), str(row["key"]).strip().lower()): row["id"]
        for row in bind.execute(
            sa.select(
                workspace_resources_table.c.id,
                workspace_resources_table.c.module_key,
                workspace_resources_table.c.key,
            )
        ).mappings()
    }

    for resource in NEW_WORKSPACE_RESOURCES:
        module_key = str(resource["module_key"]).strip().lower()
        resource_key = str(resource["key"]).strip().lower()
        payload = {
            "module_key": module_key,
            "key": resource_key,
            "name": resource["name"],
            "path": resource["path"],
            "description": resource["description"],
            "permission_prefix": resource["permission_prefix"],
            "api_module_key": resource["api_module_key"],
            "sort_order": int(resource["sort_order"]),
            "is_head_visible": bool(resource["is_head_visible"]),
            "is_active": bool(resource["is_active"]),
        }
        pair = (module_key, resource_key)

        existing_id = existing_ids_by_pair.get(pair)
        if existing_id is not None:
            bind.execute(
                workspace_resources_table.update()
                .where(workspace_resources_table.c.id == existing_id)
                .values(**payload)
            )
            continue

        bind.execute(
            workspace_resources_table.insert().values(
                id=_uuid(str(resource["id"])),
                **payload,
            )
        )

    for module_key, additions in IMPLICIT_PERMISSION_ADDITIONS.items():
        row = bind.execute(
            sa.select(
                department_modules_table.c.key,
                department_modules_table.c.implicit_read_permissions,
            ).where(department_modules_table.c.key == module_key)
        ).mappings().first()

        if row is None:
            continue

        merged_codes = _merge_codes(row.get("implicit_read_permissions"), additions)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == module_key)
            .values(implicit_read_permissions=merged_codes)
        )


def downgrade() -> None:
    bind = op.get_bind()

    for resource in NEW_WORKSPACE_RESOURCES:
        bind.execute(
            workspace_resources_table.delete().where(
                workspace_resources_table.c.module_key == str(resource["module_key"]).strip().lower(),
                workspace_resources_table.c.key == str(resource["key"]).strip().lower(),
            )
        )

    for module_key, additions in IMPLICIT_PERMISSION_ADDITIONS.items():
        row = bind.execute(
            sa.select(
                department_modules_table.c.key,
                department_modules_table.c.implicit_read_permissions,
            ).where(department_modules_table.c.key == module_key)
        ).mappings().first()

        if row is None:
            continue

        current_codes = _normalize_codes(row.get("implicit_read_permissions"))
        removal_codes = {code.strip().lower() for code in additions}
        next_codes = [code for code in current_codes if code not in removal_codes]

        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == module_key)
            .values(implicit_read_permissions=next_codes)
        )
