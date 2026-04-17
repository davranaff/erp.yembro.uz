"""Egg quality checks + grade breakdown on production/monthly analytics

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Grade breakdown on egg_production
    op.add_column(
        "egg_production",
        sa.Column("eggs_large", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_production",
        sa.Column("eggs_medium", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_production",
        sa.Column("eggs_small", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_production",
        sa.Column("eggs_defective", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_egg_prod_eggs_large_non_negative",
        "egg_production",
        "eggs_large >= 0",
    )
    op.create_check_constraint(
        "ck_egg_prod_eggs_medium_non_negative",
        "egg_production",
        "eggs_medium >= 0",
    )
    op.create_check_constraint(
        "ck_egg_prod_eggs_small_non_negative",
        "egg_production",
        "eggs_small >= 0",
    )
    op.create_check_constraint(
        "ck_egg_prod_eggs_defective_non_negative",
        "egg_production",
        "eggs_defective >= 0",
    )

    # 2. Grade + quality metrics on egg_monthly_analytics
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("large_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("medium_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("small_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("defective_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("quality_passed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("quality_failed_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "egg_monthly_analytics",
        sa.Column("quality_pending_count", sa.Integer(), nullable=False, server_default="0"),
    )
    for col in (
        "large_count",
        "medium_count",
        "small_count",
        "defective_count",
        "quality_passed_count",
        "quality_failed_count",
        "quality_pending_count",
    ):
        op.create_check_constraint(
            f"ck_egg_monthly_{col}_non_negative",
            "egg_monthly_analytics",
            f"{col} >= 0",
        )

    # 3. egg_quality_checks table
    op.create_table(
        "egg_quality_checks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("production_id", sa.UUID(), nullable=False),
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
            name="fk_egg_quality_check_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_egg_quality_check_department",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_id"],
            ["egg_production.id"],
            name="fk_egg_quality_check_production",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inspector_id"],
            ["employees.id"],
            name="fk_egg_quality_check_inspector",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed')",
            name="ck_egg_quality_check_status",
        ),
        sa.CheckConstraint(
            "grade IS NULL OR grade IN ('large', 'medium', 'small', 'defective', 'mixed')",
            name="ck_egg_quality_check_grade",
        ),
    )
    op.create_index(
        "ix_egg_quality_checks_organization_id",
        "egg_quality_checks",
        ["organization_id"],
    )
    op.create_index(
        "ix_egg_quality_checks_department_id",
        "egg_quality_checks",
        ["department_id"],
    )
    op.create_index(
        "ix_egg_quality_checks_production_id",
        "egg_quality_checks",
        ["production_id"],
    )
    op.create_index(
        "ix_egg_quality_checks_checked_on",
        "egg_quality_checks",
        ["checked_on"],
    )
    op.create_index(
        "ix_egg_quality_checks_status",
        "egg_quality_checks",
        ["status"],
    )
    op.create_index(
        "ix_egg_quality_checks_inspector_id",
        "egg_quality_checks",
        ["inspector_id"],
    )

    # 4. Seed workspace resource
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, permission_prefix,
            sort_order, is_head_visible, is_active,
            created_at, updated_at
        ) VALUES (
            '32000000-0000-0000-0000-000000000189',
            'egg',
            'egg-quality-checks',
            'Контроль качества',
            'quality-checks',
            'egg_quality_check',
            25,
            TRUE,
            TRUE,
            now(), now()
        )
        ON CONFLICT (module_key, key) DO NOTHING
        """
    )

    # 5. Seed permissions for every organization.
    op.execute(
        """
        INSERT INTO permissions (
            id, organization_id, code, resource, action, description, is_active,
            created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            o.id,
            'egg_quality_check.' || act.code,
            'egg_quality_check',
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
              AND p.code = 'egg_quality_check.' || act.code
        )
        """
    )

    # 6. Assign to admin and manager roles.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager')
          AND p.code LIKE 'egg_quality_check.%'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'egg_quality_check.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'egg_quality_check.%'")
    op.execute(
        "DELETE FROM workspace_resources WHERE key = 'egg-quality-checks'"
    )

    op.drop_index("ix_egg_quality_checks_inspector_id", table_name="egg_quality_checks")
    op.drop_index("ix_egg_quality_checks_status", table_name="egg_quality_checks")
    op.drop_index("ix_egg_quality_checks_checked_on", table_name="egg_quality_checks")
    op.drop_index("ix_egg_quality_checks_production_id", table_name="egg_quality_checks")
    op.drop_index("ix_egg_quality_checks_department_id", table_name="egg_quality_checks")
    op.drop_index("ix_egg_quality_checks_organization_id", table_name="egg_quality_checks")
    op.drop_table("egg_quality_checks")

    for col in (
        "quality_pending_count",
        "quality_failed_count",
        "quality_passed_count",
        "defective_count",
        "small_count",
        "medium_count",
        "large_count",
    ):
        op.drop_constraint(
            f"ck_egg_monthly_{col}_non_negative",
            "egg_monthly_analytics",
            type_="check",
        )
        op.drop_column("egg_monthly_analytics", col)

    for col in ("eggs_defective", "eggs_small", "eggs_medium", "eggs_large"):
        op.drop_constraint(
            f"ck_egg_prod_{col}_non_negative",
            "egg_production",
            type_="check",
        )
        op.drop_column("egg_production", col)
