from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar

import asyncpg

from app.db.errors import normalize_database_error


class Database:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10, command_timeout: int = 30) -> None:
        self._dsn = dsn
        self._min_size = min_size
        self._max_size = max_size
        self._command_timeout = command_timeout
        self._pool: asyncpg.Pool | None = None
        self._transaction_connection: ContextVar[asyncpg.Connection | None] = ContextVar(
            "db_transaction_connection",
            default=None,
        )

    async def connect(self) -> None:
        if self._pool is not None:
            return
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            command_timeout=self._command_timeout,
        )

    async def disconnect(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database is not connected")
        return self._pool

    def _get_active_connection(self) -> asyncpg.Connection | None:
        return self._transaction_connection.get()

    @asynccontextmanager
    async def transaction(self):
        active_connection = self._get_active_connection()
        if active_connection is not None:
            nested_transaction = active_connection.transaction()
            await nested_transaction.start()
            try:
                yield self
            except Exception:
                await nested_transaction.rollback()
                raise
            else:
                await nested_transaction.commit()
            return

        async with self.pool.acquire() as conn:
            token = self._transaction_connection.set(conn)
            transaction = conn.transaction()
            await transaction.start()
            try:
                yield self
            except Exception:
                await transaction.rollback()
                raise
            else:
                await transaction.commit()
            finally:
                self._transaction_connection.reset(token)

    async def fetch(self, query: str, *args):
        active_connection = self._get_active_connection()
        if active_connection is not None:
            try:
                return await active_connection.fetch(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

        async with self.pool.acquire() as conn:
            try:
                return await conn.fetch(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

    async def fetchrow(self, query: str, *args):
        active_connection = self._get_active_connection()
        if active_connection is not None:
            try:
                return await active_connection.fetchrow(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

        async with self.pool.acquire() as conn:
            try:
                return await conn.fetchrow(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

    async def fetchval(self, query: str, *args):
        active_connection = self._get_active_connection()
        if active_connection is not None:
            try:
                return await active_connection.fetchval(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

        async with self.pool.acquire() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

    async def execute(self, query: str, *args):
        active_connection = self._get_active_connection()
        if active_connection is not None:
            try:
                return await active_connection.execute(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

        async with self.pool.acquire() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
