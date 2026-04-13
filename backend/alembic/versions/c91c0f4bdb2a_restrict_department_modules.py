"""restrict department modules to operational modules

Revision ID: c91c0f4bdb2a
Revises: b6d3f4a1290c
Create Date: 2026-03-19 00:50:00.000000
"""

from alembic import op


revision = "c91c0f4bdb2a"
down_revision = "b6d3f4a1290c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_department_module_key_allowed", "departments", type_="check")
    op.create_check_constraint(
        "ck_department_module_key_allowed",
        "departments",
        "module_key IN ('egg', 'incubation', 'factory', 'feed', 'medicine', 'slaughter')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_department_module_key_allowed", "departments", type_="check")
    op.create_check_constraint(
        "ck_department_module_key_allowed",
        "departments",
        "module_key IN ('core', 'egg', 'incubation', 'factory', 'feed', 'medicine', 'slaughter', 'finance', 'hr')",
    )
