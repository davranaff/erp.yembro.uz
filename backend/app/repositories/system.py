from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from app.repositories.base import BaseRepository, QueryBuilderResult


class AuditLogRepository(BaseRepository[dict[str, object]]):
    table = "audit_logs"

    def _changed_range(
        self,
        *,
        changed_from: datetime | None = None,
        changed_to: datetime | None = None,
        start: int = 1,
    ) -> QueryBuilderResult:
        clauses: list[str] = []
        params: list[Any] = []
        cursor = start

        if changed_from is not None:
            clauses.append(f"{self._column('changed_at')} >= ${cursor}")
            params.append(changed_from)
            cursor += 1

        if changed_to is not None:
            clauses.append(f"{self._column('changed_at')} <= ${cursor}")
            params.append(changed_to)
            cursor += 1

        if not clauses:
            return QueryBuilderResult("", [])

        return QueryBuilderResult(" AND ".join(clauses), params)

    async def count_filtered(
        self,
        filters: dict[str, Any] | None = None,
        *,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
        changed_from: datetime | None = None,
        changed_to: datetime | None = None,
    ) -> int:
        where_filters = self._where(filters)
        changed_range = self._changed_range(
            changed_from=changed_from,
            changed_to=changed_to,
            start=len(where_filters.params) + 1,
        )
        search_builder = self._search(
            search,
            search_columns,
            start=len(where_filters.params) + len(changed_range.params) + 1,
        )
        builder = self._combine_clauses(where_filters, changed_range, search_builder)
        query = f"SELECT COUNT(*) AS total FROM {self._column(self.table)}{builder.query}"
        row = await self.db.fetchrow(query, *builder.params)
        return int(row["total"]) if row is not None else 0

    async def list_filtered(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
        changed_from: datetime | None = None,
        changed_to: datetime | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | Sequence[str] | None = None,
    ) -> list[dict[str, object]]:
        where_filters = self._where(filters)
        changed_range = self._changed_range(
            changed_from=changed_from,
            changed_to=changed_to,
            start=len(where_filters.params) + 1,
        )
        search_builder = self._search(
            search,
            search_columns,
            start=len(where_filters.params) + len(changed_range.params) + 1,
        )
        where = self._combine_clauses(where_filters, changed_range, search_builder)
        order_sql = self._order(order_by)
        limit_sql, limit_params = self._limit_offset(
            limit=limit,
            offset=offset,
            start=len(where.params) + 1,
        )
        query = (
            f"SELECT * FROM {self._column(self.table)}"
            f"{where.query}{order_sql}{limit_sql}"
        )
        rows = await self.db.fetch(query, *(where.params + limit_params))
        return [dict(row) for row in rows]


__all__ = ["AuditLogRepository"]
