from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
import os
import sqlite3
import re
import sys
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import aiosqlite
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import create_engine

os.environ.setdefault("APP_ENVIRONMENT", "test")
os.environ.setdefault("APP_AUTH_ALLOW_HEADER_OVERRIDES", "true")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.models  # noqa: F401
from app.api.deps import db_dependency
from app.api.exceptions import register_exception_handlers
from app.api.middleware import ApiResponseMiddleware
from app.api.router import api_router
from app.db.errors import normalize_database_error
from app.db.pool import Database
from app.models import Base
from app.scripts.load_fixtures import FIXTURE_LOAD_ORDER, FIXTURES_DIR, _coerce_value, _load_fixture_rows


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _coerce_sqlite_value(table_name: str, column_name: str, value: object) -> object:
    table = Base.metadata.tables[table_name]
    coerced = _coerce_value(table_name, column_name, value, table)

    if isinstance(coerced, UUID):
        return str(coerced)

    if isinstance(coerced, Decimal):
        return str(coerced)

    if isinstance(coerced, datetime):
        return coerced.isoformat(sep=" ")

    if isinstance(coerced, date):
        return coerced.isoformat()

    if isinstance(coerced, time):
        return coerced.isoformat()

    if isinstance(coerced, bool):
        return int(coerced)

    if isinstance(coerced, (list, dict)):
        return json.dumps(coerced)

    return coerced


def _normalize_sqlite_args(args: tuple[object, ...]) -> tuple[object, ...]:
    normalized: list[object] = []
    for value in args:
        if isinstance(value, UUID):
            normalized.append(str(value))
            continue
        if isinstance(value, Decimal):
            normalized.append(str(value))
            continue
        if isinstance(value, datetime):
            normalized.append(value.isoformat(sep=" "))
            continue
        if isinstance(value, date):
            normalized.append(value.isoformat())
            continue
        if isinstance(value, time):
            normalized.append(value.isoformat())
            continue
        if isinstance(value, bool):
            normalized.append(int(value))
            continue
        if isinstance(value, (list, dict)):
            normalized.append(json.dumps(value))
            continue
        normalized.append(value)
    return tuple(normalized)


def _sqlite_parse_temporal(value: object) -> datetime | date | None:
    if value is None:
        return None
    if isinstance(value, datetime | date):
        return value
    if not isinstance(value, str):
        return None

    normalized = value.replace("Z", "+00:00")
    for parser in (datetime.fromisoformat, date.fromisoformat):
        try:
            return parser(normalized)
        except ValueError:
            continue
    return None


def _sqlite_to_char(value: object, format_mask: object) -> str | None:
    if value is None:
        return None

    parsed = _sqlite_parse_temporal(value)
    if parsed is None:
        return str(value)

    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime.combine(parsed, time.min)

    formats = {
        "YYYY-MM-DD": "%Y-%m-%d",
        "YYYY-MM": "%Y-%m",
    }
    return parsed.strftime(formats.get(str(format_mask), "%Y-%m-%d"))


def _sqlite_date_trunc(part: object, value: object) -> str | None:
    if value is None:
        return None

    parsed = _sqlite_parse_temporal(value)
    if parsed is None:
        return str(value)

    if isinstance(parsed, date) and not isinstance(parsed, datetime):
        parsed = datetime.combine(parsed, time.min)

    if str(part).lower() == "month":
        return parsed.strftime("%Y-%m-01")
    return parsed.strftime("%Y-%m-%d")


def _sqlite_concat(*values: object) -> str:
    return "".join("" if value is None else str(value) for value in values)


def _sqlite_concat_ws(separator: object, *values: object) -> str:
    joiner = "" if separator is None else str(separator)
    parts = [str(value) for value in values if value is not None and str(value) != ""]
    return joiner.join(parts)


def _sqlite_btrim(value: object, chars: object | None = None) -> str | None:
    if value is None:
        return None
    if chars is None:
        return str(value).strip()
    return str(value).strip(str(chars))


def _sqlite_greatest(*values: object) -> object | None:
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return max(filtered)


def _sqlite_split_part(value: object, delimiter: object, index: object) -> str:
    parts = str(value).split("" if delimiter is None else str(delimiter))
    try:
        position = int(index) - 1
    except (TypeError, ValueError):
        return ""
    if position < 0 or position >= len(parts):
        return ""
    return parts[position]


def _sqlite_left(value: object, length: object) -> str | None:
    if value is None:
        return None
    try:
        n = int(length)
    except (TypeError, ValueError):
        return str(value)
    if n <= 0:
        return ""
    return str(value)[:n]


def _sqlite_right(value: object, length: object) -> str | None:
    if value is None:
        return None
    try:
        n = int(length)
    except (TypeError, ValueError):
        return str(value)
    if n <= 0:
        return ""
    return str(value)[-n:]


def _prepare_sqlite_database(path: str) -> None:
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()

    rows_by_table = _load_fixture_rows(FIXTURES_DIR)

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        for table_name in FIXTURE_LOAD_ORDER:
            rows = rows_by_table.get(table_name, [])
            if not rows:
                continue

            for row in rows:
                columns = list(row.keys())
                placeholders = ", ".join("?" for _ in columns)
                quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
                values = [
                    _coerce_sqlite_value(table_name, column_name, row[column_name])
                    for column_name in columns
                ]
                conn.execute(
                    f'INSERT INTO {_quote_identifier(table_name)} ({quoted_columns}) VALUES ({placeholders})',
                    values,
                )

        _seed_passed_quality_checks(conn, rows_by_table)

        conn.commit()


def _seed_passed_quality_checks(
    conn: sqlite3.Connection,
    rows_by_table: dict[str, list[dict[str, object]]],
) -> None:
    from uuid import uuid4

    for production in rows_by_table.get("egg_production", []):
        qc_id = str(uuid4())
        conn.execute(
            'INSERT INTO "egg_quality_checks" '
            '(id, organization_id, department_id, production_id, checked_on, status, grade) '
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                qc_id,
                str(production["organization_id"]),
                str(production["department_id"]),
                str(production["id"]),
                str(production.get("produced_on")),
                "passed",
                "large",
            ),
        )

    for batch in rows_by_table.get("feed_production_batches", []):
        qc_id = str(uuid4())
        conn.execute(
            'INSERT INTO "feed_production_quality_checks" '
            '(id, organization_id, department_id, production_batch_id, checked_on, status, grade) '
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                qc_id,
                str(batch["organization_id"]),
                str(batch["department_id"]),
                str(batch["id"]),
                str(batch.get("started_on")),
                "passed",
                "first",
            ),
        )


class AioSQLiteDatabase(Database):
    def __init__(self, dsn: str) -> None:
        super().__init__(dsn=dsn)
        self._pool = None
        self._sqlite_transaction_connection: ContextVar[aiosqlite.Connection | None] = ContextVar(
            "sqlite_transaction_connection",
            default=None,
        )

    def _convert(self, query: str, args: tuple[object, ...]) -> tuple[str, tuple[object, ...]]:
        expanded_args: list[object] = []

        def _replace_placeholder(match: re.Match[str]) -> str:
            index = int(match.group(1)) - 1
            expanded_args.append(args[index])
            return "?"

        sqlite_query = re.sub(r"\$(\d+)(::[a-zA-Z_][a-zA-Z0-9_\[\]]*)?", _replace_placeholder, query)
        sqlite_query = re.sub(r"::[a-zA-Z_][a-zA-Z0-9_\[\]]*", "", sqlite_query)
        sqlite_query = re.sub(r"([A-Za-z0-9_\.]+)\s*=\s*ANY\(\?\)", r"\1 IN (SELECT value FROM json_each(?))", sqlite_query)
        sqlite_query = re.sub(r"\(\?\s*\+\s*INTERVAL\s+'30 days'\)", "DATE(?, '+30 days')", sqlite_query)
        sqlite_query = re.sub(
            r"CURRENT_DATE\s*([+-])\s*INTERVAL\s+'(\d+)\s*(day|days|month|months|year|years)'",
            lambda m: f"DATE(CURRENT_DATE, '{m.group(1)}{m.group(2)} {m.group(3).rstrip('s')}s')",
            sqlite_query,
        )
        return sqlite_query, _normalize_sqlite_args(tuple(expanded_args))

    async def connect(self) -> None:
        return None

    async def disconnect(self) -> None:
        return None

    async def _open_connection(self) -> aiosqlite.Connection:
        conn = await aiosqlite.connect(self._dsn)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.create_function("TO_CHAR", 2, _sqlite_to_char)
        await conn.create_function("DATE_TRUNC", 2, _sqlite_date_trunc)
        await conn.create_function("CONCAT", -1, _sqlite_concat)
        await conn.create_function("CONCAT_WS", -1, _sqlite_concat_ws)
        await conn.create_function("BTRIM", -1, _sqlite_btrim)
        await conn.create_function("GREATEST", -1, _sqlite_greatest)
        await conn.create_function("split_part", 3, _sqlite_split_part)
        await conn.create_function("LEFT", 2, _sqlite_left)
        await conn.create_function("RIGHT", 2, _sqlite_right)
        return conn

    def _get_active_sqlite_connection(self) -> aiosqlite.Connection | None:
        return self._sqlite_transaction_connection.get()

    @asynccontextmanager
    async def transaction(self):
        active_connection = self._get_active_sqlite_connection()
        if active_connection is not None:
            yield self
            return

        conn = await self._open_connection()
        token = self._sqlite_transaction_connection.set(conn)
        try:
            await conn.execute("BEGIN")
            yield self
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise
        finally:
            self._sqlite_transaction_connection.reset(token)
            await conn.close()

    async def fetch(self, query: str, *args):
        sqlite_query, sqlite_args = self._convert(query, args)
        active_connection = self._get_active_sqlite_connection()
        if active_connection is not None:
            try:
                cursor = await active_connection.execute(sqlite_query, sqlite_args)
                rows = await cursor.fetchall()
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            return [dict(row) for row in rows]

        conn = await self._open_connection()
        try:
            try:
                cursor = await conn.execute(sqlite_query, sqlite_args)
                rows = await cursor.fetchall()
                await conn.commit()
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            return [dict(row) for row in rows]
        finally:
            await conn.close()

    async def fetchrow(self, query: str, *args):
        sqlite_query, sqlite_args = self._convert(query, args)
        active_connection = self._get_active_sqlite_connection()
        if active_connection is not None:
            try:
                cursor = await active_connection.execute(sqlite_query, sqlite_args)
                row = await cursor.fetchone()
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            return dict(row) if row is not None else None

        conn = await self._open_connection()
        try:
            try:
                cursor = await conn.execute(sqlite_query, sqlite_args)
                row = await cursor.fetchone()
                await conn.commit()
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            return dict(row) if row is not None else None
        finally:
            await conn.close()

    async def execute(self, query: str, *args):
        sqlite_query, sqlite_args = self._convert(query, args)
        active_connection = self._get_active_sqlite_connection()
        if active_connection is not None:
            try:
                return await active_connection.execute(sqlite_query, sqlite_args)
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise

        conn = await self._open_connection()
        try:
            try:
                cursor = await conn.execute(sqlite_query, sqlite_args)
                await conn.commit()
            except Exception as exc:
                normalized = normalize_database_error(exc)
                if normalized is not exc:
                    raise normalized from exc
                raise
            return cursor
        finally:
            await conn.close()


@pytest_asyncio.fixture
async def sqlite_db():
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as fp:
        path = fp.name
    _prepare_sqlite_database(path)
    db = AioSQLiteDatabase(path)
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()
        Path(path).unlink(missing_ok=True)


def _build_app(db: Database) -> FastAPI:
    app = FastAPI(title="test-app")
    register_exception_handlers(app)
    app.add_middleware(ApiResponseMiddleware)
    app.include_router(api_router)

    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.get("/health", include_in_schema=False)(healthcheck)
    app.dependency_overrides[db_dependency] = lambda: db
    return app


@pytest_asyncio.fixture
async def api_client(sqlite_db):
    from httpx import AsyncClient, ASGITransport
    app = _build_app(sqlite_db)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
