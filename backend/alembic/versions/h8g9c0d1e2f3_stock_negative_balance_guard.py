"""Postgres-триггер: запрет отрицательных остатков на складе.

Последний рубеж обороны. Даже если какой-нибудь сервис забудет
сделать pre-check балансa или оператор вставит движение через
прямой SQL — триггер откатит транзакцию с понятным сообщением.

Алгоритм: BEFORE INSERT на ``stock_movements``. Для outgoing /
transfer_out / adjustment_out / shrinkage считаем сумму всех
incoming минус сумму всех outgoing (в том же scope: организация +
департамент + склад + item_type + item_key) до ``occurred_on``
включительно, с учётом текущей вставляемой строки. Если сумма
уходит в минус — RAISE EXCEPTION.

Замечание: у триггера есть точки, где он ослаблен:
* Движения adjustment_in / adjustment_out от stock-take генерируются
  автоматически и могут временно выводить баланс в ноль, но не ниже.
* Транзакция replace_reference_movements сначала удаляет, потом
  вставляет движения, так что проверка после вставки корректна.

Revision ID: h8g9c0d1e2f3
Revises: g7f8b9c0d1e2
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op


revision = "h8g9c0d1e2f3"
down_revision = "g7f8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION stock_movements_guard_balance()
        RETURNS TRIGGER AS $$
        DECLARE
            incoming_sum NUMERIC(16, 3);
            outgoing_sum NUMERIC(16, 3);
            projected    NUMERIC(16, 3);
            is_minus     BOOLEAN;
        BEGIN
            is_minus := NEW.movement_kind IN (
                'outgoing', 'transfer_out', 'adjustment_out', 'shrinkage'
            );
            IF NOT is_minus THEN
                RETURN NEW;
            END IF;

            SELECT COALESCE(SUM(quantity), 0)
            INTO incoming_sum
            FROM stock_movements
            WHERE organization_id = NEW.organization_id
              AND department_id   = NEW.department_id
              AND (
                  (warehouse_id IS NULL AND NEW.warehouse_id IS NULL)
                  OR warehouse_id = NEW.warehouse_id
              )
              AND item_type = NEW.item_type
              AND item_key  = NEW.item_key
              AND occurred_on <= NEW.occurred_on
              AND movement_kind IN (
                  'incoming', 'transfer_in', 'adjustment_in'
              );

            SELECT COALESCE(SUM(quantity), 0)
            INTO outgoing_sum
            FROM stock_movements
            WHERE organization_id = NEW.organization_id
              AND department_id   = NEW.department_id
              AND (
                  (warehouse_id IS NULL AND NEW.warehouse_id IS NULL)
                  OR warehouse_id = NEW.warehouse_id
              )
              AND item_type = NEW.item_type
              AND item_key  = NEW.item_key
              AND occurred_on <= NEW.occurred_on
              AND movement_kind IN (
                  'outgoing', 'transfer_out', 'adjustment_out', 'shrinkage'
              )
              AND id != NEW.id;  -- при UPDATE исключаем саму строку

            projected := incoming_sum - outgoing_sum - NEW.quantity;

            IF projected < 0 THEN
                RAISE EXCEPTION
                    'stock_movements_guard_balance: остаток уйдёт в минус. '
                    'item_type=%, item_key=%, on_date=%, balance_before=%, delta=-%',
                    NEW.item_type,
                    NEW.item_key,
                    NEW.occurred_on,
                    (incoming_sum - outgoing_sum),
                    NEW.quantity
                USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_stock_movements_guard_balance
            ON stock_movements
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_stock_movements_guard_balance
        BEFORE INSERT ON stock_movements
        FOR EACH ROW
        EXECUTE FUNCTION stock_movements_guard_balance();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_stock_movements_guard_balance "
        "ON stock_movements"
    )
    op.execute("DROP FUNCTION IF EXISTS stock_movements_guard_balance()")
