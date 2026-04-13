"""medicine batch qr and attachments

Revision ID: f4a5b6c7d8e9
Revises: e1a2b3c4d5e6
Create Date: 2026-04-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f4a5b6c7d8e9"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("medicine_batches", sa.Column("qr_public_token", sa.Text(), nullable=True))
    op.add_column("medicine_batches", sa.Column("qr_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("medicine_batches", sa.Column("qr_generated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("medicine_batches", sa.Column("qr_image_key", sa.String(length=1024), nullable=True))
    op.add_column("medicine_batches", sa.Column("qr_image_content_type", sa.String(length=120), nullable=True))
    op.add_column("medicine_batches", sa.Column("qr_image_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("medicine_batches", sa.Column("attachment_key", sa.String(length=1024), nullable=True))
    op.add_column("medicine_batches", sa.Column("attachment_name", sa.String(length=255), nullable=True))
    op.add_column("medicine_batches", sa.Column("attachment_content_type", sa.String(length=120), nullable=True))
    op.add_column("medicine_batches", sa.Column("attachment_size_bytes", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_medicine_batches_qr_public_token"), "medicine_batches", ["qr_public_token"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_medicine_batches_qr_public_token"), table_name="medicine_batches")
    op.drop_column("medicine_batches", "attachment_size_bytes")
    op.drop_column("medicine_batches", "attachment_content_type")
    op.drop_column("medicine_batches", "attachment_name")
    op.drop_column("medicine_batches", "attachment_key")
    op.drop_column("medicine_batches", "qr_image_size_bytes")
    op.drop_column("medicine_batches", "qr_image_content_type")
    op.drop_column("medicine_batches", "qr_image_key")
    op.drop_column("medicine_batches", "qr_generated_at")
    op.drop_column("medicine_batches", "qr_token_expires_at")
    op.drop_column("medicine_batches", "qr_public_token")
