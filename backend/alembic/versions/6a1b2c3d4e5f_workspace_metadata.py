"""workspace metadata and currency defaults

Revision ID: 6a1b2c3d4e5f
Revises: 5c9d4b1e2a3f
Create Date: 2026-03-25 20:10:00.000000
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "6a1b2c3d4e5f"
down_revision = "5c9d4b1e2a3f"
branch_labels = None
depends_on = None


CURRENCY_DEFAULT_TABLES = (
    "cash_accounts",
    "cash_transactions",
    "expenses",
    "egg_monthly_analytics",
    "egg_shipments",
    "chick_arrivals",
    "chick_shipments",
    "feed_arrivals",
    "feed_raw_arrivals",
    "feed_product_shipments",
    "medicine_arrivals",
    "medicine_batches",
    "slaughter_arrivals",
    "slaughter_semi_product_shipments",
)


department_modules_table = sa.table(
    "department_modules",
    sa.column("id", sa.UUID()),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("icon", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_department_assignable", sa.Boolean()),
    sa.column("analytics_section_key", sa.String()),
    sa.column("implicit_read_permissions", sa.JSON()),
    sa.column("analytics_read_permissions", sa.JSON()),
    sa.column("is_active", sa.Boolean()),
)

workspace_resources_table = sa.table(
    "workspace_resources",
    sa.column("id", sa.UUID()),
    sa.column("module_key", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("path", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("permission_prefix", sa.String()),
    sa.column("api_module_key", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_head_visible", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
)

organizations_table = sa.table(
    "organizations",
    sa.column("id", sa.UUID()),
)

permissions_table = sa.table(
    "permissions",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("resource", sa.String()),
    sa.column("action", sa.String()),
    sa.column("description", sa.String()),
    sa.column("is_active", sa.Boolean()),
)

roles_table = sa.table(
    "roles",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("slug", sa.String()),
)

role_permissions_table = sa.table(
    "role_permissions",
    sa.column("role_id", sa.UUID()),
    sa.column("permission_id", sa.UUID()),
)


def _split_key_value(line: str) -> tuple[str, str]:
    key, separator, value = line.partition(":")
    if not separator:
        raise ValueError(f"Invalid fixture line: {line!r}")
    return key.strip(), value.strip()


def _parse_scalar(raw_value: str) -> object:
    if raw_value in {"null", "~"}:
        return None
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    if (raw_value.startswith('"') and raw_value.endswith('"')) or (
        raw_value.startswith("'") and raw_value.endswith("'")
    ):
        return raw_value[1:-1]
    if raw_value.lstrip("-").isdigit():
        return int(raw_value)
    return raw_value


def _parse_fixture_file(path: Path) -> dict[str, list[dict[str, object]]]:
    parsed: dict[str, list[dict[str, object]]] = {}
    current_section: str | None = None
    current_item: dict[str, object] | None = None

    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if raw_line.startswith("  - "):
            if current_section is None:
                raise ValueError(f"{path}:{lineno}: item without section")
            current_item = {}
            parsed[current_section].append(current_item)
            key, raw_value = _split_key_value(raw_line[4:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("- "):
            if current_section is None:
                raise ValueError(f"{path}:{lineno}: item without section")
            current_item = {}
            parsed[current_section].append(current_item)
            key, raw_value = _split_key_value(raw_line[2:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("    "):
            if current_item is None:
                raise ValueError(f"{path}:{lineno}: attribute without item")
            key, raw_value = _split_key_value(raw_line[4:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("  "):
            if current_item is None:
                raise ValueError(f"{path}:{lineno}: attribute without item")
            key, raw_value = _split_key_value(raw_line[2:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if not raw_line.startswith(" "):
            if not stripped.endswith(":"):
                raise ValueError(f"{path}:{lineno}: expected section header")
            current_section = stripped[:-1]
            parsed.setdefault(current_section, [])
            current_item = None
            continue

        raise ValueError(f"{path}:{lineno}: unsupported indentation")

    return parsed


def _fixture_rows(section: str) -> list[dict[str, object]]:
    fixture_path = Path(__file__).resolve().parents[2] / "fixtures" / "core.yaml"
    parsed = _parse_fixture_file(fixture_path)
    return parsed.get(section, [])


def _json_value(raw_value: object | None) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return []
        return list(json.loads(candidate))
    if isinstance(raw_value, (list, tuple, set)):
        return [str(item) for item in raw_value]
    return [str(raw_value)]


def _uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _seed_department_modules() -> None:
    bind = op.get_bind()
    existing_by_key = {
        str(row["key"]).strip().lower(): row["id"]
        for row in bind.execute(
            sa.select(department_modules_table.c.id, department_modules_table.c.key)
        ).mappings()
    }

    for row in _fixture_rows("department_modules"):
        key = str(row["key"]).strip().lower()
        payload = {
            "name": row.get("name"),
            "description": row.get("description"),
            "icon": row.get("icon"),
            "sort_order": int(row.get("sort_order", 100)),
            "is_department_assignable": bool(row.get("is_department_assignable", True)),
            "analytics_section_key": row.get("analytics_section_key"),
            "implicit_read_permissions": _json_value(row.get("implicit_read_permissions")),
            "analytics_read_permissions": _json_value(row.get("analytics_read_permissions")),
            "is_active": bool(row.get("is_active", True)),
        }
        if key in existing_by_key:
            bind.execute(
                department_modules_table.update()
                .where(department_modules_table.c.key == key)
                .values(**payload)
            )
            continue

        bind.execute(
            department_modules_table.insert().values(
                id=_uuid(row["id"]),
                key=key,
                **payload,
            )
        )


def _seed_workspace_resources() -> None:
    bind = op.get_bind()
    existing_pairs = {
        (str(row["module_key"]).strip().lower(), str(row["key"]).strip().lower())
        for row in bind.execute(
            sa.select(workspace_resources_table.c.module_key, workspace_resources_table.c.key)
        ).mappings()
    }

    for row in _fixture_rows("workspace_resources"):
        module_key = str(row["module_key"]).strip().lower()
        resource_key = str(row["key"]).strip().lower()
        payload = {
            "name": row.get("name"),
            "path": row.get("path"),
            "description": row.get("description"),
            "permission_prefix": row.get("permission_prefix"),
            "api_module_key": row.get("api_module_key"),
            "sort_order": int(row.get("sort_order", 100)),
            "is_head_visible": bool(row.get("is_head_visible", False)),
            "is_active": bool(row.get("is_active", True)),
        }
        if (module_key, resource_key) in existing_pairs:
            bind.execute(
                workspace_resources_table.update()
                .where(workspace_resources_table.c.module_key == module_key)
                .where(workspace_resources_table.c.key == resource_key)
                .values(**payload)
            )
            continue

        bind.execute(
            workspace_resources_table.insert().values(
                id=_uuid(row["id"]),
                module_key=module_key,
                key=resource_key,
                **payload,
            )
        )


def _seed_dashboard_permission() -> None:
    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())
    permission_ids_by_org: dict[UUID, UUID] = {}

    for organization in organizations:
        organization_id = organization["id"]
        existing_permission = bind.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.organization_id == organization_id,
                permissions_table.c.code == "dashboard.read",
            )
        ).scalar_one_or_none()
        if existing_permission is None:
            existing_permission = uuid4()
            bind.execute(
                permissions_table.insert().values(
                    id=existing_permission,
                    organization_id=organization_id,
                    code="dashboard.read",
                    resource="dashboard",
                    action="read",
                    description="View dashboard analytics and overview",
                    is_active=True,
                )
            )
        permission_ids_by_org[organization_id] = existing_permission

    admin_roles = list(
        bind.execute(
            sa.select(roles_table.c.id, roles_table.c.organization_id).where(
                roles_table.c.slug.in_(("admin", "manager"))
            )
        ).mappings()
    )
    for role in admin_roles:
        permission_id = permission_ids_by_org.get(role["organization_id"])
        if permission_id is None:
            continue
        existing_assignment = bind.execute(
            sa.select(role_permissions_table.c.role_id).where(
                role_permissions_table.c.role_id == role["id"],
                role_permissions_table.c.permission_id == permission_id,
            )
        ).scalar_one_or_none()
        if existing_assignment is not None:
            continue
        bind.execute(
            role_permissions_table.insert().values(
                role_id=role["id"],
                permission_id=permission_id,
            )
        )


def upgrade() -> None:
    op.add_column(
        "department_modules",
        sa.Column(
            "is_department_assignable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "department_modules",
        sa.Column("analytics_section_key", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "department_modules",
        sa.Column(
            "implicit_read_permissions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        "department_modules",
        sa.Column(
            "analytics_read_permissions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )

    op.create_table(
        "workspace_resources",
        sa.Column("module_key", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("path", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permission_prefix", sa.String(length=96), nullable=False),
        sa.Column("api_module_key", sa.String(length=64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_head_visible", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["module_key"], ["department_modules.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("module_key", "key", name="uq_workspace_resource_module_key"),
    )
    op.create_index(op.f("ix_workspace_resources_id"), "workspace_resources", ["id"], unique=False)
    op.create_index(
        op.f("ix_workspace_resources_module_key"),
        "workspace_resources",
        ["module_key"],
        unique=False,
    )
    op.create_index(op.f("ix_workspace_resources_key"), "workspace_resources", ["key"], unique=False)
    op.create_index(
        op.f("ix_workspace_resources_permission_prefix"),
        "workspace_resources",
        ["permission_prefix"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_resources_api_module_key"),
        "workspace_resources",
        ["api_module_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workspace_resources_sort_order"),
        "workspace_resources",
        ["sort_order"],
        unique=False,
    )

    _seed_department_modules()
    _seed_workspace_resources()
    _seed_dashboard_permission()

    for table_name in CURRENCY_DEFAULT_TABLES:
        op.alter_column(table_name, "currency", server_default=None)


def downgrade() -> None:
    for table_name in CURRENCY_DEFAULT_TABLES:
        op.alter_column(table_name, "currency", server_default="UZS")

    op.drop_index(op.f("ix_workspace_resources_sort_order"), table_name="workspace_resources")
    op.drop_index(op.f("ix_workspace_resources_api_module_key"), table_name="workspace_resources")
    op.drop_index(op.f("ix_workspace_resources_permission_prefix"), table_name="workspace_resources")
    op.drop_index(op.f("ix_workspace_resources_key"), table_name="workspace_resources")
    op.drop_index(op.f("ix_workspace_resources_module_key"), table_name="workspace_resources")
    op.drop_index(op.f("ix_workspace_resources_id"), table_name="workspace_resources")
    op.drop_table("workspace_resources")

    op.drop_column("department_modules", "analytics_read_permissions")
    op.drop_column("department_modules", "implicit_read_permissions")
    op.drop_column("department_modules", "analytics_section_key")
    op.drop_column("department_modules", "is_department_assignable")
