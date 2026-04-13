"""department scoped module finance

Revision ID: c2d4e6f8a9b0
Revises: a9b1c2d3e4f6
Create Date: 2026-04-12 00:00:00.000000
"""

from __future__ import annotations

from collections import defaultdict
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic import op
import sqlalchemy as sa


revision = "c2d4e6f8a9b0"
down_revision = "a9b1c2d3e4f6"
branch_labels = None
depends_on = None


expense_categories_table = sa.table(
    "expense_categories",
    sa.column("id", sa.UUID()),
    sa.column("organization_id", sa.UUID()),
    sa.column("department_id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("code", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("is_active", sa.Boolean()),
    sa.column("is_global", sa.Boolean()),
)

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

MODULE_EXPENSE_CATEGORY_RESOURCES: tuple[dict[str, object], ...] = (
    {
        "id": "32000000-0000-0000-0000-000000000908",
        "module_key": "egg",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 79,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000909",
        "module_key": "incubation",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 59,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000910",
        "module_key": "factory",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 59,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000911",
        "module_key": "feed",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 99,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000912",
        "module_key": "medicine",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 69,
        "is_head_visible": True,
        "is_active": True,
    },
    {
        "id": "32000000-0000-0000-0000-000000000913",
        "module_key": "slaughter",
        "key": "expense-categories",
        "name": "Категории расходов",
        "path": "expense-categories",
        "description": "Категории расходов выбранного департамента",
        "permission_prefix": "expense_category",
        "api_module_key": "finance",
        "sort_order": 69,
        "is_head_visible": True,
        "is_active": True,
    },
)


def _build_clone_id(category_id: str, department_id: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"expense-category|{category_id}|{department_id}")


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
    for resource in MODULE_EXPENSE_CATEGORY_RESOURCES:
        bind.execute(
            workspace_resources_table.delete().where(
                workspace_resources_table.c.module_key == resource["module_key"],
                workspace_resources_table.c.key == resource["key"],
            )
        )


def _clone_shared_categories_per_department(bind) -> None:
    categories = list(
        bind.execute(
            sa.text(
                """
                SELECT id, organization_id, name, code, description, is_active, is_global
                FROM expense_categories
                ORDER BY organization_id, name, code, id
                """
            )
        ).mappings()
    )
    expense_usage_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT category_id, department_id
                FROM expenses
                WHERE category_id IS NOT NULL
                ORDER BY category_id, department_id
                """
            )
        ).mappings()
    )
    department_rows = list(
        bind.execute(
            sa.text(
                """
                SELECT id, organization_id
                FROM departments
                ORDER BY organization_id, name, id
                """
            )
        ).mappings()
    )

    departments_by_category: dict[str, list[str]] = defaultdict(list)
    for row in expense_usage_rows:
        category_id = str(row["category_id"])
        department_id = str(row["department_id"])
        if department_id not in departments_by_category[category_id]:
            departments_by_category[category_id].append(department_id)

    fallback_department_by_org: dict[str, str] = {}
    for row in department_rows:
        organization_id = str(row["organization_id"])
        department_id = str(row["id"])
        fallback_department_by_org.setdefault(organization_id, department_id)

    for category in categories:
        category_id = str(category["id"])
        organization_id = str(category["organization_id"])
        scoped_departments = list(departments_by_category.get(category_id, []))

        fallback_department_id = fallback_department_by_org.get(organization_id)
        if not scoped_departments and fallback_department_id is not None:
            scoped_departments.append(fallback_department_id)
        if not scoped_departments:
            continue

        primary_department_id = scoped_departments[0]
        bind.execute(
            expense_categories_table.update()
            .where(expense_categories_table.c.id == UUID(category_id))
            .values(
                department_id=UUID(primary_department_id),
                is_global=False,
            )
        )

        for department_id in scoped_departments[1:]:
            clone_id = _build_clone_id(category_id, department_id)
            existing_clone = bind.execute(
                sa.select(expense_categories_table.c.id).where(
                    expense_categories_table.c.id == clone_id
                )
            ).scalar_one_or_none()
            if existing_clone is None:
                bind.execute(
                    expense_categories_table.insert().values(
                        id=clone_id,
                        organization_id=UUID(organization_id),
                        department_id=UUID(department_id),
                        name=category["name"],
                        code=category["code"],
                        description=category["description"],
                        is_active=bool(category["is_active"]),
                        is_global=False,
                    )
                )

            bind.execute(
                sa.text(
                    """
                    UPDATE expenses
                    SET category_id = :clone_id
                    WHERE category_id = :category_id
                      AND department_id = :department_id
                    """
                ),
                {
                    "clone_id": str(clone_id),
                    "category_id": category_id,
                    "department_id": department_id,
                },
            )


def _merge_department_scoped_categories(bind) -> None:
    categories = list(
        bind.execute(
            sa.text(
                """
                SELECT id, organization_id, name, code
                FROM expense_categories
                ORDER BY organization_id, name, code, id
                """
            )
        ).mappings()
    )

    canonical_by_name_and_code: dict[tuple[str, str, str], str] = {}
    duplicate_ids: list[str] = []

    for row in categories:
        organization_id = str(row["organization_id"])
        key = (organization_id, str(row["name"] or ""), str(row["code"] or ""))
        category_id = str(row["id"])
        canonical_id = canonical_by_name_and_code.get(key)
        if canonical_id is None:
            canonical_by_name_and_code[key] = category_id
            continue

        bind.execute(
            sa.text(
                """
                UPDATE expenses
                SET category_id = :canonical_id
                WHERE category_id = :duplicate_id
                """
            ),
            {
                "canonical_id": canonical_id,
                "duplicate_id": category_id,
            },
        )
        duplicate_ids.append(category_id)

    for duplicate_id in duplicate_ids:
        bind.execute(
            expense_categories_table.delete().where(
                expense_categories_table.c.id == UUID(duplicate_id)
            )
        )


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("expense_categories", sa.Column("department_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_expense_categories_department_id"),
        "expense_categories",
        ["department_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_expense_categories_department_id",
        "expense_categories",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("uq_expense_category_org_name", "expense_categories", type_="unique")
    op.drop_constraint("uq_expense_category_org_code", "expense_categories", type_="unique")

    _clone_shared_categories_per_department(bind)

    op.alter_column("expense_categories", "department_id", nullable=False)
    op.create_unique_constraint(
        "uq_expense_category_org_department_name",
        "expense_categories",
        ["organization_id", "department_id", "name"],
    )
    op.create_unique_constraint(
        "uq_expense_category_org_department_code",
        "expense_categories",
        ["organization_id", "department_id", "code"],
    )

    for resource in MODULE_EXPENSE_CATEGORY_RESOURCES:
        _upsert_workspace_resource(bind, resource)


def downgrade() -> None:
    bind = op.get_bind()

    _delete_workspace_resources(bind)
    _merge_department_scoped_categories(bind)

    op.drop_constraint(
        "uq_expense_category_org_department_name",
        "expense_categories",
        type_="unique",
    )
    op.drop_constraint(
        "uq_expense_category_org_department_code",
        "expense_categories",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_expense_category_org_name",
        "expense_categories",
        ["organization_id", "name"],
    )
    op.create_unique_constraint(
        "uq_expense_category_org_code",
        "expense_categories",
        ["organization_id", "code"],
    )
    op.drop_constraint("fk_expense_categories_department_id", "expense_categories", type_="foreignkey")
    op.drop_index(op.f("ix_expense_categories_department_id"), table_name="expense_categories")
    op.drop_column("expense_categories", "department_id")
