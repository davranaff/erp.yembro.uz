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


class TelegramRecipientRepository(BaseRepository[dict[str, object]]):
    table = "telegram_recipients"

    async def get_by_telegram_account(
        self,
        *,
        telegram_user_id: str,
        telegram_chat_id: str,
    ) -> dict[str, object] | None:
        row = await self.db.fetchrow(
            """
            SELECT *
            FROM telegram_recipients
            WHERE telegram_user_id = $1
               OR telegram_chat_id = $2
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT 1
            """,
            telegram_user_id,
            telegram_chat_id,
        )
        return dict(row) if row is not None else None

    async def deactivate_other_bindings_for_user(
        self,
        *,
        user_id: str,
        keep_id: str | None = None,
        updated_at: datetime,
    ) -> list[dict[str, object]]:
        if keep_id:
            rows = await self.db.fetch(
                """
                UPDATE telegram_recipients
                SET is_active = $1,
                    updated_at = $2
                WHERE user_id = $3
                  AND id <> $4
                  AND is_active = true
                RETURNING *
                """,
                False,
                updated_at,
                user_id,
                keep_id,
            )
        else:
            rows = await self.db.fetch(
                """
                UPDATE telegram_recipients
                SET is_active = $1,
                    updated_at = $2
                WHERE user_id = $3
                  AND is_active = true
                RETURNING *
                """,
                False,
                updated_at,
                user_id,
            )
        return [dict(row) for row in rows]

    async def list_active_admin_recipients(
        self,
        *,
        organization_id: str,
    ) -> list[dict[str, object]]:
        rows = await self.db.fetch(
            """
            SELECT DISTINCT
                tr.id,
                tr.telegram_chat_id,
                tr.telegram_user_id,
                tr.user_id,
                tr.organization_id,
                e.organization_key AS employee_username,
                e.first_name AS employee_first_name,
                e.last_name AS employee_last_name
            FROM telegram_recipients AS tr
            INNER JOIN employees AS e
              ON e.id = tr.user_id
            INNER JOIN employee_roles AS er
              ON er.employee_id = e.id
            INNER JOIN roles AS r
              ON r.id = er.role_id
            WHERE tr.organization_id = $1
              AND tr.is_active = true
              AND e.is_active = true
              AND r.is_active = true
              AND lower(r.slug) = 'admin'
            ORDER BY tr.id
            """,
            organization_id,
        )
        return [dict(row) for row in rows]


__all__ = ["AuditLogRepository", "TelegramRecipientRepository"]
