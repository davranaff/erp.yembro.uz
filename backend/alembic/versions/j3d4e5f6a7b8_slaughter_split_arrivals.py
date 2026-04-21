"""slaughter: split arrivals out of processings + rename menu items

Revision ID: j3d4e5f6a7b8
Revises: i2c3d4e5f6a7
Create Date: 2026-04-20
"""

from __future__ import annotations

import json
from uuid import UUID

from alembic import op
import sqlalchemy as sa


revision = "j3d4e5f6a7b8"
down_revision = "i2c3d4e5f6a7"
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


SLAUGHTER_ARRIVALS_RESOURCE: dict[str, object] = {
    "id": "32000000-0000-0000-0000-000000000301",
    "module_key": "slaughter",
    "key": "arrivals",
    "name": "Партии (приход)",
    "path": "arrivals",
    "description": "Приход партий живой птицы — из фабрики или от поставщика",
    "permission_prefix": "slaughter_arrival",
    "api_module_key": "slaughter",
    "sort_order": 5,
    "is_head_visible": True,
    "is_active": True,
}

SLAUGHTER_IMPLICIT_ADDITIONS: tuple[str, ...] = ("slaughter_arrival.read",)


RENAME_RESOURCES: tuple[tuple[str, str, str], ...] = (
    ("slaughter", "processings", "Убой"),
    ("slaughter", "semi-products", "Разделка"),
    ("slaughter", "semi-product-shipments", "Отгрузки"),
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

    # 1. Create slaughter_arrivals table
    op.create_table(
        "slaughter_arrivals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("factory_shipment_id", sa.UUID(), nullable=True),
        sa.Column("supplier_client_id", sa.UUID(), nullable=True),
        sa.Column("poultry_type_id", sa.UUID(), nullable=True),
        sa.Column("arrived_on", sa.Date(), nullable=False),
        sa.Column("birds_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("arrival_total_weight_kg", sa.Numeric(16, 3), nullable=True),
        sa.Column("arrival_unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("arrival_currency", sa.String(8), nullable=True),
        sa.Column("arrival_invoice_no", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["factory_shipment_id"], ["factory_shipments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["poultry_type_id"], ["poultry_types.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "source_type IN ('factory', 'external')",
            name="ck_slaughter_arrival_source_type",
        ),
        sa.CheckConstraint(
            "(source_type = 'factory' AND factory_shipment_id IS NOT NULL AND supplier_client_id IS NULL) OR "
            "(source_type = 'external' AND supplier_client_id IS NOT NULL AND factory_shipment_id IS NULL)",
            name="ck_slaughter_arrival_source_exactly_one",
        ),
        sa.CheckConstraint("birds_received >= 0", name="ck_slaughter_arrival_birds_received_non_negative"),
        sa.CheckConstraint(
            "arrival_total_weight_kg IS NULL OR arrival_total_weight_kg >= 0",
            name="ck_slaughter_arrival_total_weight_non_negative",
        ),
        sa.CheckConstraint(
            "arrival_unit_price IS NULL OR arrival_unit_price >= 0",
            name="ck_slaughter_arrival_unit_price_non_negative",
        ),
    )
    op.create_index("ix_slaughter_arrivals_organization_id", "slaughter_arrivals", ["organization_id"])
    op.create_index("ix_slaughter_arrivals_department_id", "slaughter_arrivals", ["department_id"])
    op.create_index("ix_slaughter_arrivals_source_type", "slaughter_arrivals", ["source_type"])
    op.create_index("ix_slaughter_arrivals_factory_shipment_id", "slaughter_arrivals", ["factory_shipment_id"])
    op.create_index("ix_slaughter_arrivals_supplier_client_id", "slaughter_arrivals", ["supplier_client_id"])
    op.create_index("ix_slaughter_arrivals_poultry_type_id", "slaughter_arrivals", ["poultry_type_id"])
    op.create_index("ix_slaughter_arrivals_arrived_on", "slaughter_arrivals", ["arrived_on"])

    # 2. Backfill arrivals from existing processings (use processing.id as arrival.id → 1:1)
    bind.execute(
        sa.text(
            """
            INSERT INTO slaughter_arrivals (
                id, organization_id, department_id, source_type,
                factory_shipment_id, supplier_client_id, poultry_type_id,
                arrived_on, birds_received, arrival_total_weight_kg,
                arrival_unit_price, arrival_currency, arrival_invoice_no,
                note, created_at, updated_at
            )
            SELECT
                id, organization_id, department_id, source_type,
                factory_shipment_id, supplier_client_id, poultry_type_id,
                arrived_on, birds_received, arrival_total_weight_kg,
                arrival_unit_price, arrival_currency, arrival_invoice_no,
                NULL, created_at, updated_at
            FROM slaughter_processings
            """
        )
    )

    # 3. Add arrival_id on processings (nullable first, then set + NOT NULL)
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_id", sa.UUID(), nullable=True),
    )
    bind.execute(sa.text("UPDATE slaughter_processings SET arrival_id = id"))
    op.alter_column("slaughter_processings", "arrival_id", nullable=False)
    op.create_foreign_key(
        "fk_slaughter_processings_arrival_id",
        "slaughter_processings",
        "slaughter_arrivals",
        ["arrival_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_slaughter_processings_arrival_id",
        "slaughter_processings",
        ["arrival_id"],
    )

    # 4. Drop now-obsolete constraints from processings
    for constraint in (
        "ck_slaughter_processing_source_type",
        "ck_slaughter_processing_source_exactly_one",
        "ck_slaughter_processing_birds_received_non_negative",
        "ck_slaughter_processing_processed_not_exceed_received",
        "ck_slaughter_processing_arrival_total_weight_non_negative",
        "ck_slaughter_processing_arrival_unit_price_non_negative",
    ):
        bind.execute(sa.text(f"ALTER TABLE slaughter_processings DROP CONSTRAINT IF EXISTS {constraint}"))

    # 5. Drop arrival + source columns from processings
    for index_name in (
        "ix_slaughter_processings_source_type",
        "ix_slaughter_processings_factory_shipment_id",
        "ix_slaughter_processings_supplier_client_id",
        "ix_slaughter_processings_poultry_type_id",
        "ix_slaughter_processings_arrived_on",
    ):
        bind.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))

    for column in (
        "source_type",
        "factory_shipment_id",
        "supplier_client_id",
        "poultry_type_id",
        "arrived_on",
        "birds_received",
        "arrival_total_weight_kg",
        "arrival_unit_price",
        "arrival_currency",
        "arrival_invoice_no",
    ):
        bind.execute(sa.text(f"ALTER TABLE slaughter_processings DROP COLUMN IF EXISTS {column}"))

    # 6. Workspace resource for new arrivals menu
    resource = SLAUGHTER_ARRIVALS_RESOURCE
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

    # 7. Rename existing slaughter menu labels to match new flow
    for module_key, resource_key, new_name in RENAME_RESOURCES:
        bind.execute(
            workspace_resources_table.update()
            .where(
                workspace_resources_table.c.module_key == module_key,
                workspace_resources_table.c.key == resource_key,
            )
            .values(name=new_name)
        )

    # 8. Add slaughter_arrival.read to slaughter implicit_read_permissions
    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "slaughter")
    ).mappings().first()
    if row is not None:
        merged = _merge_codes(row.get("implicit_read_permissions"), SLAUGHTER_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "slaughter")
            .values(implicit_read_permissions=merged)
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Revert implicit permissions
    row = bind.execute(
        sa.select(
            department_modules_table.c.key,
            department_modules_table.c.implicit_read_permissions,
        ).where(department_modules_table.c.key == "slaughter")
    ).mappings().first()
    if row is not None:
        next_codes = _strip_codes(row.get("implicit_read_permissions"), SLAUGHTER_IMPLICIT_ADDITIONS)
        bind.execute(
            department_modules_table.update()
            .where(department_modules_table.c.key == "slaughter")
            .values(implicit_read_permissions=next_codes)
        )

    # Remove arrivals workspace resource
    bind.execute(
        workspace_resources_table.delete().where(
            workspace_resources_table.c.module_key == "slaughter",
            workspace_resources_table.c.key == "arrivals",
        )
    )
    # Restore original names (best-effort)
    for module_key, resource_key, _ in RENAME_RESOURCES:
        default_name = {
            "processings": "Сортировка и разделка",
            "semi-products": "Полуфабрикат и части",
            "semi-product-shipments": "Отгрузки полуфабриката",
        }[resource_key]
        bind.execute(
            workspace_resources_table.update()
            .where(
                workspace_resources_table.c.module_key == module_key,
                workspace_resources_table.c.key == resource_key,
            )
            .values(name=default_name)
        )

    # Re-add arrival columns to processings
    op.add_column(
        "slaughter_processings",
        sa.Column("source_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("factory_shipment_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("supplier_client_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("poultry_type_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrived_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("birds_received", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_total_weight_kg", sa.Numeric(16, 3), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_unit_price", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_currency", sa.String(8), nullable=True),
    )
    op.add_column(
        "slaughter_processings",
        sa.Column("arrival_invoice_no", sa.String(120), nullable=True),
    )

    # Copy back
    bind.execute(
        sa.text(
            """
            UPDATE slaughter_processings sp
            SET source_type = ar.source_type,
                factory_shipment_id = ar.factory_shipment_id,
                supplier_client_id = ar.supplier_client_id,
                poultry_type_id = ar.poultry_type_id,
                arrived_on = ar.arrived_on,
                birds_received = ar.birds_received,
                arrival_total_weight_kg = ar.arrival_total_weight_kg,
                arrival_unit_price = ar.arrival_unit_price,
                arrival_currency = ar.arrival_currency,
                arrival_invoice_no = ar.arrival_invoice_no
            FROM slaughter_arrivals ar
            WHERE sp.arrival_id = ar.id
            """
        )
    )

    op.alter_column("slaughter_processings", "source_type", nullable=False)
    op.alter_column("slaughter_processings", "arrived_on", nullable=False)
    op.alter_column("slaughter_processings", "birds_received", nullable=False)

    # Drop arrival_id FK + column
    op.drop_index("ix_slaughter_processings_arrival_id", table_name="slaughter_processings")
    op.drop_constraint("fk_slaughter_processings_arrival_id", "slaughter_processings", type_="foreignkey")
    op.drop_column("slaughter_processings", "arrival_id")

    # Drop arrivals table
    op.drop_index("ix_slaughter_arrivals_arrived_on", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_poultry_type_id", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_supplier_client_id", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_factory_shipment_id", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_source_type", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_department_id", table_name="slaughter_arrivals")
    op.drop_index("ix_slaughter_arrivals_organization_id", table_name="slaughter_arrivals")
    op.drop_table("slaughter_arrivals")
