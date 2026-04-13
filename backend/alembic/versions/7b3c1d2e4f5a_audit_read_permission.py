"""audit read permission

Revision ID: 7b3c1d2e4f5a
Revises: f2a3c4d5e6b7
Create Date: 2026-03-25 00:30:00.000000
"""

from __future__ import annotations

from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "7b3c1d2e4f5a"
down_revision = "f2a3c4d5e6b7"
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


def upgrade() -> None:
    bind = op.get_bind()
    organizations = list(bind.execute(sa.select(organizations_table.c.id)).mappings())

    permission_ids_by_org: dict[object, object] = {}
    for organization in organizations:
        organization_id = organization["id"]
        existing_permission_id = bind.execute(
            sa.select(permissions_table.c.id).where(
                permissions_table.c.organization_id == organization_id,
                permissions_table.c.code == "audit.read",
            )
        ).scalar_one_or_none()

        if existing_permission_id is None:
            existing_permission_id = uuid4()
            bind.execute(
                permissions_table.insert().values(
                    id=existing_permission_id,
                    organization_id=organization_id,
                    code="audit.read",
                    resource="audit",
                    action="read",
                    description="View audit history",
                    is_active=True,
                )
            )

        permission_ids_by_org[organization_id] = existing_permission_id

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


def downgrade() -> None:
    bind = op.get_bind()
    permission_rows = list(
        bind.execute(
            sa.select(permissions_table.c.id).where(permissions_table.c.code == "audit.read")
        ).mappings()
    )
    permission_ids = [row["id"] for row in permission_rows]
    if not permission_ids:
        return

    bind.execute(
        role_permissions_table.delete().where(role_permissions_table.c.permission_id.in_(permission_ids))
    )
    bind.execute(permissions_table.delete().where(permissions_table.c.id.in_(permission_ids)))
