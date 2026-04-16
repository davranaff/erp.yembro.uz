"""measurement units catalog

Revision ID: a1b2c3d4e5f6
Revises: f6e7d8c9b0a1
Create Date: 2026-04-16 12:00:00.000000
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f6e7d8c9b0a1"
branch_labels = None
depends_on = None


organizations_table = sa.table(
    "organizations",
    sa.column("id", sa.UUID()),
)

measurement_units_table = sa.table(
    "measurement_units",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_active", sa.Boolean()),
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

DEFAULT_PERMISSION_DESCRIPTIONS = {
    "read": "View measurement units",
    "create": "Create measurement units",
    "write": "Update measurement units",
    "delete": "Delete measurement units",
}

DEFAULT_UNITS = [
    {"code": "pcs", "name": "Dona", "description": "Dona (штука)", "sort_order": 10},
    {"code": "kg", "name": "Kilogramm", "description": "Kilogramm", "sort_order": 20},
    {"code": "ltr", "name": "Litr", "description": "Litr", "sort_order": 30},
    {"code": "g", "name": "Gramm", "description": "Gramm", "sort_order": 40},
    {"code": "ml", "name": "Millilitr", "description": "Millilitr", "sort_order": 50},
    {"code": "ton", "name": "Tonna", "description": "Tonna", "sort_order": 60},
]


def upgrade() -> None:
    op.create_table(
        "measurement_units",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="100", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_measurement_unit_org_code"),
        sa.UniqueConstraint("organization_id", "name", name="uq_measurement_unit_org_name"),
    )
    op.create_index(op.f("ix_measurement_units_id"), "measurement_units", ["id"], unique=False)
    op.create_index(op.f("ix_measurement_units_code"), "measurement_units", ["code"], unique=False)
    op.create_index(op.f("ix_measurement_units_name"), "measurement_units", ["name"], unique=False)
    op.create_index(op.f("ix_measurement_units_organization_id"), "measurement_units", ["organization_id"], unique=False)
    op.create_index(op.f("ix_measurement_units_sort_order"), "measurement_units", ["sort_order"], unique=False)

    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())

    for organization in organizations:
        organization_id = organization["id"]
        for unit in DEFAULT_UNITS:
            bind.execute(
                measurement_units_table.insert().values(
                    id=uuid4(),
                    organization_id=organization_id,
                    code=unit["code"],
                    name=unit["name"],
                    description=unit["description"],
                    sort_order=unit["sort_order"],
                    is_active=True,
                )
            )

    permission_ids_by_org_and_code: dict[tuple[object, str], object] = {}
    for organization in organizations:
        organization_id = organization["id"]
        for action, description in DEFAULT_PERMISSION_DESCRIPTIONS.items():
            code = f"measurement_unit.{action}"
            existing_permission_id = bind.execute(
                sa.select(permissions_table.c.id).where(
                    permissions_table.c.organization_id == organization_id,
                    permissions_table.c.code == code,
                )
            ).scalar_one_or_none()

            if existing_permission_id is None:
                existing_permission_id = uuid4()
                bind.execute(
                    permissions_table.insert().values(
                        id=existing_permission_id,
                        organization_id=organization_id,
                        code=code,
                        resource="measurement_unit",
                        action=action,
                        description=description,
                        is_active=True,
                    )
                )
            permission_ids_by_org_and_code[(organization_id, code)] = existing_permission_id

    admin_roles = list(
        bind.execute(
            sa.select(roles_table.c.id, roles_table.c.organization_id).where(
                roles_table.c.slug.in_(("admin", "manager"))
            )
        ).mappings()
    )

    for role in admin_roles:
        organization_id = role["organization_id"]
        for action in DEFAULT_PERMISSION_DESCRIPTIONS:
            permission_id = permission_ids_by_org_and_code.get((organization_id, f"measurement_unit.{action}"))
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


def downgrade() -> None:
    bind = op.get_bind()
    permission_rows = list(
        bind.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.resource == "measurement_unit"
            )
        ).mappings()
    )
    permission_ids = [row["id"] for row in permission_rows]
    if permission_ids:
        bind.execute(
            role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(permission_ids))
        )
        bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))

    op.drop_index(op.f("ix_measurement_units_sort_order"), table_name="measurement_units")
    op.drop_index(op.f("ix_measurement_units_organization_id"), table_name="measurement_units")
    op.drop_index(op.f("ix_measurement_units_name"), table_name="measurement_units")
    op.drop_index(op.f("ix_measurement_units_code"), table_name="measurement_units")
    op.drop_index(op.f("ix_measurement_units_id"), table_name="measurement_units")
    op.drop_table("measurement_units")
