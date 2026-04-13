"""department module hierarchy

Revision ID: 8c9c9b5c40ab
Revises: 3b4f0a6f2c11
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "8c9c9b5c40ab"
down_revision = "3b4f0a6f2c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("departments", sa.Column("module_key", sa.String(length=32), nullable=True))
    op.execute("UPDATE departments SET module_key = 'core' WHERE module_key IS NULL")
    op.alter_column("departments", "module_key", nullable=False)
    op.create_index(op.f("ix_departments_module_key"), "departments", ["module_key"], unique=False)
    op.drop_constraint("uq_department_org_name", "departments", type_="unique")
    op.drop_constraint("uq_department_org_code", "departments", type_="unique")
    op.create_unique_constraint(
        "uq_department_org_module_name",
        "departments",
        ["organization_id", "module_key", "name"],
    )
    op.create_unique_constraint(
        "uq_department_org_module_code",
        "departments",
        ["organization_id", "module_key", "code"],
    )
    op.create_check_constraint(
        "ck_department_module_key_allowed",
        "departments",
        "module_key IN ('core', 'egg', 'incubation', 'factory', 'feed', 'medicine', 'slaughter', 'finance', 'hr')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_department_module_key_allowed", "departments", type_="check")
    op.drop_constraint("uq_department_org_module_code", "departments", type_="unique")
    op.drop_constraint("uq_department_org_module_name", "departments", type_="unique")
    op.create_unique_constraint("uq_department_org_code", "departments", ["organization_id", "code"])
    op.create_unique_constraint("uq_department_org_name", "departments", ["organization_id", "name"])
    op.drop_index(op.f("ix_departments_module_key"), table_name="departments")
    op.drop_column("departments", "module_key")
