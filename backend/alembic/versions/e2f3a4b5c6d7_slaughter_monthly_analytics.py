"""Slaughter monthly analytics: new table for monthly KPI tracking

Revision ID: e2f3a4b5c6d7
Revises: d0e1f2a3b4c5
Create Date: 2026-04-17
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slaughter_monthly_analytics",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("poultry_type_id", sa.UUID(), nullable=True),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("birds_received", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("birds_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_sort_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("second_sort_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bad_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_sort_weight_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("second_sort_weight_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("bad_weight_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("shipped_quantity_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("shipped_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("purchased_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_slaughter_monthly_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_slaughter_monthly_department",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["poultry_type_id"],
            ["poultry_types.id"],
            name="fk_slaughter_monthly_poultry_type",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "department_id",
            "poultry_type_id",
            "month_start",
            name="uq_slaughter_monthly_org_department_poultry_month",
        ),
        sa.CheckConstraint(
            "birds_received >= 0",
            name="ck_slaughter_monthly_birds_received_non_negative",
        ),
        sa.CheckConstraint(
            "birds_processed >= 0",
            name="ck_slaughter_monthly_birds_processed_non_negative",
        ),
        sa.CheckConstraint(
            "birds_processed <= birds_received",
            name="ck_slaughter_monthly_processed_not_exceed_received",
        ),
        sa.CheckConstraint(
            "first_sort_count >= 0",
            name="ck_slaughter_monthly_first_sort_count_non_negative",
        ),
        sa.CheckConstraint(
            "second_sort_count >= 0",
            name="ck_slaughter_monthly_second_sort_count_non_negative",
        ),
        sa.CheckConstraint(
            "bad_count >= 0",
            name="ck_slaughter_monthly_bad_count_non_negative",
        ),
        sa.CheckConstraint(
            "first_sort_weight_kg >= 0",
            name="ck_slaughter_monthly_first_sort_weight_non_negative",
        ),
        sa.CheckConstraint(
            "second_sort_weight_kg >= 0",
            name="ck_slaughter_monthly_second_sort_weight_non_negative",
        ),
        sa.CheckConstraint(
            "bad_weight_kg >= 0",
            name="ck_slaughter_monthly_bad_weight_non_negative",
        ),
        sa.CheckConstraint(
            "shipped_quantity_kg >= 0",
            name="ck_slaughter_monthly_shipped_quantity_non_negative",
        ),
        sa.CheckConstraint(
            "shipped_amount >= 0",
            name="ck_slaughter_monthly_shipped_amount_non_negative",
        ),
        sa.CheckConstraint(
            "purchased_amount >= 0",
            name="ck_slaughter_monthly_purchased_amount_non_negative",
        ),
    )
    op.create_index(
        "ix_slaughter_monthly_analytics_organization_id",
        "slaughter_monthly_analytics",
        ["organization_id"],
    )
    op.create_index(
        "ix_slaughter_monthly_analytics_department_id",
        "slaughter_monthly_analytics",
        ["department_id"],
    )
    op.create_index(
        "ix_slaughter_monthly_analytics_poultry_type_id",
        "slaughter_monthly_analytics",
        ["poultry_type_id"],
    )
    op.create_index(
        "ix_slaughter_monthly_analytics_month_start",
        "slaughter_monthly_analytics",
        ["month_start"],
    )

    # Seed workspace resource for the new module entity.
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, permission_prefix,
            sort_order, is_head_visible, is_active,
            created_at, updated_at
        ) VALUES (
            '32000000-0000-0000-0000-000000000188',
            'slaughter',
            'slaughter-monthly-analytics',
            'Помесячная аналитика',
            'monthly-analytics',
            'slaughter_monthly_analytics',
            35,
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
            'slaughter_monthly_analytics.' || act.code,
            'slaughter_monthly_analytics',
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
              AND p.code = 'slaughter_monthly_analytics.' || act.code
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
          AND p.code LIKE 'slaughter_monthly_analytics.%'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'slaughter_monthly_analytics.%')"
    )
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'slaughter_monthly_analytics.%'"
    )
    op.execute(
        "DELETE FROM workspace_resources WHERE key = 'slaughter-monthly-analytics'"
    )

    op.drop_index(
        "ix_slaughter_monthly_analytics_month_start",
        table_name="slaughter_monthly_analytics",
    )
    op.drop_index(
        "ix_slaughter_monthly_analytics_poultry_type_id",
        table_name="slaughter_monthly_analytics",
    )
    op.drop_index(
        "ix_slaughter_monthly_analytics_department_id",
        table_name="slaughter_monthly_analytics",
    )
    op.drop_index(
        "ix_slaughter_monthly_analytics_organization_id",
        table_name="slaughter_monthly_analytics",
    )
    op.drop_table("slaughter_monthly_analytics")
