"""factory operational tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-17 11:00:00.000000
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

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

FACTORY_RESOURCES = [
    ("factory_flock", "Factory flocks"),
    ("factory_daily_log", "Factory daily logs"),
    ("factory_shipment", "Factory shipments"),
]
ACTIONS = ["read", "create", "write", "delete"]


def upgrade() -> None:
    # --- factory_flocks ---
    op.create_table(
        "factory_flocks",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
        sa.Column("poultry_type_id", sa.UUID(), nullable=True),
        sa.Column("source_client_id", sa.UUID(), nullable=True),
        sa.Column("flock_code", sa.String(120), nullable=False),
        sa.Column("arrived_on", sa.Date(), nullable=False),
        sa.Column("initial_count", sa.Integer(), nullable=False),
        sa.Column("current_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["poultry_type_id"], ["poultry_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_client_id"], ["clients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "flock_code", name="uq_factory_flock_org_code"),
        sa.CheckConstraint("initial_count > 0", name="ck_factory_flock_initial_count_positive"),
        sa.CheckConstraint("current_count >= 0", name="ck_factory_flock_current_count_non_negative"),
        sa.CheckConstraint("current_count <= initial_count", name="ck_factory_flock_current_not_exceed_initial"),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_factory_flock_status_valid"),
    )
    for col in ("id", "organization_id", "department_id", "warehouse_id", "poultry_type_id", "source_client_id", "flock_code", "arrived_on"):
        op.create_index(op.f(f"ix_factory_flocks_{col}"), "factory_flocks", [col], unique=False)

    # --- factory_daily_logs ---
    op.create_table(
        "factory_daily_logs",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("flock_id", sa.UUID(), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("mortality_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("feed_consumed_kg", sa.Numeric(16, 3), server_default="0", nullable=False),
        sa.Column("water_consumed_liters", sa.Numeric(16, 3), nullable=True),
        sa.Column("avg_weight_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("temperature", sa.Numeric(5, 1), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["flock_id"], ["factory_flocks.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("flock_id", "log_date", name="uq_factory_daily_log_flock_date"),
        sa.CheckConstraint("mortality_count >= 0", name="ck_factory_daily_log_mortality_non_negative"),
        sa.CheckConstraint("feed_consumed_kg >= 0", name="ck_factory_daily_log_feed_non_negative"),
        sa.CheckConstraint("water_consumed_liters IS NULL OR water_consumed_liters >= 0", name="ck_factory_daily_log_water_non_negative"),
        sa.CheckConstraint("avg_weight_kg IS NULL OR avg_weight_kg >= 0", name="ck_factory_daily_log_weight_non_negative"),
        sa.CheckConstraint("temperature IS NULL OR (temperature >= -50 AND temperature <= 80)", name="ck_factory_daily_log_temperature_range"),
    )
    for col in ("id", "organization_id", "department_id", "flock_id", "log_date"):
        op.create_index(op.f(f"ix_factory_daily_logs_{col}"), "factory_daily_logs", [col], unique=False)

    # --- factory_shipments ---
    op.create_table(
        "factory_shipments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
        sa.Column("flock_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("shipped_on", sa.Date(), nullable=False),
        sa.Column("birds_count", sa.Integer(), nullable=False),
        sa.Column("total_weight_kg", sa.Numeric(16, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("invoice_no", sa.String(120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["flock_id"], ["factory_flocks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "shipped_on", "client_id", "invoice_no", name="uq_factory_shipment_invoice"),
        sa.CheckConstraint("birds_count > 0", name="ck_factory_shipment_birds_count_positive"),
        sa.CheckConstraint("total_weight_kg > 0", name="ck_factory_shipment_weight_positive"),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_factory_shipment_unit_price_non_negative"),
    )
    for col in ("id", "organization_id", "department_id", "warehouse_id", "flock_id", "client_id", "shipped_on"):
        op.create_index(op.f(f"ix_factory_shipments_{col}"), "factory_shipments", [col], unique=False)

    # --- Seed permissions for admin/manager roles ---
    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())

    permission_ids_by_org_and_code: dict[tuple[object, str], object] = {}
    for org in organizations:
        org_id = org["id"]
        for resource, description in FACTORY_RESOURCES:
            for action in ACTIONS:
                code = f"{resource}.{action}"
                perm_id = uuid4()
                bind.execute(
                    permissions_table.insert().values(
                        id=perm_id,
                        organization_id=org_id,
                        code=code,
                        resource=resource,
                        action=action,
                        description=f"{action.capitalize()} {description}",
                        is_active=True,
                    )
                )
                permission_ids_by_org_and_code[(org_id, code)] = perm_id

    admin_roles = list(
        bind.execute(
            sa.select(roles_table.c.id, roles_table.c.organization_id).where(
                roles_table.c.slug.in_(("admin", "manager"))
            )
        ).mappings()
    )

    for role in admin_roles:
        org_id = role["organization_id"]
        for resource, _ in FACTORY_RESOURCES:
            for action in ACTIONS:
                perm_id = permission_ids_by_org_and_code.get((org_id, f"{resource}.{action}"))
                if perm_id is None:
                    continue
                bind.execute(
                    role_permissions_table.insert().values(
                        role_id=role["id"],
                        permission_id=perm_id,
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()

    for resource, _ in FACTORY_RESOURCES:
        perm_rows = list(
            bind.execute(
                sa.select(permissions_table.c.id).where(permissions_table.c.resource == resource)
            ).mappings()
        )
        perm_ids = [r["id"] for r in perm_rows]
        if perm_ids:
            bind.execute(role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(perm_ids)))
            bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(perm_ids)))

    for table_name in ("factory_shipments", "factory_daily_logs", "factory_flocks"):
        indexes = [idx for idx in ("id", "organization_id", "department_id", "warehouse_id", "flock_id", "client_id", "shipped_on", "poultry_type_id", "source_client_id", "flock_code", "arrived_on", "log_date")]
        for col in indexes:
            try:
                op.drop_index(op.f(f"ix_{table_name}_{col}"), table_name=table_name)
            except Exception:
                pass
        op.drop_table(table_name)
