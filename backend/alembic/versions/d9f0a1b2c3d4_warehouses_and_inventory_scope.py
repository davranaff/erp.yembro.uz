"""warehouses and inventory scope

Revision ID: d9f0a1b2c3d4
Revises: c7d8e9f0a1b2
Create Date: 2026-04-07 00:00:00.000000
"""

from __future__ import annotations

import re
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic import op
import sqlalchemy as sa


revision = "d9f0a1b2c3d4"
down_revision = "c7d8e9f0a1b2"
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


warehouses_table = sa.table(
    "warehouses",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("department_id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("code", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("is_default", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
)


WAREHOUSE_RESOURCE = {
    "id": "32000000-0000-0000-0000-000000000161",
    "module_key": "core",
    "key": "warehouses",
    "name": "Склады",
    "path": "warehouses",
    "description": "Склады и складские зоны подразделений",
    "permission_prefix": "warehouse",
    "api_module_key": None,
    "sort_order": 25,
    "is_head_visible": False,
    "is_active": True,
}


def _normalize_warehouse_code_seed(raw_value: object | None) -> str:
    candidate = str(raw_value or "").strip().upper()
    normalized = re.sub(r"[^A-Z0-9]+", "-", candidate).strip("-")
    return normalized or "WH"


def _build_default_warehouse_rows(bind) -> list[dict[str, object]]:
    departments = bind.execute(
        sa.text(
            """
            SELECT id, organization_id, name, code, is_active
            FROM departments
            ORDER BY organization_id, name, id
            """
        )
    ).mappings()

    code_counters: dict[tuple[str, str], int] = {}
    rows: list[dict[str, object]] = []
    for department in departments:
        organization_id = str(department["organization_id"])
        department_id = str(department["id"])
        base_seed = _normalize_warehouse_code_seed(department.get("code") or department.get("name"))
        base_code = (f"{base_seed}-WH"[:80]).rstrip("-") or "WH"
        counter_key = (organization_id, base_code)
        next_counter = code_counters.get(counter_key, 0) + 1
        code_counters[counter_key] = next_counter
        if next_counter == 1:
            code = base_code
        else:
            suffix = f"-{next_counter}"
            allowed_base_length = max(1, 80 - len(suffix))
            code = f"{base_code[:allowed_base_length].rstrip('-')}{suffix}"

        rows.append(
            {
                "id": uuid5(NAMESPACE_URL, f"warehouse|{department_id}|default"),
                "organization_id": UUID(organization_id),
                "department_id": UUID(department_id),
                "name": "Asosiy ombor",
                "code": code,
                "description": f"Default warehouse for {department.get('name') or 'department'}",
                "is_default": True,
                "is_active": bool(department.get("is_active", True)),
            }
        )

    return rows


def _upsert_workspace_resource(bind) -> None:
    existing_id = bind.execute(
        sa.select(workspace_resources_table.c.id).where(
            workspace_resources_table.c.module_key == WAREHOUSE_RESOURCE["module_key"],
            workspace_resources_table.c.key == WAREHOUSE_RESOURCE["key"],
        )
    ).scalar_one_or_none()

    payload = {
        "module_key": WAREHOUSE_RESOURCE["module_key"],
        "key": WAREHOUSE_RESOURCE["key"],
        "name": WAREHOUSE_RESOURCE["name"],
        "path": WAREHOUSE_RESOURCE["path"],
        "description": WAREHOUSE_RESOURCE["description"],
        "permission_prefix": WAREHOUSE_RESOURCE["permission_prefix"],
        "api_module_key": WAREHOUSE_RESOURCE["api_module_key"],
        "sort_order": WAREHOUSE_RESOURCE["sort_order"],
        "is_head_visible": WAREHOUSE_RESOURCE["is_head_visible"],
        "is_active": WAREHOUSE_RESOURCE["is_active"],
    }
    if existing_id is None:
        bind.execute(
            workspace_resources_table.insert().values(
                id=UUID(str(WAREHOUSE_RESOURCE["id"])),
                **payload,
            )
        )
        return

    bind.execute(
        workspace_resources_table.update()
        .where(workspace_resources_table.c.id == existing_id)
        .values(**payload)
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "warehouses",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_warehouse_org_code"),
        sa.UniqueConstraint("organization_id", "department_id", "name", name="uq_warehouse_org_department_name"),
    )
    op.create_index(op.f("ix_warehouses_organization_id"), "warehouses", ["organization_id"], unique=False)
    op.create_index(op.f("ix_warehouses_department_id"), "warehouses", ["department_id"], unique=False)
    op.create_index(op.f("ix_warehouses_name"), "warehouses", ["name"], unique=False)
    op.create_index(op.f("ix_warehouses_code"), "warehouses", ["code"], unique=False)

    op.add_column("stock_movements", sa.Column("warehouse_id", sa.UUID(), nullable=True))
    op.add_column("stock_movements", sa.Column("counterparty_warehouse_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_stock_movements_warehouse_id"), "stock_movements", ["warehouse_id"], unique=False)
    op.create_index(
        op.f("ix_stock_movements_counterparty_warehouse_id"),
        "stock_movements",
        ["counterparty_warehouse_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_stock_movements_warehouse_id",
        "stock_movements",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_stock_movements_counterparty_warehouse_id",
        "stock_movements",
        "warehouses",
        ["counterparty_warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )

    warehouse_rows = _build_default_warehouse_rows(bind)
    if warehouse_rows:
        op.bulk_insert(warehouses_table, warehouse_rows)

    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET warehouse_id = w.id
            FROM warehouses AS w
            WHERE sm.department_id = w.department_id
              AND w.is_default = true
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE stock_movements AS sm
            SET counterparty_warehouse_id = w.id
            FROM warehouses AS w
            WHERE sm.counterparty_department_id = w.department_id
              AND w.is_default = true
            """
        )
    )

    op.alter_column("stock_movements", "warehouse_id", nullable=False)
    op.drop_constraint("uq_stock_movement_reference_kind_scope", "stock_movements", type_="unique")
    op.create_unique_constraint(
        "uq_stock_movement_reference_kind_scope",
        "stock_movements",
        ["reference_table", "reference_id", "movement_kind", "warehouse_id", "item_type", "item_key"],
    )

    _upsert_workspace_resource(bind)


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        workspace_resources_table.delete().where(
            workspace_resources_table.c.module_key == WAREHOUSE_RESOURCE["module_key"],
            workspace_resources_table.c.key == WAREHOUSE_RESOURCE["key"],
        )
    )

    op.drop_constraint("uq_stock_movement_reference_kind_scope", "stock_movements", type_="unique")
    op.create_unique_constraint(
        "uq_stock_movement_reference_kind_scope",
        "stock_movements",
        ["reference_table", "reference_id", "movement_kind", "department_id", "item_type", "item_key"],
    )
    op.drop_constraint("fk_stock_movements_counterparty_warehouse_id", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_warehouse_id", "stock_movements", type_="foreignkey")
    op.drop_index(op.f("ix_stock_movements_counterparty_warehouse_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_warehouse_id"), table_name="stock_movements")
    op.drop_column("stock_movements", "counterparty_warehouse_id")
    op.drop_column("stock_movements", "warehouse_id")

    op.drop_index(op.f("ix_warehouses_code"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_name"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_department_id"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_organization_id"), table_name="warehouses")
    op.drop_table("warehouses")
