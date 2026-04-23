"""Feed formula composition + production batch cost tracking.

Добавляет:

* таблицу ``feed_formula_ingredients`` — состав формулы (сколько чего
  на одну единицу готового корма). До этой миграции формула существовала
  только как «имя + тип корма» и никак не влияла на склад;
* колонки ``total_cost`` / ``unit_cost`` / ``cost_currency_id`` в
  ``feed_production_batches`` — себестоимость партии, которую сервис
  производства считает автоматически из цен приходов сырья;
* permissions ``feed_formula_ingredient.{read, list, create, write, delete}``
  и привязку к ролям ``admin`` + ``manager_feed``.

Миграция идемпотентная по permissions (``ON CONFLICT DO NOTHING``).

Revision ID: g7f8b9c0d1e2
Revises: f6e7a8b9cadb
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "g7f8b9c0d1e2"
down_revision = "f6e7a8b9cadb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------- feed_formula_ingredients --------------------
    op.create_table(
        "feed_formula_ingredients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("formula_id", sa.UUID(), nullable=False),
        sa.Column("ingredient_id", sa.UUID(), nullable=False),
        sa.Column("quantity_per_unit", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "unit", sa.String(length=20), nullable=False, server_default="kg"
        ),
        sa.Column("measurement_unit_id", sa.UUID(), nullable=False),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
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
            ["formula_id"], ["feed_formulas.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ingredient_id"], ["feed_ingredients.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["measurement_unit_id"], ["measurement_units.id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "quantity_per_unit > 0",
            name="ck_feed_formula_ingredient_qty_positive",
        ),
        sa.UniqueConstraint(
            "formula_id",
            "ingredient_id",
            name="uq_feed_formula_ingredient_formula_ingredient",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_feed_formula_ingredients_organization_id",
        "feed_formula_ingredients",
        ["organization_id"],
    )
    op.create_index(
        "ix_feed_formula_ingredients_formula_id",
        "feed_formula_ingredients",
        ["formula_id"],
    )
    op.create_index(
        "ix_feed_formula_ingredients_ingredient_id",
        "feed_formula_ingredients",
        ["ingredient_id"],
    )
    op.create_index(
        "ix_feed_formula_ingredients_measurement_unit_id",
        "feed_formula_ingredients",
        ["measurement_unit_id"],
    )

    # -------------------- feed_production_batches: cost fields --------------------
    op.add_column(
        "feed_production_batches",
        sa.Column(
            "total_cost",
            sa.Numeric(16, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "feed_production_batches",
        sa.Column(
            "unit_cost",
            sa.Numeric(16, 4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "feed_production_batches",
        sa.Column(
            "cost_currency_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_feed_production_batch_cost_currency",
        "feed_production_batches",
        "currencies",
        ["cost_currency_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # -------------------- permissions --------------------
    op.execute(
        """
        INSERT INTO permissions (id, organization_id, code, resource, action, description, is_active)
        SELECT gen_random_uuid(), o.id, data.code, data.resource, data.action, data.description, true
        FROM organizations o
        CROSS JOIN (VALUES
            ('feed_formula_ingredient.read',   'feed_formula_ingredient', 'read',   'Прочитать состав формулы корма'),
            ('feed_formula_ingredient.list',   'feed_formula_ingredient', 'list',   'Список состава формул'),
            ('feed_formula_ingredient.create', 'feed_formula_ingredient', 'create', 'Добавить ингредиент в формулу'),
            ('feed_formula_ingredient.write',  'feed_formula_ingredient', 'write',  'Изменить ингредиент формулы'),
            ('feed_formula_ingredient.delete', 'feed_formula_ingredient', 'delete', 'Удалить ингредиент из формулы')
        ) AS data(code, resource, action, description)
        ON CONFLICT DO NOTHING
        """
    )

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        INNER JOIN permissions p ON p.organization_id = r.organization_id
        WHERE r.slug IN ('admin', 'manager_feed')
          AND p.code LIKE 'feed_formula_ingredient.%'
        ON CONFLICT DO NOTHING
        """
    )

    # -------------------- workspace resource: surface in UI --------------------
    op.execute(
        """
        INSERT INTO workspace_resources (
            id, module_key, key, name, path, description, permission_prefix,
            sort_order, is_head_visible, is_active, created_at, updated_at
        )
        VALUES (
            gen_random_uuid(),
            'feed',
            'formula-ingredients',
            'Состав формул',
            'formula-ingredients',
            'Список ингредиентов каждой формулы корма с пропорциями. Используется для автосписания сырья при производстве.',
            'feed_formula_ingredient',
            45,
            true,
            true,
            now(),
            now()
        )
        ON CONFLICT (module_key, key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN ("
        "SELECT id FROM permissions WHERE code LIKE 'feed_formula_ingredient.%')"
    )
    op.execute(
        "DELETE FROM permissions WHERE code LIKE 'feed_formula_ingredient.%'"
    )

    op.drop_constraint(
        "fk_feed_production_batch_cost_currency",
        "feed_production_batches",
        type_="foreignkey",
    )
    op.drop_column("feed_production_batches", "cost_currency_id")
    op.drop_column("feed_production_batches", "unit_cost")
    op.drop_column("feed_production_batches", "total_cost")

    op.drop_index(
        "ix_feed_formula_ingredients_measurement_unit_id",
        table_name="feed_formula_ingredients",
    )
    op.drop_index(
        "ix_feed_formula_ingredients_ingredient_id",
        table_name="feed_formula_ingredients",
    )
    op.drop_index(
        "ix_feed_formula_ingredients_formula_id",
        table_name="feed_formula_ingredients",
    )
    op.drop_index(
        "ix_feed_formula_ingredients_organization_id",
        table_name="feed_formula_ingredients",
    )
    op.drop_table("feed_formula_ingredients")
