"""Factory: flock expenses, vaccination plans, cost fields

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Cost fields ---
    op.add_column("factory_daily_logs", sa.Column("feed_cost", sa.Numeric(16, 2), nullable=True))
    op.add_column("factory_medicine_usages", sa.Column("unit_cost", sa.Numeric(16, 2), nullable=True))
    op.add_column("factory_medicine_usages", sa.Column("total_cost", sa.Numeric(16, 2), nullable=True))

    # --- 2. Factory flock expenses ---
    op.create_table(
        "factory_flock_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("flock_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("factory_flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="UZS"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_factory_flock_expense_amount_positive"),
        sa.CheckConstraint(
            "category IN ('feed', 'medicine', 'electricity', 'heating', 'labor', 'transport', 'cleaning', 'other')",
            name="ck_factory_flock_expense_category_valid",
        ),
    )
    op.create_index("ix_factory_flock_expenses_organization_id", "factory_flock_expenses", ["organization_id"])
    op.create_index("ix_factory_flock_expenses_department_id", "factory_flock_expenses", ["department_id"])
    op.create_index("ix_factory_flock_expenses_flock_id", "factory_flock_expenses", ["flock_id"])
    op.create_index("ix_factory_flock_expenses_expense_date", "factory_flock_expenses", ["expense_date"])
    op.create_index("ix_factory_flock_expenses_category", "factory_flock_expenses", ["category"])

    # --- 3. Factory vaccination plans ---
    op.create_table(
        "factory_vaccination_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("flock_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("factory_flocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("medicine_type_id", postgresql.UUID(as_uuid=True),
                   sa.ForeignKey("medicine_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("day_of_life", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("is_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("day_of_life > 0", name="ck_factory_vaccination_plan_day_positive"),
    )
    op.create_index("ix_factory_vaccination_plans_organization_id", "factory_vaccination_plans", ["organization_id"])
    op.create_index("ix_factory_vaccination_plans_department_id", "factory_vaccination_plans", ["department_id"])
    op.create_index("ix_factory_vaccination_plans_flock_id", "factory_vaccination_plans", ["flock_id"])
    op.create_index("ix_factory_vaccination_plans_medicine_type_id", "factory_vaccination_plans", ["medicine_type_id"])
    op.create_index("ix_factory_vaccination_plans_planned_date", "factory_vaccination_plans", ["planned_date"])

    # --- 4. Permissions ---
    for resource in ("factory_flock_expense", "factory_vaccination_plan"):
        op.execute(
            f"""
            INSERT INTO permissions (id, organization_id, code, resource, action, description, is_active)
            SELECT
                gen_random_uuid(),
                o.id,
                '{resource}.' || act.code,
                '{resource}',
                act.code,
                act.description,
                true
            FROM organizations o
            CROSS JOIN (
                VALUES
                    ('read',   'Просмотр'),
                    ('create', 'Создание'),
                    ('write',  'Редактирование'),
                    ('delete', 'Удаление')
            ) AS act(code, description)
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions p
                WHERE p.organization_id = o.id
                  AND p.code = '{resource}.' || act.code
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
          AND (p.code LIKE 'factory_flock_expense.%' OR p.code LIKE 'factory_vaccination_plan.%')
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code LIKE 'factory_flock_expense.%' OR code LIKE 'factory_vaccination_plan.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'factory_flock_expense.%' OR code LIKE 'factory_vaccination_plan.%'")

    op.drop_table("factory_vaccination_plans")
    op.drop_table("factory_flock_expenses")

    op.drop_column("factory_medicine_usages", "total_cost")
    op.drop_column("factory_medicine_usages", "unit_cost")
    op.drop_column("factory_daily_logs", "feed_cost")
