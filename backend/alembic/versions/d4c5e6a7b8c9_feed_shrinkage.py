"""Feed shrinkage profiles + lot state + 'shrinkage' movement kind

Adds the two tables the Feed Shrinkage spec (v1) asks for:

* ``feed_shrinkage_profiles`` — per-ingredient / per-feed-type rules
  (``N% every M days``, optional ``warehouse_id`` scope, optional
  ``max_total_percent`` / ``stop_after_days`` / ``starts_after_days``).
* ``feed_lot_shrinkage_state`` — one row per lot (raw arrival or
  production batch) capturing the accumulated shrinkage, the last
  applied date, and a freeze flag when the cap is reached.

Also extends the ``stock_movements.movement_kind`` CHECK constraint to
accept ``'shrinkage'``, which is the kind the shrinkage worker writes
when it decrements a lot.

The usual CRUD permissions (``feed_shrinkage_profile.{read, create,
write, delete}``) plus run permissions (``feed_shrinkage_run.{read,
execute}``) are inserted and attached to the ``admin`` and
``manager_feed`` role templates.

Revision ID: d4c5e6a7b8c9
Revises: b2c3d4e5f6a8
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "d4c5e6a7b8c9"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feed_shrinkage_profiles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(length=24), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=True),
        sa.Column("feed_type_id", sa.UUID(), nullable=True),
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=False),
        sa.Column("percent_per_period", sa.Numeric(6, 3), nullable=False),
        sa.Column("max_total_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("stop_after_days", sa.Integer(), nullable=True),
        sa.Column(
            "starts_after_days",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["feed_ingredients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["feed_type_id"], ["feed_types.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "target_type IN ('ingredient', 'feed_type')",
            name="ck_feed_shrinkage_profile_target_type",
        ),
        sa.CheckConstraint(
            "(target_type = 'ingredient' AND ingredient_id IS NOT NULL "
            "AND feed_type_id IS NULL) "
            "OR (target_type = 'feed_type' AND feed_type_id IS NOT NULL "
            "AND ingredient_id IS NULL)",
            name="ck_feed_shrinkage_profile_target_exactly_one",
        ),
        sa.CheckConstraint(
            "period_days > 0",
            name="ck_feed_shrinkage_profile_period_positive",
        ),
        sa.CheckConstraint(
            "percent_per_period >= 0 AND percent_per_period <= 100",
            name="ck_feed_shrinkage_profile_percent_bounded",
        ),
        sa.CheckConstraint(
            "max_total_percent IS NULL OR "
            "(max_total_percent >= 0 AND max_total_percent <= 100)",
            name="ck_feed_shrinkage_profile_max_percent_bounded",
        ),
        sa.CheckConstraint(
            "stop_after_days IS NULL OR stop_after_days > 0",
            name="ck_feed_shrinkage_profile_stop_after_positive",
        ),
        sa.CheckConstraint(
            "starts_after_days >= 0",
            name="ck_feed_shrinkage_profile_starts_after_non_negative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feed_shrinkage_profiles_organization_id",
        "feed_shrinkage_profiles",
        ["organization_id"],
    )
    op.create_index(
        "ix_feed_shrinkage_profiles_ingredient_id",
        "feed_shrinkage_profiles",
        ["ingredient_id"],
    )
    op.create_index(
        "ix_feed_shrinkage_profiles_feed_type_id",
        "feed_shrinkage_profiles",
        ["feed_type_id"],
    )
    op.create_index(
        "ix_feed_shrinkage_profiles_warehouse_id",
        "feed_shrinkage_profiles",
        ["warehouse_id"],
    )
    # Partial unique indexes — NULL warehouse_id has to be distinct from
    # a real UUID per the spec. Splitting into ingredient/feed_type
    # variants lets us enforce uniqueness in both cases without relying
    # on Postgres' NULL-aware UNIQUE extensions.
    op.execute(
        "CREATE UNIQUE INDEX uq_feed_shrinkage_profile_ingredient_wh "
        "ON feed_shrinkage_profiles "
        "(organization_id, ingredient_id, warehouse_id) "
        "WHERE target_type = 'ingredient' AND warehouse_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_feed_shrinkage_profile_ingredient_any "
        "ON feed_shrinkage_profiles "
        "(organization_id, ingredient_id) "
        "WHERE target_type = 'ingredient' AND warehouse_id IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_feed_shrinkage_profile_feed_type_wh "
        "ON feed_shrinkage_profiles "
        "(organization_id, feed_type_id, warehouse_id) "
        "WHERE target_type = 'feed_type' AND warehouse_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_feed_shrinkage_profile_feed_type_any "
        "ON feed_shrinkage_profiles "
        "(organization_id, feed_type_id) "
        "WHERE target_type = 'feed_type' AND warehouse_id IS NULL"
    )

    op.create_table(
        "feed_lot_shrinkage_state",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("lot_type", sa.String(length=24), nullable=False),
        sa.Column("lot_id", sa.UUID(), nullable=False),
        sa.Column("profile_id", sa.UUID(), nullable=False),
        sa.Column("initial_quantity", sa.Numeric(16, 3), nullable=False),
        sa.Column(
            "accumulated_loss",
            sa.Numeric(16, 3),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_applied_on", sa.Date(), nullable=True),
        sa.Column(
            "is_frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["feed_shrinkage_profiles.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "lot_type IN ('raw_arrival', 'production_batch')",
            name="ck_feed_lot_shrinkage_state_lot_type",
        ),
        sa.CheckConstraint(
            "initial_quantity > 0",
            name="ck_feed_lot_shrinkage_state_initial_positive",
        ),
        sa.CheckConstraint(
            "accumulated_loss >= 0 AND accumulated_loss <= initial_quantity",
            name="ck_feed_lot_shrinkage_state_loss_bounded",
        ),
        sa.UniqueConstraint(
            "lot_type", "lot_id", name="uq_feed_lot_shrinkage_state_lot"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feed_lot_shrinkage_state_organization_id",
        "feed_lot_shrinkage_state",
        ["organization_id"],
    )
    op.create_index(
        "ix_feed_lot_shrinkage_state_profile_id",
        "feed_lot_shrinkage_state",
        ["profile_id"],
    )
    op.create_index(
        "ix_feed_lot_shrinkage_state_scan",
        "feed_lot_shrinkage_state",
        ["organization_id", "lot_type", "is_frozen"],
    )

    # ------- extend stock_movements kind CHECK -------
    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS ck_stock_movement_kind_allowed"
    )
    op.execute(
        "ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movement_kind_allowed "
        "CHECK (movement_kind IN "
        "('incoming', 'outgoing', 'transfer_in', 'transfer_out', "
        "'adjustment_in', 'adjustment_out', 'shrinkage'))"
    )

    # ------- permissions (per-organization rows matching the existing shape) -------
    op.execute(
        """
        INSERT INTO permissions (id, organization_id, code, resource, action, description, is_active)
        SELECT gen_random_uuid(), o.id, data.code, data.resource, data.action, data.description, true
        FROM organizations o
        CROSS JOIN (VALUES
            ('feed_shrinkage_profile.read',   'feed_shrinkage_profile', 'read',   'Прочитать профиль усушки кормов'),
            ('feed_shrinkage_profile.list',   'feed_shrinkage_profile', 'list',   'Список профилей усушки кормов'),
            ('feed_shrinkage_profile.create', 'feed_shrinkage_profile', 'create', 'Создать профиль усушки кормов'),
            ('feed_shrinkage_profile.write',  'feed_shrinkage_profile', 'write',  'Редактировать профиль усушки кормов'),
            ('feed_shrinkage_profile.delete', 'feed_shrinkage_profile', 'delete', 'Удалить профиль усушки кормов'),
            ('feed_shrinkage_run.read',       'feed_shrinkage_run',     'read',   'Прочитать состояние усушки по партиям'),
            ('feed_shrinkage_run.execute',    'feed_shrinkage_run',     'execute','Запустить/сбросить расчёт усушки')
        ) AS data(code, resource, action, description)
        ON CONFLICT DO NOTHING
        """
    )

    # Attach the fresh permissions to admin + manager_feed role templates
    # in every organization that already has those roles.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        INNER JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager_feed')
          AND p.code LIKE 'feed_shrinkage_%'
        ON CONFLICT DO NOTHING
        """
    )

    # ------- workspace_resources: surface the new profiles CRUD -------
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, description, permission_prefix,
            sort_order, is_head_visible, is_active, created_at, updated_at
        )
        VALUES (
            gen_random_uuid(),
            'feed',
            'shrinkage-profiles',
            'Профили усушки',
            'shrinkage-profiles',
            'Правила списания веса сырья и готового корма на испарение и потери при хранении',
            'feed_shrinkage_profile',
            95,
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
        "DELETE FROM workspace_resources WHERE key = 'shrinkage-profiles'"
    )
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'feed_shrinkage_%')"
    )
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'feed_shrinkage_%'"
    )
    op.execute(
        "ALTER TABLE stock_movements DROP CONSTRAINT IF EXISTS ck_stock_movement_kind_allowed"
    )
    op.execute(
        "ALTER TABLE stock_movements ADD CONSTRAINT ck_stock_movement_kind_allowed "
        "CHECK (movement_kind IN "
        "('incoming', 'outgoing', 'transfer_in', 'transfer_out', "
        "'adjustment_in', 'adjustment_out'))"
    )
    op.drop_index(
        "ix_feed_lot_shrinkage_state_scan", table_name="feed_lot_shrinkage_state"
    )
    op.drop_index(
        "ix_feed_lot_shrinkage_state_profile_id",
        table_name="feed_lot_shrinkage_state",
    )
    op.drop_index(
        "ix_feed_lot_shrinkage_state_organization_id",
        table_name="feed_lot_shrinkage_state",
    )
    op.drop_table("feed_lot_shrinkage_state")
    op.execute("DROP INDEX IF EXISTS uq_feed_shrinkage_profile_feed_type_any")
    op.execute("DROP INDEX IF EXISTS uq_feed_shrinkage_profile_feed_type_wh")
    op.execute("DROP INDEX IF EXISTS uq_feed_shrinkage_profile_ingredient_any")
    op.execute("DROP INDEX IF EXISTS uq_feed_shrinkage_profile_ingredient_wh")
    op.drop_index(
        "ix_feed_shrinkage_profiles_warehouse_id",
        table_name="feed_shrinkage_profiles",
    )
    op.drop_index(
        "ix_feed_shrinkage_profiles_feed_type_id",
        table_name="feed_shrinkage_profiles",
    )
    op.drop_index(
        "ix_feed_shrinkage_profiles_ingredient_id",
        table_name="feed_shrinkage_profiles",
    )
    op.drop_index(
        "ix_feed_shrinkage_profiles_organization_id",
        table_name="feed_shrinkage_profiles",
    )
    op.drop_table("feed_shrinkage_profiles")
