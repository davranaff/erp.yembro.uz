"""department modules catalog

Revision ID: 4e6f8a9b1c2d
Revises: 7b3c1d2e4f5a
Create Date: 2026-03-25 10:00:00.000000
"""

from __future__ import annotations

from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa


revision = "4e6f8a9b1c2d"
down_revision = "7b3c1d2e4f5a"
branch_labels = None
depends_on = None


department_modules_table = sa.table(
    "department_modules",
    sa.column("id", sa.UUID()),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
    sa.column("icon", sa.String()),
    sa.column("sort_order", sa.Integer()),
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

DEFAULT_DEPARTMENT_MODULES = (
    {
        "id": UUID("31111111-1111-1111-1111-111111111111"),
        "key": "egg",
        "name": "Egg Farm",
        "description": "Operational module for egg production departments",
        "icon": "egg",
        "sort_order": 10,
        "is_active": True,
    },
    {
        "id": UUID("31222222-2222-2222-2222-222222222222"),
        "key": "incubation",
        "name": "Incubation",
        "description": "Operational module for incubation departments",
        "icon": "archive",
        "sort_order": 20,
        "is_active": True,
    },
    {
        "id": UUID("31333333-3333-3333-3333-333333333333"),
        "key": "factory",
        "name": "Factory",
        "description": "Operational module for broiler factory departments",
        "icon": "factory",
        "sort_order": 30,
        "is_active": True,
    },
    {
        "id": UUID("31444444-4444-4444-4444-444444444444"),
        "key": "feed",
        "name": "Feed Mill",
        "description": "Operational module for feed mill departments",
        "icon": "package",
        "sort_order": 40,
        "is_active": True,
    },
    {
        "id": UUID("31555555-5555-5555-5555-555555555555"),
        "key": "medicine",
        "name": "Vet Pharmacy",
        "description": "Operational module for veterinary pharmacy departments",
        "icon": "pill",
        "sort_order": 50,
        "is_active": True,
    },
    {
        "id": UUID("31666666-6666-6666-6666-666666666666"),
        "key": "slaughter",
        "name": "Slaughterhouse",
        "description": "Operational module for slaughter departments",
        "icon": "shield",
        "sort_order": 60,
        "is_active": True,
    },
)

DEFAULT_PERMISSION_DESCRIPTIONS = {
    "read": "View department modules",
    "create": "Create department modules",
    "write": "Update department modules",
    "delete": "Delete department modules",
}


def upgrade() -> None:
    op.create_table(
        "department_modules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(length=48), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_department_module_key"),
    )
    op.create_index(op.f("ix_department_modules_id"), "department_modules", ["id"], unique=False)
    op.create_index(op.f("ix_department_modules_key"), "department_modules", ["key"], unique=False)
    op.create_index(op.f("ix_department_modules_name"), "department_modules", ["name"], unique=False)
    op.create_index(op.f("ix_department_modules_sort_order"), "department_modules", ["sort_order"], unique=False)

    op.bulk_insert(department_modules_table, list(DEFAULT_DEPARTMENT_MODULES))

    op.drop_constraint("ck_department_module_key_allowed", "departments", type_="check")
    op.create_foreign_key(
        "fk_departments_module_key_department_modules",
        "departments",
        "department_modules",
        ["module_key"],
        ["key"],
        ondelete="RESTRICT",
    )

    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())
    permission_ids_by_org_and_code: dict[tuple[object, str], object] = {}

    for organization in organizations:
        organization_id = organization["id"]
        for action, description in DEFAULT_PERMISSION_DESCRIPTIONS.items():
            code = f"department_module.{action}"
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
                        resource="department_module",
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
            permission_id = permission_ids_by_org_and_code.get(
                (organization_id, f"department_module.{action}")
            )
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
                permissions_table.c.resource == "department_module"
            )
        ).mappings()
    )
    permission_ids = [row["id"] for row in permission_rows]
    if permission_ids:
        bind.execute(
            role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(permission_ids))
        )
        bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))

    op.drop_constraint(
        "fk_departments_module_key_department_modules",
        "departments",
        type_="foreignkey",
    )
    op.create_check_constraint(
        "ck_department_module_key_allowed",
        "departments",
        "module_key IN ('egg', 'incubation', 'factory', 'feed', 'medicine', 'slaughter')",
    )

    op.drop_index(op.f("ix_department_modules_sort_order"), table_name="department_modules")
    op.drop_index(op.f("ix_department_modules_name"), table_name="department_modules")
    op.drop_index(op.f("ix_department_modules_key"), table_name="department_modules")
    op.drop_index(op.f("ix_department_modules_id"), table_name="department_modules")
    op.drop_table("department_modules")
