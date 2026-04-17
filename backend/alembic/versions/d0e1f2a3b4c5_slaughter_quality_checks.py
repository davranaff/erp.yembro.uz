"""Slaughter quality checks: new table blocking shipments until passed

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slaughter_quality_checks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("semi_product_id", sa.UUID(), nullable=False),
        sa.Column("checked_on", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("grade", sa.String(length=20), nullable=True),
        sa.Column("inspector_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_slaughter_quality_check_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_slaughter_quality_check_department",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["semi_product_id"],
            ["slaughter_semi_products.id"],
            name="fk_slaughter_quality_check_semi_product",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inspector_id"],
            ["employees.id"],
            name="fk_slaughter_quality_check_inspector",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed')",
            name="ck_slaughter_quality_check_status",
        ),
        sa.CheckConstraint(
            "grade IS NULL OR grade IN ('first', 'second', 'mixed', 'byproduct')",
            name="ck_slaughter_quality_check_grade",
        ),
    )
    op.create_index(
        "ix_slaughter_quality_checks_organization_id",
        "slaughter_quality_checks",
        ["organization_id"],
    )
    op.create_index(
        "ix_slaughter_quality_checks_department_id",
        "slaughter_quality_checks",
        ["department_id"],
    )
    op.create_index(
        "ix_slaughter_quality_checks_semi_product_id",
        "slaughter_quality_checks",
        ["semi_product_id"],
    )
    op.create_index(
        "ix_slaughter_quality_checks_checked_on",
        "slaughter_quality_checks",
        ["checked_on"],
    )
    op.create_index(
        "ix_slaughter_quality_checks_status",
        "slaughter_quality_checks",
        ["status"],
    )
    op.create_index(
        "ix_slaughter_quality_checks_inspector_id",
        "slaughter_quality_checks",
        ["inspector_id"],
    )

    # Seed workspace resource for the new module entity.
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, permission_prefix,
            sort_order, is_head_visible, is_active,
            created_at, updated_at
        ) VALUES (
            '32000000-0000-0000-0000-000000000187',
            'slaughter',
            'slaughter-quality-checks',
            'Контроль качества',
            'quality-checks',
            'slaughter_quality_check',
            30,
            TRUE,
            TRUE,
            now(), now()
        )
        ON CONFLICT (module_key, key) DO NOTHING
        """
    )

    # Seed permissions for every organization (one row per action).
    op.execute(
        """
        INSERT INTO permissions (
            id, organization_id, code, resource, action, description, is_active,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            o.id,
            'slaughter_quality_check.' || act.code,
            'slaughter_quality_check',
            act.code,
            act.description,
            true,
            now(), now()
        FROM organizations o
        CROSS JOIN (
            VALUES
                ('read',   'Просмотр'),
                ('list',   'Список'),
                ('create', 'Создание'),
                ('update', 'Обновление'),
                ('write',  'Редактирование'),
                ('delete', 'Удаление')
        ) AS act(code, description)
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.organization_id = o.id
              AND p.code = 'slaughter_quality_check.' || act.code
        )
        """
    )

    # Assign new permissions to admin and manager roles.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager')
          AND p.code LIKE 'slaughter_quality_check.%'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'slaughter_quality_check.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'slaughter_quality_check.%'")
    op.execute(
        "DELETE FROM workspace_resources WHERE key = 'slaughter-quality-checks'"
    )

    op.drop_index(
        "ix_slaughter_quality_checks_inspector_id",
        table_name="slaughter_quality_checks",
    )
    op.drop_index(
        "ix_slaughter_quality_checks_status",
        table_name="slaughter_quality_checks",
    )
    op.drop_index(
        "ix_slaughter_quality_checks_checked_on",
        table_name="slaughter_quality_checks",
    )
    op.drop_index(
        "ix_slaughter_quality_checks_semi_product_id",
        table_name="slaughter_quality_checks",
    )
    op.drop_index(
        "ix_slaughter_quality_checks_department_id",
        table_name="slaughter_quality_checks",
    )
    op.drop_index(
        "ix_slaughter_quality_checks_organization_id",
        table_name="slaughter_quality_checks",
    )
    op.drop_table("slaughter_quality_checks")
