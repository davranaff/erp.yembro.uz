"""feed consumptions

Revision ID: b6d3f4a1290c
Revises: 8c9c9b5c40ab
Create Date: 2026-03-19 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b6d3f4a1290c"
down_revision = "8c9c9b5c40ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_consumptions",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("poultry_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feed_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumed_on", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(16, 3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False, server_default="kg"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_feed_consumption_quantity_positive"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["feed_type_id"], ["feed_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["poultry_type_id"], ["poultry_types.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feed_consumptions_consumed_on"), "feed_consumptions", ["consumed_on"], unique=False)
    op.create_index(op.f("ix_feed_consumptions_department_id"), "feed_consumptions", ["department_id"], unique=False)
    op.create_index(op.f("ix_feed_consumptions_feed_type_id"), "feed_consumptions", ["feed_type_id"], unique=False)
    op.create_index(op.f("ix_feed_consumptions_organization_id"), "feed_consumptions", ["organization_id"], unique=False)
    op.create_index(op.f("ix_feed_consumptions_poultry_type_id"), "feed_consumptions", ["poultry_type_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_feed_consumptions_poultry_type_id"), table_name="feed_consumptions")
    op.drop_index(op.f("ix_feed_consumptions_organization_id"), table_name="feed_consumptions")
    op.drop_index(op.f("ix_feed_consumptions_feed_type_id"), table_name="feed_consumptions")
    op.drop_index(op.f("ix_feed_consumptions_department_id"), table_name="feed_consumptions")
    op.drop_index(op.f("ix_feed_consumptions_consumed_on"), table_name="feed_consumptions")
    op.drop_table("feed_consumptions")
