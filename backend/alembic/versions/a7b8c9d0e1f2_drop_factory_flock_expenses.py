"""Drop factory_flock_expenses table (use finance module instead)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-17
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove permissions
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code LIKE 'factory_flock_expense.%')"
    )
    op.execute("DELETE FROM permissions WHERE code LIKE 'factory_flock_expense.%'")

    # Drop table
    op.drop_table("factory_flock_expenses")


def downgrade() -> None:
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
