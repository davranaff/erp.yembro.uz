"""telegram recipients and admin alerts

Revision ID: f6e7d8c9b0a1
Revises: c2d4e6f8a9b0
Create Date: 2026-04-16 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f6e7d8c9b0a1"
down_revision = "c2d4e6f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_recipients",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=80), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=80), nullable=False),
        sa.Column("telegram_username", sa.String(length=255), nullable=True),
        sa.Column("telegram_first_name", sa.String(length=255), nullable=True),
        sa.Column("telegram_last_name", sa.String(length=255), nullable=True),
        sa.Column("telegram_language_code", sa.String(length=32), nullable=True),
        sa.Column("chat_type", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_chat_id", name="uq_telegram_recipients_telegram_chat_id"),
        sa.UniqueConstraint("telegram_user_id", name="uq_telegram_recipients_telegram_user_id"),
    )
    op.create_index(op.f("ix_telegram_recipients_id"), "telegram_recipients", ["id"], unique=False)
    op.create_index(
        op.f("ix_telegram_recipients_organization_id"),
        "telegram_recipients",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_telegram_recipients_user_id"), "telegram_recipients", ["user_id"], unique=False)
    op.create_index(
        "ix_telegram_recipients_active_org_user",
        "telegram_recipients",
        ["organization_id", "user_id", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_recipients_active_org_user", table_name="telegram_recipients")
    op.drop_index(op.f("ix_telegram_recipients_user_id"), table_name="telegram_recipients")
    op.drop_index(op.f("ix_telegram_recipients_organization_id"), table_name="telegram_recipients")
    op.drop_index(op.f("ix_telegram_recipients_id"), table_name="telegram_recipients")
    op.drop_table("telegram_recipients")
