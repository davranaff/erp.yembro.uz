from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from app.repositories.base import BaseRepository


class StockMovementRepository(BaseRepository[dict[str, object]]):
    table = "stock_movements"

    async def delete_by_reference(self, *, reference_table: str, reference_id: str) -> int:
        rows = await self.db.fetch(
            f"""
            DELETE FROM {self._column(self.table)}
            WHERE {self._column('reference_table')} = $1
              AND {self._column('reference_id')} = $2
            RETURNING {self._column(self.id_column)}
            """,
            reference_table,
            reference_id,
        )
        return len(rows)

    async def get_balance(
        self,
        *,
        organization_id: str,
        warehouse_id: str | None = None,
        department_id: str | None,
        item_type: str,
        item_key: str,
        as_of: date | None = None,
        exclude_reference_table: str | None = None,
        exclude_reference_id: str | None = None,
    ) -> Decimal:
        where_clauses: list[str] = [
            f"{self._column('organization_id')} = $1",
            f"{self._column('item_type')} = $2",
            f"{self._column('item_key')} = $3",
        ]
        params: list[Any] = [organization_id, item_type, item_key]
        cursor = 4

        if warehouse_id is not None:
            where_clauses.append(f"{self._column('warehouse_id')} = ${cursor}")
            params.append(warehouse_id)
            cursor += 1

        if department_id is not None:
            where_clauses.append(f"{self._column('department_id')} = ${cursor}")
            params.append(department_id)
            cursor += 1

        if as_of is not None:
            where_clauses.append(f"{self._column('occurred_on')} <= ${cursor}")
            params.append(as_of)
            cursor += 1

        if exclude_reference_table is not None and exclude_reference_id is not None:
            where_clauses.append(
                f"NOT ({self._column('reference_table')} = ${cursor} AND {self._column('reference_id')} = ${cursor + 1})"
            )
            params.append(exclude_reference_table)
            params.append(exclude_reference_id)
            cursor += 2

        row = await self.db.fetchrow(
            f"""
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN {self._column('movement_kind')} IN ('incoming', 'transfer_in', 'adjustment_in')
                        THEN {self._column('quantity')}
                        ELSE -{self._column('quantity')}
                    END
                ),
                0
            ) AS balance
            FROM {self._column(self.table)}
            WHERE {' AND '.join(where_clauses)}
            """,
            *params,
        )
        if row is None:
            return Decimal("0")
        raw_balance = row.get("balance")
        if isinstance(raw_balance, Decimal):
            return raw_balance
        if raw_balance is None:
            return Decimal("0")
        return Decimal(str(raw_balance))

    async def has_item_movements(
        self,
        *,
        organization_id: str,
        warehouse_id: str | None = None,
        department_id: str | None,
        item_type: str,
        item_key: str,
    ) -> bool:
        where_clauses = [
            f"{self._column('organization_id')} = $1",
            f"{self._column('item_type')} = $2",
            f"{self._column('item_key')} = $3",
        ]
        params: list[Any] = [organization_id, item_type, item_key]

        cursor = 4
        if warehouse_id is not None:
            where_clauses.append(f"{self._column('warehouse_id')} = ${cursor}")
            params.append(warehouse_id)
            cursor += 1

        if department_id is not None:
            where_clauses.append(f"{self._column('department_id')} = ${cursor}")
            params.append(department_id)

        row = await self.db.fetchrow(
            f"""
            SELECT 1 AS ok
            FROM {self._column(self.table)}
            WHERE {' AND '.join(where_clauses)}
            LIMIT 1
            """,
            *params,
        )
        return row is not None

    async def list_balances(
        self,
        *,
        organization_id: str,
        warehouse_id: str | None = None,
        department_id: str | None = None,
        item_type: str,
        as_of: date | None = None,
    ) -> list[dict[str, object]]:
        params: list[Any] = [organization_id, item_type]
        cursor = 3
        where_parts = [
            f"{self._column('organization_id')} = $1",
            f"{self._column('item_type')} = $2",
        ]

        if warehouse_id is not None:
            where_parts.append(f"{self._column('warehouse_id')} = ${cursor}")
            params.append(warehouse_id)
            cursor += 1

        if department_id is not None:
            where_parts.append(f"{self._column('department_id')} = ${cursor}")
            params.append(department_id)
            cursor += 1

        if as_of is not None:
            where_parts.append(f"{self._column('occurred_on')} <= ${cursor}")
            params.append(as_of)
            cursor += 1

        rows = await self.db.fetch(
            f"""
            SELECT
                {self._column('item_type')} AS item_type,
                {self._column('item_key')} AS item_key,
                COALESCE(
                    SUM(
                        CASE
                            WHEN {self._column('movement_kind')} IN ('incoming', 'transfer_in', 'adjustment_in')
                            THEN {self._column('quantity')}
                            ELSE -{self._column('quantity')}
                        END
                    ),
                    0
                ) AS balance,
                MAX({self._column('unit')}) AS unit,
                MAX({self._column('occurred_on')}) AS last_movement_on
            FROM {self._column(self.table)}
            WHERE {' AND '.join(where_parts)}
            GROUP BY {self._column('item_type')}, {self._column('item_key')}
            ORDER BY {self._column('item_key')} ASC
            """,
            *params,
        )
        return [dict(row) for row in rows]


__all__ = ["StockMovementRepository"]
