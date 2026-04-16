"""client categories catalog

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-16 14:00:00.000000
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


organizations_table = sa.table(
    "organizations",
    sa.column("id", sa.UUID()),
)

client_categories_table = sa.table(
    "client_categories",
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
    "read": "View client categories",
    "create": "Create client categories",
    "write": "Update client categories",
    "delete": "Delete client categories",
}

DEFAULT_CATEGORIES = [
    {"code": "supplier", "name": "Yetkazib beruvchi", "description": "Yetkazib beruvchi (поставщик)", "sort_order": 10},
    {"code": "buyer", "name": "Xaridor", "description": "Xaridor (покупатель)", "sort_order": 20},
    {"code": "logistics", "name": "Logistika", "description": "Logistika kompaniyasi", "sort_order": 30},
]


def upgrade() -> None:
    op.create_table(
        "client_categories",
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
        sa.UniqueConstraint("organization_id", "code", name="uq_client_category_org_code"),
        sa.UniqueConstraint("organization_id", "name", name="uq_client_category_org_name"),
    )
    op.create_index(op.f("ix_client_categories_id"), "client_categories", ["id"], unique=False)
    op.create_index(op.f("ix_client_categories_code"), "client_categories", ["code"], unique=False)
    op.create_index(op.f("ix_client_categories_name"), "client_categories", ["name"], unique=False)
    op.create_index(op.f("ix_client_categories_organization_id"), "client_categories", ["organization_id"], unique=False)
    op.create_index(op.f("ix_client_categories_sort_order"), "client_categories", ["sort_order"], unique=False)

    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())

    for organization in organizations:
        organization_id = organization["id"]
        for category in DEFAULT_CATEGORIES:
            bind.execute(
                client_categories_table.insert().values(
                    id=uuid4(),
                    organization_id=organization_id,
                    code=category["code"],
                    name=category["name"],
                    description=category["description"],
                    sort_order=category["sort_order"],
                    is_active=True,
                )
            )

    permission_ids_by_org_and_code: dict[tuple[object, str], object] = {}
    for organization in organizations:
        organization_id = organization["id"]
        for action, description in DEFAULT_PERMISSION_DESCRIPTIONS.items():
            code = f"client_category.{action}"
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
                        resource="client_category",
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
            permission_id = permission_ids_by_org_and_code.get((organization_id, f"client_category.{action}"))
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
                permissions_table.c.resource == "client_category"
            )
        ).mappings()
    )
    permission_ids = [row["id"] for row in permission_rows]
    if permission_ids:
        bind.execute(
            role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(permission_ids))
        )
        bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))

    op.drop_index(op.f("ix_client_categories_sort_order"), table_name="client_categories")
    op.drop_index(op.f("ix_client_categories_organization_id"), table_name="client_categories")
    op.drop_index(op.f("ix_client_categories_name"), table_name="client_categories")
    op.drop_index(op.f("ix_client_categories_code"), table_name="client_categories")
    op.drop_index(op.f("ix_client_categories_id"), table_name="client_categories")
    op.drop_table("client_categories")
