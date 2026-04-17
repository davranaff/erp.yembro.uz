"""Feed module parity: raw arrivals/consumptions warehouses + created_by,
production QC table, monthly analytics table, seed workspace_resources & permissions.

Revision ID: a2b3c4d5e6f7
Revises: f3a4b5c6d7e8
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a2b3c4d5e6f7"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. warehouse_id + created_by on feed_raw_arrivals
    op.add_column(
        "feed_raw_arrivals",
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_raw_arrival_warehouse",
        "feed_raw_arrivals",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_raw_arrivals_warehouse_id",
        "feed_raw_arrivals",
        ["warehouse_id"],
    )
    op.add_column(
        "feed_raw_arrivals",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_raw_arrival_created_by",
        "feed_raw_arrivals",
        "employees",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_raw_arrivals_created_by",
        "feed_raw_arrivals",
        ["created_by"],
    )

    # 2. warehouse_id + created_by on feed_raw_consumptions
    op.add_column(
        "feed_raw_consumptions",
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_raw_consumption_warehouse",
        "feed_raw_consumptions",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_raw_consumptions_warehouse_id",
        "feed_raw_consumptions",
        ["warehouse_id"],
    )
    op.add_column(
        "feed_raw_consumptions",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_raw_consumption_created_by",
        "feed_raw_consumptions",
        "employees",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_raw_consumptions_created_by",
        "feed_raw_consumptions",
        ["created_by"],
    )

    # 3. created_by on feed_production_batches + feed_product_shipments
    op.add_column(
        "feed_production_batches",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_production_batch_created_by",
        "feed_production_batches",
        "employees",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_production_batches_created_by",
        "feed_production_batches",
        ["created_by"],
    )

    op.add_column(
        "feed_product_shipments",
        sa.Column("created_by", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_feed_product_shipment_created_by",
        "feed_product_shipments",
        "employees",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_feed_product_shipments_created_by",
        "feed_product_shipments",
        ["created_by"],
    )

    # 4. feed_production_quality_checks
    op.create_table(
        "feed_production_quality_checks",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("production_batch_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_feed_production_quality_check_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_feed_production_quality_check_department",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["production_batch_id"],
            ["feed_production_batches.id"],
            name="fk_feed_production_quality_check_batch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["inspector_id"],
            ["employees.id"],
            name="fk_feed_production_quality_check_inspector",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'passed', 'failed')",
            name="ck_feed_production_quality_check_status",
        ),
        sa.CheckConstraint(
            "grade IS NULL OR grade IN ('first', 'second', 'mixed', 'premium', 'rejected')",
            name="ck_feed_production_quality_check_grade",
        ),
    )
    op.create_index(
        "ix_feed_production_quality_checks_organization_id",
        "feed_production_quality_checks",
        ["organization_id"],
    )
    op.create_index(
        "ix_feed_production_quality_checks_department_id",
        "feed_production_quality_checks",
        ["department_id"],
    )
    op.create_index(
        "ix_feed_production_quality_checks_batch_id",
        "feed_production_quality_checks",
        ["production_batch_id"],
    )
    op.create_index(
        "ix_feed_production_quality_checks_checked_on",
        "feed_production_quality_checks",
        ["checked_on"],
    )
    op.create_index(
        "ix_feed_production_quality_checks_status",
        "feed_production_quality_checks",
        ["status"],
    )
    op.create_index(
        "ix_feed_production_quality_checks_inspector_id",
        "feed_production_quality_checks",
        ["inspector_id"],
    )

    # 5. feed_monthly_analytics
    op.create_table(
        "feed_monthly_analytics",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("feed_type_id", sa.UUID(), nullable=True),
        sa.Column("month_start", sa.Date(), nullable=False),
        sa.Column("raw_arrivals_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("raw_consumptions_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("produced_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("shipped_kg", sa.Numeric(16, 3), nullable=False, server_default="0"),
        sa.Column("shipped_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("purchased_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("quality_passed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_pending_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False),
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
            name="fk_feed_monthly_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name="fk_feed_monthly_department",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["feed_type_id"],
            ["feed_types.id"],
            name="fk_feed_monthly_feed_type",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "department_id",
            "feed_type_id",
            "month_start",
            name="uq_feed_monthly_org_dept_type_month",
        ),
        sa.CheckConstraint("raw_arrivals_kg >= 0", name="ck_feed_monthly_raw_arrivals_non_negative"),
        sa.CheckConstraint("raw_consumptions_kg >= 0", name="ck_feed_monthly_raw_consumptions_non_negative"),
        sa.CheckConstraint("produced_kg >= 0", name="ck_feed_monthly_produced_non_negative"),
        sa.CheckConstraint("shipped_kg >= 0", name="ck_feed_monthly_shipped_non_negative"),
        sa.CheckConstraint("shipped_amount >= 0", name="ck_feed_monthly_shipped_amount_non_negative"),
        sa.CheckConstraint("purchased_amount >= 0", name="ck_feed_monthly_purchased_amount_non_negative"),
        sa.CheckConstraint("quality_passed_count >= 0", name="ck_feed_monthly_quality_passed_non_negative"),
        sa.CheckConstraint("quality_failed_count >= 0", name="ck_feed_monthly_quality_failed_non_negative"),
        sa.CheckConstraint("quality_pending_count >= 0", name="ck_feed_monthly_quality_pending_non_negative"),
    )
    op.create_index(
        "ix_feed_monthly_analytics_organization_id",
        "feed_monthly_analytics",
        ["organization_id"],
    )
    op.create_index(
        "ix_feed_monthly_analytics_department_id",
        "feed_monthly_analytics",
        ["department_id"],
    )
    op.create_index(
        "ix_feed_monthly_analytics_feed_type_id",
        "feed_monthly_analytics",
        ["feed_type_id"],
    )
    op.create_index(
        "ix_feed_monthly_analytics_month_start",
        "feed_monthly_analytics",
        ["month_start"],
    )

    # 6. Activate existing raw-arrivals/raw-consumptions workspace_resources
    #    (fixtures had them as is_head_visible=false, is_active=false).
    op.execute(
        """
        UPDATE workspace_resources
        SET is_head_visible = TRUE, is_active = TRUE, updated_at = now()
        WHERE module_key = 'feed'
          AND key IN ('raw-arrivals', 'raw-consumptions')
        """
    )

    # 7. Seed workspace resources for quality-checks and monthly-analytics.
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, permission_prefix,
            sort_order, is_head_visible, is_active,
            created_at, updated_at
        ) VALUES
            (
                '32000000-0000-0000-0000-000000000190',
                'feed',
                'quality-checks',
                'Контроль качества',
                'quality-checks',
                'feed_production_quality_check',
                55,
                TRUE,
                TRUE,
                now(), now()
            ),
            (
                '32000000-0000-0000-0000-000000000191',
                'feed',
                'monthly-analytics',
                'Помесячная аналитика',
                'monthly-analytics',
                'feed_monthly_analytics',
                85,
                TRUE,
                TRUE,
                now(), now()
            )
        ON CONFLICT (module_key, key) DO NOTHING
        """
    )

    # 8. Seed permissions for every organization.
    for resource, prefix in (
        ("feed_production_quality_check", "feed_production_quality_check"),
        ("feed_monthly_analytics", "feed_monthly_analytics"),
        # raw_arrival / raw_consumption permissions were previously seeded
        # but let's re-ensure they exist in case orgs were created since.
        ("feed_raw_arrival", "feed_raw_arrival"),
        ("feed_raw_consumption", "feed_raw_consumption"),
    ):
        op.execute(
            f"""
            INSERT INTO permissions (
                id, organization_id, code, resource, action, description, is_active,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                o.id,
                '{prefix}.' || act.code,
                '{resource}',
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
                  AND p.code = '{prefix}.' || act.code
            )
            """
        )

        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r
            JOIN permissions p ON p.organization_id = r.organization_id
            WHERE r.slug IN ('admin', 'manager')
              AND p.code LIKE '{prefix}.%'
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
            """
        )


def downgrade() -> None:
    # Remove seeded permissions.
    for prefix in (
        "feed_monthly_analytics",
        "feed_production_quality_check",
    ):
        op.execute(
            f"DELETE FROM role_permissions WHERE permission_id IN ("
            f"SELECT id FROM permissions WHERE code LIKE '{prefix}.%')"
        )
        op.execute(f"DELETE FROM permissions WHERE code LIKE '{prefix}.%'")

    op.execute(
        "DELETE FROM workspace_resources WHERE id IN ('32000000-0000-0000-0000-000000000190', '32000000-0000-0000-0000-000000000191')"
    )

    op.drop_index(
        "ix_feed_monthly_analytics_month_start",
        table_name="feed_monthly_analytics",
    )
    op.drop_index(
        "ix_feed_monthly_analytics_feed_type_id",
        table_name="feed_monthly_analytics",
    )
    op.drop_index(
        "ix_feed_monthly_analytics_department_id",
        table_name="feed_monthly_analytics",
    )
    op.drop_index(
        "ix_feed_monthly_analytics_organization_id",
        table_name="feed_monthly_analytics",
    )
    op.drop_table("feed_monthly_analytics")

    op.drop_index(
        "ix_feed_production_quality_checks_inspector_id",
        table_name="feed_production_quality_checks",
    )
    op.drop_index(
        "ix_feed_production_quality_checks_status",
        table_name="feed_production_quality_checks",
    )
    op.drop_index(
        "ix_feed_production_quality_checks_checked_on",
        table_name="feed_production_quality_checks",
    )
    op.drop_index(
        "ix_feed_production_quality_checks_batch_id",
        table_name="feed_production_quality_checks",
    )
    op.drop_index(
        "ix_feed_production_quality_checks_department_id",
        table_name="feed_production_quality_checks",
    )
    op.drop_index(
        "ix_feed_production_quality_checks_organization_id",
        table_name="feed_production_quality_checks",
    )
    op.drop_table("feed_production_quality_checks")

    op.drop_index(
        "ix_feed_product_shipments_created_by",
        table_name="feed_product_shipments",
    )
    op.drop_constraint(
        "fk_feed_product_shipment_created_by",
        "feed_product_shipments",
        type_="foreignkey",
    )
    op.drop_column("feed_product_shipments", "created_by")

    op.drop_index(
        "ix_feed_production_batches_created_by",
        table_name="feed_production_batches",
    )
    op.drop_constraint(
        "fk_feed_production_batch_created_by",
        "feed_production_batches",
        type_="foreignkey",
    )
    op.drop_column("feed_production_batches", "created_by")

    op.drop_index(
        "ix_feed_raw_consumptions_created_by",
        table_name="feed_raw_consumptions",
    )
    op.drop_constraint(
        "fk_feed_raw_consumption_created_by",
        "feed_raw_consumptions",
        type_="foreignkey",
    )
    op.drop_column("feed_raw_consumptions", "created_by")

    op.drop_index(
        "ix_feed_raw_consumptions_warehouse_id",
        table_name="feed_raw_consumptions",
    )
    op.drop_constraint(
        "fk_feed_raw_consumption_warehouse",
        "feed_raw_consumptions",
        type_="foreignkey",
    )
    op.drop_column("feed_raw_consumptions", "warehouse_id")

    op.drop_index(
        "ix_feed_raw_arrivals_created_by",
        table_name="feed_raw_arrivals",
    )
    op.drop_constraint(
        "fk_feed_raw_arrival_created_by",
        "feed_raw_arrivals",
        type_="foreignkey",
    )
    op.drop_column("feed_raw_arrivals", "created_by")

    op.drop_index(
        "ix_feed_raw_arrivals_warehouse_id",
        table_name="feed_raw_arrivals",
    )
    op.drop_constraint(
        "fk_feed_raw_arrival_warehouse",
        "feed_raw_arrivals",
        type_="foreignkey",
    )
    op.drop_column("feed_raw_arrivals", "warehouse_id")
