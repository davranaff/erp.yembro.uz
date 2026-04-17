"""Factory enhancements: medicine usages, daily log fields, client department scoping

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Add new columns to factory_daily_logs ---
    op.add_column("factory_daily_logs", sa.Column("sick_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("factory_daily_logs", sa.Column("healthy_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(
        "factory_daily_logs",
        sa.Column("feed_type_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_factory_daily_log_feed_type",
        "factory_daily_logs",
        "feed_types",
        ["feed_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint("ck_factory_daily_log_sick_non_negative", "factory_daily_logs", "sick_count >= 0")
    op.create_check_constraint("ck_factory_daily_log_healthy_non_negative", "factory_daily_logs", "healthy_count >= 0")

    # --- 2. Add department_id to clients ---
    op.add_column(
        "clients",
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_client_department",
        "clients",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_clients_department_id", "clients", ["department_id"])

    # --- 3. Create factory_medicine_usages table ---
    op.create_table(
        "factory_medicine_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "department_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "flock_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("factory_flocks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column(
            "medicine_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medicine_types.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "medicine_batch_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("medicine_batches.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("quantity", sa.Numeric(16, 3), nullable=False),
        sa.Column(
            "measurement_unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("measurement_units.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_factory_medicine_usage_quantity_positive"),
    )
    op.create_index("ix_factory_medicine_usages_organization_id", "factory_medicine_usages", ["organization_id"])
    op.create_index("ix_factory_medicine_usages_department_id", "factory_medicine_usages", ["department_id"])
    op.create_index("ix_factory_medicine_usages_flock_id", "factory_medicine_usages", ["flock_id"])
    op.create_index("ix_factory_medicine_usages_usage_date", "factory_medicine_usages", ["usage_date"])
    op.create_index("ix_factory_medicine_usages_medicine_type_id", "factory_medicine_usages", ["medicine_type_id"])
    op.create_index("ix_factory_medicine_usages_medicine_batch_id", "factory_medicine_usages", ["medicine_batch_id"])

    # --- 4. Seed permissions for factory_medicine_usage ---
    op.execute(
        """
        INSERT INTO permissions (id, organization_id, code, resource, action, description, is_active)
        SELECT
            gen_random_uuid(),
            o.id,
            'factory_medicine_usage.' || act.code,
            'factory_medicine_usage',
            act.code,
            act.description,
            true
        FROM organizations o
        CROSS JOIN (
            VALUES
                ('read',   'Просмотр расхода лекарств на фабрике'),
                ('create', 'Создание записей расхода лекарств'),
                ('write',  'Редактирование расхода лекарств'),
                ('delete', 'Удаление записей расхода лекарств')
        ) AS act(code, description)
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions p
            WHERE p.organization_id = o.id
              AND p.code = 'factory_medicine_usage.' || act.code
        )
        """
    )

    # Assign to admin and manager roles
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager')
          AND p.code LIKE 'factory_medicine_usage.%'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code LIKE 'factory_medicine_usage.%')")
    op.execute("DELETE FROM permissions WHERE code LIKE 'factory_medicine_usage.%'")

    op.drop_table("factory_medicine_usages")

    op.drop_index("ix_clients_department_id", "clients")
    op.drop_constraint("fk_client_department", "clients", type_="foreignkey")
    op.drop_column("clients", "department_id")

    op.drop_constraint("ck_factory_daily_log_healthy_non_negative", "factory_daily_logs", type_="check")
    op.drop_constraint("ck_factory_daily_log_sick_non_negative", "factory_daily_logs", type_="check")
    op.drop_constraint("fk_factory_daily_log_feed_type", "factory_daily_logs", type_="foreignkey")
    op.drop_column("factory_daily_logs", "feed_type_id")
    op.drop_column("factory_daily_logs", "healthy_count")
    op.drop_column("factory_daily_logs", "sick_count")
