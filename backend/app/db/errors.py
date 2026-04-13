from __future__ import annotations

import re
import sqlite3

import asyncpg

from app.core.exceptions import ConflictError, ValidationError


_ASYNC_PG_CONFLICT_TABLE_RE = re.compile(r'constraint "[^"]+" on table "(?P<table>[^"]+)"', re.IGNORECASE)
_ASYNC_PG_UNIQUE_DETAIL_RE = re.compile(r"Key \((?P<columns>[^)]+)\)=\((?P<values>[^)]+)\)", re.IGNORECASE)
_SQLITE_UNIQUE_RE = re.compile(r"UNIQUE constraint failed: (?P<columns>.+)", re.IGNORECASE)
_SQLITE_NOT_NULL_RE = re.compile(r"NOT NULL constraint failed: (?P<column>.+)", re.IGNORECASE)
_SQLITE_CHECK_RE = re.compile(r"CHECK constraint failed: (?P<constraint>.+)", re.IGNORECASE)


def normalize_database_error(exc: Exception) -> Exception:
    if isinstance(exc, (ConflictError, ValidationError)):
        return exc

    if isinstance(exc, asyncpg.exceptions.ForeignKeyViolationError):
        return ConflictError(_build_asyncpg_foreign_key_message(exc))

    if isinstance(exc, asyncpg.exceptions.UniqueViolationError):
        return ConflictError(_build_asyncpg_unique_message(exc))

    if isinstance(
        exc,
        (
            asyncpg.exceptions.NotNullViolationError,
            asyncpg.exceptions.CheckViolationError,
            asyncpg.exceptions.InvalidTextRepresentationError,
            asyncpg.exceptions.NumericValueOutOfRangeError,
            asyncpg.exceptions.StringDataRightTruncationError,
            asyncpg.exceptions.DataError,
        ),
    ):
        return ValidationError(_build_asyncpg_validation_message(exc))

    if isinstance(exc, sqlite3.IntegrityError):
        return _build_sqlite_integrity_error(exc)

    return exc


def _build_asyncpg_foreign_key_message(exc: asyncpg.exceptions.ForeignKeyViolationError) -> str:
    detail = getattr(exc, "detail", None) or ""
    message = str(exc).splitlines()[0]

    detail_match = re.search(r'referenced from table "(?P<table>[^"]+)"', detail, re.IGNORECASE)
    if detail_match is not None:
        return (
            "Cannot delete or update this record because it is still referenced by "
            f'"{detail_match.group("table")}".'
        )

    message_match = _ASYNC_PG_CONFLICT_TABLE_RE.search(message)
    if message_match is not None:
        return (
            "Cannot delete or update this record because it is still referenced by "
            f'"{message_match.group("table")}".'
        )

    return "Cannot delete or update this record because it is referenced by other records."


def _build_asyncpg_unique_message(exc: asyncpg.exceptions.UniqueViolationError) -> str:
    detail = getattr(exc, "detail", None) or ""
    match = _ASYNC_PG_UNIQUE_DETAIL_RE.search(detail)
    if match is None:
        return "A record with the same unique values already exists."

    columns = ", ".join(part.strip() for part in match.group("columns").split(","))
    return f"A record with the same {columns} already exists."


def _build_asyncpg_validation_message(exc: Exception) -> str:
    message = str(exc).splitlines()[0]
    constraint_name = getattr(exc, "constraint_name", None)
    column_name = getattr(exc, "column_name", None)

    if column_name:
        return f'Field "{column_name}" has an invalid value.'

    if constraint_name:
        return f'Constraint "{constraint_name}" was violated.'

    return message


def _build_sqlite_integrity_error(exc: sqlite3.IntegrityError) -> Exception:
    message = str(exc)

    if "FOREIGN KEY constraint failed" in message:
        return ConflictError(
            "Cannot delete or update this record because it is referenced by other records."
        )

    unique_match = _SQLITE_UNIQUE_RE.search(message)
    if unique_match is not None:
        columns = [
            column.rsplit(".", 1)[-1].strip()
            for column in unique_match.group("columns").split(",")
        ]
        return ConflictError(f'A record with the same {", ".join(columns)} already exists.')

    not_null_match = _SQLITE_NOT_NULL_RE.search(message)
    if not_null_match is not None:
        column = not_null_match.group("column").rsplit(".", 1)[-1].strip()
        return ValidationError(f'Field "{column}" is required.')

    check_match = _SQLITE_CHECK_RE.search(message)
    if check_match is not None:
        return ValidationError(f'Constraint "{check_match.group("constraint").strip()}" was violated.')

    return ValidationError(message)
