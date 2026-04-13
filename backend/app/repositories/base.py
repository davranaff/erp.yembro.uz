from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Generic, Iterable, Mapping, Sequence, TypeVar

from sqlalchemy.sql.sqltypes import Enum as SqlEnum, String, Text, Unicode, UnicodeText

from app.core.exceptions import NotFoundError, ValidationError
from app.db.pool import Database
from app.models import Base

Row = Mapping[str, Any]
RowT = TypeVar("RowT", bound=Row)
AUDIT_COLUMNS = {"created_at", "updated_at", "deleted_at"}
TEXTUAL_TYPES = (String, Text, Unicode, UnicodeText, SqlEnum)


@dataclass(slots=True)
class QueryBuilderResult:
    query: str
    params: list[Any]


class BaseRepository(ABC, Generic[RowT]):
    """Common asyncpg repository abstraction."""

    table: str
    id_column: str = "id"

    def __init__(self, db: Database) -> None:
        self.db = db

    def has_column(self, column_name: str) -> bool:
        table = Base.metadata.tables.get(self.table)
        if table is None:
            return False
        return column_name in table.columns

    def get_searchable_columns(self) -> tuple[str, ...]:
        table = Base.metadata.tables.get(self.table)
        if table is None:
            return ()

        columns: list[str] = []
        for column in table.columns:
            if (
                column.name == self.id_column
                or column.name in AUDIT_COLUMNS
                or column.name.endswith("_id")
                or column.name == "password"
            ):
                continue
            if isinstance(column.type, TEXTUAL_TYPES):
                columns.append(column.name)

        return tuple(columns)

    @staticmethod
    def _column(name: str) -> str:
        if not name:
            raise ValidationError("Column name cannot be empty")
        if '"' in name:
            raise ValidationError("Invalid column name")
        return f'"{name}"'

    def _where(self, filters: Mapping[str, Any] | None, start: int = 1) -> QueryBuilderResult:
        clauses: list[str] = []
        params: list[Any] = []

        if not filters:
            return QueryBuilderResult("", params)

        cursor = start
        for key, value in filters.items():
            if value is None:
                continue

            column = self._column(key)

            if isinstance(value, (list, tuple, set)):
                value_list = list(value)
                if not value_list:
                    clauses.append("1 = 0")
                    continue
                placeholders = ", ".join(f"${i}" for i in range(cursor, cursor + len(value_list)))
                clauses.append(f"{column} IN ({placeholders})")
                params.extend(value_list)
                cursor += len(value_list)
                continue

            clauses.append(f"{column} = ${cursor}")
            params.append(value)
            cursor += 1

        if not clauses:
            return QueryBuilderResult("", params)

        return QueryBuilderResult(" WHERE " + " AND ".join(clauses), params)

    def _search(
        self,
        search: str | None,
        columns: Sequence[str] | None,
        *,
        start: int = 1,
    ) -> QueryBuilderResult:
        normalized_search = (search or "").strip().lower()
        if not normalized_search or not columns:
            return QueryBuilderResult("", [])

        clauses: list[str] = []
        params: list[Any] = []
        cursor = start
        column_names = list(dict.fromkeys(columns))

        if "first_name" in column_names or "last_name" in column_names:
            name_parts: list[str] = []
            if "first_name" in column_names:
                name_parts.append(f"COALESCE(CAST({self._column('first_name')} AS TEXT), '')")
            if "last_name" in column_names:
                name_parts.append(f"COALESCE(CAST({self._column('last_name')} AS TEXT), '')")
            if name_parts:
                clauses.append(
                    "LOWER(TRIM(" + " || ' ' || ".join(name_parts) + f")) LIKE ${cursor}"
                )
                params.append(f"%{normalized_search}%")
                cursor += 1

        for column_name in column_names:
            column = self._column(column_name)
            clauses.append(f"LOWER(COALESCE(CAST({column} AS TEXT), '')) LIKE ${cursor}")
            params.append(f"%{normalized_search}%")
            cursor += 1

        if not clauses:
            return QueryBuilderResult("", [])

        return QueryBuilderResult("(" + " OR ".join(clauses) + ")", params)

    @staticmethod
    def _combine_clauses(*parts: QueryBuilderResult) -> QueryBuilderResult:
        clauses = [part.query.replace(" WHERE ", "", 1) for part in parts if part.query]
        params: list[Any] = []
        for part in parts:
            params.extend(part.params)

        if not clauses:
            return QueryBuilderResult("", params)

        return QueryBuilderResult(" WHERE " + " AND ".join(clauses), params)

    @staticmethod
    def _payload_keys(payload: Mapping[str, Any]) -> list[str]:
        if not payload:
            raise ValidationError("Payload cannot be empty")
        return list(payload.keys())

    @staticmethod
    def _values(payload: Mapping[str, Any]) -> list[Any]:
        return list(payload.values())

    def _set_clause(self, payload: Mapping[str, Any], start: int = 1) -> tuple[str, list[Any]]:
        assignments: list[str] = []
        values: list[Any] = []
        for index, (key, value) in enumerate(payload.items(), start=start):
            assignments.append(f"{self._column(key)} = ${index}")
            values.append(value)
        return ", ".join(assignments), values

    def _order(self, order_by: str | Sequence[str] | None) -> str:
        if not order_by:
            return ""
        if isinstance(order_by, str):
            return f" ORDER BY {self._column(order_by)}"

        columns: list[str] = []
        for item in order_by:
            if not item:
                continue
            parts = item.strip().rsplit(" ", 1)
            if len(parts) == 2 and parts[1].lower() in {"asc", "desc"}:
                columns.append(f"{self._column(parts[0])} {parts[1].upper()}")
            else:
                columns.append(self._column(item))
        return " ORDER BY " + ", ".join(columns) if columns else ""

    def _limit_offset(
        self,
        limit: int | None,
        offset: int | None,
        *,
        start: int = 1,
    ) -> tuple[str, list[Any]]:
        parts: list[str] = []
        params: list[Any] = []
        i = start

        if limit is not None:
            parts.append(f" LIMIT ${i}")
            params.append(limit)
            i += 1

        if offset is not None:
            parts.append(f" OFFSET ${i}")
            params.append(offset)
            i += 1

        return "".join(parts), params

    async def count(
        self,
        filters: Mapping[str, Any] | None = None,
        *,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
    ) -> int:
        where_filters = self._where(filters)
        builder = self._combine_clauses(
            where_filters,
            self._search(search, search_columns, start=len(where_filters.params) + 1),
        )
        query = f"SELECT COUNT(*) AS total FROM {self._column(self.table)}{builder.query}"
        row = await self.db.fetchrow(query, *builder.params)
        return int(row["total"]) if row is not None else 0

    async def list(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | Sequence[str] | None = None,
    ) -> list[Row]:
        where_filters = self._where(filters)
        where = self._combine_clauses(
            where_filters,
            self._search(search, search_columns, start=len(where_filters.params) + 1),
        )
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

    async def list_with_pagination(
        self,
        *,
        filters: Mapping[str, Any] | None = None,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | Sequence[str] | None = None,
    ) -> dict[str, Any]:
        items = await self.list(
            filters=filters,
            search=search,
            search_columns=search_columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        total = await self.count(filters=filters, search=search, search_columns=search_columns)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    async def get_optional_by(
        self,
        filters: Mapping[str, Any],
        order_by: str | Sequence[str] | None = None,
    ) -> Row | None:
        where = self._where(filters)
        if not where.query:
            raise ValidationError("Filters cannot be empty")

        order_sql = self._order(order_by)
        query = f"SELECT * FROM {self._column(self.table)}{where.query}{order_sql} LIMIT 1"
        row = await self.db.fetchrow(query, *where.params)
        return dict(row) if row is not None else None

    async def get_one_by(
        self,
        filters: Mapping[str, Any],
        order_by: str | Sequence[str] | None = None,
    ) -> Row:
        row = await self.get_optional_by(filters=filters, order_by=order_by)
        if row is None:
            raise NotFoundError(f"{self.__class__.__name__} with filters={filters} not found")
        return dict(row)

    async def get_by_ids(
        self,
        ids: Sequence[Any],
        order_by: str | Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Row]:
        if not ids:
            return []
        return await self.list(
            filters={self.id_column: list(ids)},
            order_by=order_by,
            limit=limit,
            offset=offset,
        )

    async def get_scalar(self, column: str, filters: Mapping[str, Any] | None = None) -> Any | None:
        if not column:
            raise ValidationError("Column name cannot be empty")

        where = self._where(filters)
        query = (
            f"SELECT {self._column(column)} FROM {self._column(self.table)}"
            f"{where.query} LIMIT 1"
        )
        row = await self.db.fetchrow(query, *where.params)
        if row is None:
            return None
        return row[0]

    async def pluck(
        self,
        column: str,
        filters: Mapping[str, Any] | None = None,
        search: str | None = None,
        search_columns: Sequence[str] | None = None,
        order_by: str | Sequence[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Any]:
        if not column:
            raise ValidationError("Column name cannot be empty")

        where_filters = self._where(filters)
        where = self._combine_clauses(
            where_filters,
            self._search(search, search_columns, start=len(where_filters.params) + 1),
        )
        order_sql = self._order(order_by)
        limit_sql, limit_params = self._limit_offset(
            limit=limit,
            offset=offset,
            start=len(where.params) + 1,
        )
        rows = await self.db.fetch(
            f"SELECT {self._column(column)} AS value FROM {self._column(self.table)}"
            f"{where.query}{order_sql}{limit_sql}",
            *(where.params + limit_params),
        )
        return [row["value"] for row in rows]

    async def exists(self, filters: Mapping[str, Any]) -> bool:
        row = await self.get_optional_by(filters)
        return row is not None

    async def create_many_bulk(self, payloads: Iterable[Mapping[str, Any]]) -> list[Row]:
        payloads_list = list(payloads)
        if len(payloads_list) == 0:
            return []

        base_payload = payloads_list[0]
        cols = self._payload_keys(base_payload)
        columns = ", ".join(self._column(name) for name in cols)

        for payload in payloads_list:
            if self._payload_keys(payload) != cols:
                raise ValidationError("All payload dictionaries must have the same keys")

        values: list[Any] = []
        value_placeholders: list[str] = []
        cursor = 1
        for payload in payloads_list:
            payload_values = self._values(payload)
            placeholders = ", ".join(f"${i}" for i in range(cursor, cursor + len(cols)))
            value_placeholders.append(f"({placeholders})")
            cursor += len(cols)
            values.extend(payload_values)

        query = (
            f"INSERT INTO {self._column(self.table)} ({columns}) VALUES "
            f"{', '.join(value_placeholders)} RETURNING *"
        )
        rows = await self.db.fetch(query, *values)
        return [dict(row) for row in rows]

    async def get_by_id(self, entity_id: Any) -> Row:
        query = f"SELECT * FROM {self._column(self.table)} WHERE {self._column(self.id_column)} = $1 LIMIT 1"
        row = await self.db.fetchrow(query, entity_id)
        if row is None:
            raise NotFoundError(f"{self.__class__.__name__} with id={entity_id} not found")
        return dict(row)

    async def exists_by_id(self, entity_id: Any) -> bool:
        return await self.get_by_id_optional(entity_id) is not None

    async def get_by_id_optional(self, entity_id: Any) -> Row | None:
        query = f"SELECT * FROM {self._column(self.table)} WHERE {self._column(self.id_column)} = $1 LIMIT 1"
        row = await self.db.fetchrow(query, entity_id)
        if row is None:
            return None
        return dict(row)

    async def create(self, payload: Mapping[str, Any]) -> Row:
        cols = self._payload_keys(payload)
        values = self._values(payload)
        placeholders = ", ".join(f"${i}" for i in range(1, len(values) + 1))
        columns = ", ".join(self._column(name) for name in cols)

        row = await self.db.fetchrow(
            f"INSERT INTO {self._column(self.table)} ({columns}) VALUES ({placeholders}) RETURNING *",
            *values,
        )
        if row is None:
            raise ValidationError("Failed to create entity")
        return dict(row)

    async def create_many(self, payloads: Iterable[Mapping[str, Any]]) -> list[Row]:
        return await self.create_many_bulk(payloads)

    async def update_by_id(self, entity_id: Any, payload: Mapping[str, Any]) -> Row:
        assignments, values = self._set_clause(payload, start=1)
        if not assignments:
            raise ValidationError("Payload cannot be empty")

        query = (
            f"UPDATE {self._column(self.table)} SET "
            f"{assignments} "
            f"WHERE {self._column(self.id_column)} = ${len(values) + 1} RETURNING *"
        )
        row = await self.db.fetchrow(query, *values, entity_id)
        if row is None:
            raise NotFoundError(f"{self.__class__.__name__} with id={entity_id} not found")
        return dict(row)

    async def update_by_filters(
        self,
        filters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> list[Row]:
        assignments, values = self._set_clause(payload, start=1)
        where = self._where(filters, start=len(values) + 1)
        if not where.query:
            raise ValidationError("Filters cannot be empty")
        if not assignments:
            raise ValidationError("Payload cannot be empty")

        query = (
            f"UPDATE {self._column(self.table)} SET {assignments}"
            f"{where.query} RETURNING *"
        )
        rows = await self.db.fetch(query, *(values + where.params))
        return [dict(row) for row in rows]

    async def update_by_ids(self, ids: Sequence[Any], payload: Mapping[str, Any]) -> list[Row]:
        if not ids:
            return []
        return await self.update_by_filters(filters={self.id_column: list(ids)}, payload=payload)

    async def increment_by_filters(
        self,
        filters: Mapping[str, Any],
        increments: Mapping[str, int | float],
    ) -> list[Row]:
        if not increments:
            raise ValidationError("Increments cannot be empty")

        assignments: list[str] = []
        values: list[Any] = []
        for index, (key, value) in enumerate(increments.items(), start=1):
            if not isinstance(value, (int, float)):
                raise ValidationError("Increment values must be int or float")
            assignments.append(f"{self._column(key)} = {self._column(key)} + ${index}")
            values.append(value)

        where = self._where(filters, start=len(values) + 1)
        if not where.query:
            raise ValidationError("Filters cannot be empty")

        query = (
            f"UPDATE {self._column(self.table)} SET {', '.join(assignments)}"
            f"{where.query} RETURNING *"
        )
        rows = await self.db.fetch(query, *(values + where.params))
        return [dict(row) for row in rows]

    async def increment_by_id(
        self,
        entity_id: Any,
        increments: Mapping[str, int | float],
    ) -> Row:
        rows = await self.increment_by_filters(filters={self.id_column: entity_id}, increments=increments)
        if not rows:
            raise NotFoundError(f"{self.__class__.__name__} with id={entity_id} not found")
        return rows[0]

    async def decrement_by_filters(
        self,
        filters: Mapping[str, Any],
        decrements: Mapping[str, int | float],
    ) -> list[Row]:
        negative_increments = {
            key: -value for key, value in decrements.items()
        }
        return await self.increment_by_filters(filters=filters, increments=negative_increments)

    async def decrement_by_id(
        self,
        entity_id: Any,
        decrements: Mapping[str, int | float],
    ) -> Row:
        rows = await self.decrement_by_filters(filters={self.id_column: entity_id}, decrements=decrements)
        if not rows:
            raise NotFoundError(f"{self.__class__.__name__} with id={entity_id} not found")
        return rows[0]

    async def upsert(
        self,
        payload: Mapping[str, Any],
        conflict_columns: Sequence[str] | str,
        update_columns: Sequence[str] | None = None,
        do_nothing: bool = False,
    ) -> Row:
        cols = self._payload_keys(payload)
        values = self._values(payload)
        columns = ", ".join(self._column(name) for name in cols)
        placeholders = ", ".join(f"${i}" for i in range(1, len(cols) + 1))

        if isinstance(conflict_columns, str):
            conflict_columns = [conflict_columns]
        conflict_sql = ", ".join(self._column(name) for name in conflict_columns)
        if do_nothing:
            query = (
                f"INSERT INTO {self._column(self.table)} ({columns}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_sql}) DO NOTHING "
                f"RETURNING *"
            )
        else:
            if update_columns is None:
                update_columns = [column for column in cols if column not in list(conflict_columns)]
            if not update_columns:
                raise ValidationError("No columns to update in upsert")
            updates = ", ".join(
                f"{self._column(column)} = EXCLUDED.{self._column(column)}"
                for column in update_columns
            )
            query = (
                f"INSERT INTO {self._column(self.table)} ({columns}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {updates} "
                f"RETURNING *"
            )

        row = await self.db.fetchrow(query, *values)
        if row is None:
            return await self.get_one_by({column: payload[column] for column in conflict_columns if column in payload})
        return dict(row)

    async def upsert_many(
        self,
        payloads: Iterable[Mapping[str, Any]],
        conflict_columns: Sequence[str] | str,
        update_columns: Sequence[str] | None = None,
        do_nothing: bool = False,
    ) -> list[Row]:
        payloads_list = list(payloads)
        if len(payloads_list) == 0:
            return []

        rows: list[Row] = []
        for payload in payloads_list:
            row = await self.upsert(
                payload=payload,
                conflict_columns=conflict_columns,
                update_columns=update_columns,
                do_nothing=do_nothing,
            )
            rows.append(row)
        return rows

    async def delete_by_id(self, entity_id: Any) -> bool:
        query = f"DELETE FROM {self._column(self.table)} WHERE {self._column(self.id_column)} = $1 RETURNING {self._column(self.id_column)}"
        row = await self.db.fetchrow(query, entity_id)
        return row is not None

    async def delete_by_ids(self, ids: Sequence[Any]) -> int:
        if not ids:
            return 0
        return await self.delete_by_filters(filters={self.id_column: list(ids)})

    async def delete_by_filters(self, filters: Mapping[str, Any]) -> int:
        where = self._where(filters)
        if not where.query:
            raise ValidationError("Filters cannot be empty")

        rows = await self.db.fetch(
            f"DELETE FROM {self._column(self.table)}{where.query} RETURNING {self._column(self.id_column)}",
            *where.params,
        )
        return len(rows)
