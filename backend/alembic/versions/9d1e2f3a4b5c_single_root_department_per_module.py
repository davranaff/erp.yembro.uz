"""single root department per module

Revision ID: 9d1e2f3a4b5c
Revises: 6a1b2c3d4e5f
Create Date: 2026-03-25 22:35:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9d1e2f3a4b5c"
down_revision = "6a1b2c3d4e5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_roots = list(
        bind.execute(
            sa.text(
                """
                SELECT organization_id, module_key, COUNT(*) AS root_count
                FROM departments
                WHERE parent_department_id IS NULL
                GROUP BY organization_id, module_key
                HAVING COUNT(*) > 1
                """
            )
        ).mappings()
    )

    if duplicate_roots:
        duplicate_summary = ", ".join(
            f"{row['organization_id']}::{row['module_key']} ({row['root_count']})"
            for row in duplicate_roots
        )
        raise RuntimeError(
            "Cannot enforce single root department per module while duplicates exist: "
            + duplicate_summary
        )

    op.create_index(
        "uq_departments_org_module_root",
        "departments",
        ["organization_id", "module_key"],
        unique=True,
        postgresql_where=sa.text("parent_department_id IS NULL"),
        sqlite_where=sa.text("parent_department_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_departments_org_module_root", table_name="departments")
