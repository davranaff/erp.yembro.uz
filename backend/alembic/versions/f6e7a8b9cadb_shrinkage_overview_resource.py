"""Register the Feed / Shrinkage Overview workspace resource

The overview is a read-only view ("было X — сейчас Y") over the
``feed_lot_shrinkage_state`` data, with auto-apply on each view. It
surfaces as a sibling menu item to the Profiles CRUD under the Feed
module. Permissions are reused from ``feed_shrinkage_run`` (the read
side already exists).

Revision ID: f6e7a8b9cadb
Revises: e5d6f7a8b9ca
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "f6e7a8b9cadb"
down_revision = "e5d6f7a8b9ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, description, permission_prefix,
            sort_order, is_head_visible, is_active, created_at, updated_at
        )
        VALUES (
            gen_random_uuid(),
            'feed',
            'shrinkage-overview',
            'Обзор усушки',
            'shrinkage-overview',
            'Автоматический обзор по партиям: было на складе — сейчас с учётом усушки.',
            'feed_shrinkage_run',
            96,
            true,
            true,
            now(),
            now()
        )
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM workspace_resources WHERE key = 'shrinkage-overview'"
    )
