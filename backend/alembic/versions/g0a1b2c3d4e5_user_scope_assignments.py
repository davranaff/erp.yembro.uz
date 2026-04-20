"""user_scope_assignments: row-level scope grants beyond home department

Revision ID: g0a1b2c3d4e5
Revises: e0f1a2b3c4d5
Create Date: 2026-04-19

Adds `user_scope_assignments` table to express per-user extra access to
departments or warehouses beyond the user's home department
(Employee.department_id). See docs/adr/0001-row-level-scope.md.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "g0a1b2c3d4e5"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_scope_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_type", sa.Text(), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_prefix", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "scope_type IN ('department', 'warehouse')",
            name="user_scope_assignments_scope_type_check",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["employees.id"], ondelete="CASCADE"
        ),
    )

    op.create_index(
        "ix_user_scope_assignments_employee_type",
        "user_scope_assignments",
        ["employee_id", "scope_type"],
    )
    op.create_index(
        "ix_user_scope_assignments_scope",
        "user_scope_assignments",
        ["scope_type", "scope_id"],
    )
    op.create_unique_constraint(
        "uq_user_scope_assignments_unique_grant",
        "user_scope_assignments",
        ["employee_id", "scope_type", "scope_id", "permission_prefix"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_user_scope_assignments_unique_grant",
        "user_scope_assignments",
        type_="unique",
    )
    op.drop_index(
        "ix_user_scope_assignments_scope",
        table_name="user_scope_assignments",
    )
    op.drop_index(
        "ix_user_scope_assignments_employee_type",
        table_name="user_scope_assignments",
    )
    op.drop_table("user_scope_assignments")
