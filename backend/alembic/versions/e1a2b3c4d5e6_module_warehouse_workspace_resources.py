"""module warehouse workspace resources

Revision ID: e1a2b3c4d5e6
Revises: d9f0a1b2c3d4
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "e1a2b3c4d5e6"
down_revision = "d9f0a1b2c3d4"
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
    sa.column("id", sa.UUID()),
    sa.column("key", sa.String()),
    sa.column("implicit_read_permissions", sa.JSON()),
)

MODULE_WAREHOUSE_RESOURCES: tuple[dict[str, object], ...] = (
    {
        "id": "32000000-0000-0000-0000-000000000181",
        "module_key": "egg",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 56,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000182",
        "module_key": "incubation",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 38,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000183",
        "module_key": "factory",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 36,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000184",
        "module_key": "feed",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 76,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000185",
        "module_key": "medicine",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 56,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000186",
        "module_key": "slaughter",
        "key": "warehouses",
        "name": "Склады",
        "path": "warehouses",
        "description": "Склады и складские зоны подразделений",
        "permission_prefix": "warehouse",
        "api_module_key": "core",
        "sort_order": 46,
        "is_head_visible": True,
        "is_active": True,
    },
)

MODULE_WAREHOUSE_RESOURCE_KEYS = tuple(
    (str(resource["module_key"]), str(resource["key"])) for resource in MODULE_WAREHOUSE_RESOURCES
)
TARGET_MODULE_KEYS = tuple(str(resource["module_key"]) for resource in MODULE_WAREHOUSE_RESOURCES)
WAREHOUSE_READ_PERMISSION = "warehouse.read"


def _normalize_permission_codes(raw_value: object) -> list[str]:
    if raw_value is None:
        return []

    parsed_value = raw_value
    if isinstance(raw_value, str):
        try:
            parsed_value = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed_value = [raw_value]

    if not isinstance(parsed_value, list):
        return []

    normalized_codes: list[str] = []
    seen_codes: set[str] = set()
    for item in parsed_value:
        code = str(item or "").strip().lower()
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        normalized_codes.append(code)
    return normalized_codes


def _upsert_workspace_resource(bind, resource: dict[str, object]) -> None:
    existing_id = bind.execute(
        sa.select(workspace_resources_table.c.id).where(
            workspace_resources_table.c.module_key == resource["module_key"],
            workspace_resources_table.c.key == resource["key"],
        )
    ).scalar_one_or_none()

    payload = {
        "module_key": resource["module_key"],
        "key": resource["key"],
        "name": resource["name"],
        "path": resource["path"],
        "description": resource["description"],
        "permission_prefix": resource["permission_prefix"],
        "api_module_key": resource["api_module_key"],
        "sort_order": resource["sort_order"],
        "is_head_visible": resource["is_head_visible"],
        "is_active": resource["is_active"],
    }

    if existing_id is None:
        bind.execute(
            workspace_resources_table.insert().values(
                id=UUID(str(resource["id"])),
                **payload,
            )
        )
        return

    bind.execute(
        workspace_resources_table.update()
        .where(workspace_resources_table.c.id == existing_id)
        .values(**payload)
    )


def _delete_workspace_resources(bind) -> None:
    for module_key, resource_key in MODULE_WAREHOUSE_RESOURCE_KEYS:
        bind.execute(
            workspace_resources_table.delete().where(
                workspace_resources_table.c.module_key == module_key,
                workspace_resources_table.c.key == resource_key,
            )
        )


def _update_module_read_permissions(bind, *, add_permission: bool) -> None:
    rows = bind.execute(
        sa.select(
            department_modules_table.c.id,
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key.in_(TARGET_MODULE_KEYS))
    ).mappings()

    for row in rows:
        permission_codes = _normalize_permission_codes(row.get("implicit_read_permissions"))
        has_permission = WAREHOUSE_READ_PERMISSION in permission_codes

        if add_permission and not has_permission:
            permission_codes.append(WAREHOUSE_READ_PERMISSION)
        elif not add_permission and has_permission:
            permission_codes = [
                code for code in permission_codes if code != WAREHOUSE_READ_PERMISSION
            ]
        else:
            continue

        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.id == row["id"])
            .values(implicit_read_permissions=permission_codes)
        )


def upgrade() -> None:
    bind = op.get_bind()

    for resource in MODULE_WAREHOUSE_RESOURCES:
        _upsert_workspace_resource(bind, resource)

    _update_module_read_permissions(bind, add_permission=True)


def downgrade() -> None:
    bind = op.get_bind()

    _delete_workspace_resources(bind)
    _update_module_read_permissions(bind, add_permission=False)
