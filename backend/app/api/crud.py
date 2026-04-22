from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime, time
from typing import Any, Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.sql.sqltypes import Enum as SqlEnum, String, Text, Unicode, UnicodeText

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.repositories.system import AuditLogRepository
from app.models import Base
from app.services.base import BaseService
from app.services.system import AuditLogService
from app.utils.result import Result


ServiceFactory = Callable[[Database], BaseService]
S = TypeVar("S", bound=BaseService)
AUDIT_COLUMNS = {"created_at", "updated_at", "deleted_at"}
REFERENCE_LABEL_CANDIDATES = (
    "name",
    "display_name",
    "short_name",
    "full_name",
    "legal_name",
    "company_name",
    "title",
    "part_name",
    "code",
    "client_code",
    "key",
    "organization_key",
    "invoice_no",
    "lot_no",
    "batch_code",
    "barcode",
    "symbol",
    "unit",
    "category",
    "email",
    "phone",
    "slug",
    "resource",
    "action",
)
REFERENCE_LABEL_EXCLUDED_COLUMNS = AUDIT_COLUMNS.union(
    {
        "id",
        "organization_id",
        "department_id",
        "parent_department_id",
        "created_by",
        "created_by_id",
        "updated_by",
        "updated_by_id",
        "deleted_by",
        "deleted_by_id",
        "is_active",
        "is_default",
        "sort_order",
        "status",
        "password",
    }
)
TEXTUAL_REFERENCE_LABEL_TYPES = (String, Text, Unicode, UnicodeText, SqlEnum)


def _ensure_ok(result: Result[Any]) -> Any:
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error or "Operation failed")
    return result.data


def _quote_identifier(value: str) -> str:
    if not value or '"' in value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SQL identifier")
    return f'"{value}"'


def _humanize_column(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def _get_model_columns(table: str) -> list[str]:
    model_table = Base.metadata.tables.get(table)
    if model_table is None:
        return []
    return [column.name for column in model_table.columns]


def _is_textual_reference_column(column: Any) -> bool:
    if isinstance(column.type, TEXTUAL_REFERENCE_LABEL_TYPES):
        return True
    try:
        return getattr(column.type, "python_type", None) is str
    except (NotImplementedError, AttributeError):
        return False


def _is_non_text_reference_column(column: Any) -> bool:
    try:
        python_type = getattr(column.type, "python_type", None)
    except (NotImplementedError, AttributeError):
        return False

    return python_type in {date, datetime, time, int, float, Decimal}


def _fallback_reference_label_columns(
    table: str,
    *,
    reference_column: str,
    label_column: str | None = None,
    include_non_text: bool = False,
) -> list[str]:
    model_table = Base.metadata.tables.get(table)
    if model_table is None:
        return []

    fallback_columns: list[str] = []
    excluded = set(REFERENCE_LABEL_EXCLUDED_COLUMNS)
    excluded.add(reference_column)
    if label_column:
        excluded.add(label_column)

    for column in model_table.columns:
        column_name = str(column.name)

        if column_name in excluded:
            continue
        if column_name.endswith("_id"):
            continue
        if column_name.startswith("is_"):
            continue
        if column_name.endswith(("_at", "_on", "_date")):
            if include_non_text and _is_non_text_reference_column(column):
                fallback_columns.append(column_name)
            continue

        if _is_textual_reference_column(column):
            fallback_columns.append(column_name)
            continue

        if include_non_text and _is_non_text_reference_column(column):
            fallback_columns.append(column_name)
            continue

    return fallback_columns


def _map_field_type(data_type: str, udt_name: str) -> str:
    normalized = (data_type or "").lower()
    normalized_udt = (udt_name or "").lower()

    if normalized in {"smallint", "integer", "bigint"}:
        return "integer"
    if normalized in {"numeric", "decimal", "real", "double precision"}:
        return "number"
    if normalized == "boolean":
        return "boolean"
    if normalized == "date":
        return "date"
    if "timestamp" in normalized:
        return "datetime"
    if normalized.startswith("time"):
        return "time"
    if normalized in {"json", "jsonb", "array"} or normalized_udt.startswith("_"):
        return "json"
    if normalized == "uuid":
        return "uuid"
    return "string"


async def _fetch_column_rows(db: Database, table: str) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT
            c.column_name,
            c.data_type,
            c.udt_name,
            (c.is_nullable = 'YES') AS is_nullable,
            c.column_default,
            c.ordinal_position,
            (c.is_identity = 'YES') AS is_identity
        FROM information_schema.columns AS c
        WHERE c.table_schema = 'public' AND c.table_name = $1
        ORDER BY c.ordinal_position
        """,
        table,
    )
    return [dict(row) for row in rows]


async def _fetch_primary_key_columns(db: Database, table: str) -> set[str]:
    rows = await db.fetch(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = $1
          AND tc.constraint_type = 'PRIMARY KEY'
        """,
        table,
    )
    return {str(row["column_name"]) for row in rows}


async def _fetch_foreign_keys(db: Database, table: str) -> dict[str, dict[str, str]]:
    rows = await db.fetch(
        """
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = $1
          AND tc.constraint_type = 'FOREIGN KEY'
        """,
        table,
    )
    return {
        str(row["column_name"]): {
            "table": str(row["foreign_table_name"]),
            "column": str(row["foreign_column_name"]),
        }
        for row in rows
    }


async def _detect_reference_label_column(db: Database, table: str, reference_column: str) -> str:
    columns = _get_model_columns(table)

    for candidate in REFERENCE_LABEL_CANDIDATES:
        if candidate in columns and candidate != reference_column:
            return candidate

    fallback_columns = _fallback_reference_label_columns(
        table,
        reference_column=reference_column,
        include_non_text=True,
    )
    if fallback_columns:
        return fallback_columns[0]

    return reference_column


def _build_reference_label_expression(
    *,
    table: str,
    reference_column: str,
    label_column: str,
) -> str:
    columns = set(_get_model_columns(table))
    reference_expr = f"CAST({_quote_identifier(reference_column)} AS TEXT)"

    def text_expr(column_name: str) -> str:
        return f"CAST({_quote_identifier(column_name)} AS TEXT)"

    def non_empty(column_name: str) -> str:
        return f"NULLIF(TRIM(COALESCE({text_expr(column_name)}, '')), '')"

    if table == "warehouses" and "name" in columns and "code" in columns:
        warehouse_name_expr = non_empty("name")
        warehouse_code_expr = non_empty("code")
        warehouse_name_with_code_expr = (
            "CASE "
            f"WHEN {warehouse_name_expr} IS NOT NULL "
            f"AND {warehouse_code_expr} IS NOT NULL "
            f"AND {warehouse_name_expr} <> {warehouse_code_expr} "
            f"THEN {warehouse_name_expr} || ' (' || {warehouse_code_expr} || ')' "
            "ELSE NULL END"
        )
        return (
            "COALESCE("
            f"{warehouse_name_with_code_expr}, "
            f"{warehouse_name_expr}, "
            f"{warehouse_code_expr}, "
            f"{reference_expr}"
            ")"
        )

    if "full_name" in columns:
        return f"COALESCE({non_empty('full_name')}, {reference_expr})"

    if "first_name" in columns or "last_name" in columns:
        name_parts: list[str] = []
        if "first_name" in columns:
            name_parts.append(f"COALESCE({text_expr('first_name')}, '')")
        if "last_name" in columns:
            name_parts.append(f"COALESCE({text_expr('last_name')}, '')")
        full_name_expr = "NULLIF(TRIM(" + " || ' ' || ".join(name_parts) + "), '')"
        fallbacks = [full_name_expr]
        for candidate in (label_column, "organization_key", "email", "code", "title", "name", "slug"):
            if candidate in columns and candidate not in {"first_name", "last_name"}:
                fallbacks.append(non_empty(candidate))
        fallbacks.append(reference_expr)
        return "COALESCE(" + ", ".join(fallbacks) + ")"

    fallbacks: list[str] = []
    seen_candidates: set[str] = set()
    for candidate in (
        label_column,
        "name",
        "display_name",
        "short_name",
        "legal_name",
        "company_name",
        "title",
        "part_name",
        "code",
        "client_code",
        "organization_key",
        "invoice_no",
        "lot_no",
        "batch_code",
        "barcode",
        "symbol",
        "unit",
        "category",
        "email",
        "slug",
        "resource",
        "action",
    ):
        if candidate in columns and candidate not in seen_candidates:
            seen_candidates.add(candidate)
            fallbacks.append(non_empty(candidate))

    for candidate in _fallback_reference_label_columns(
        table,
        reference_column=reference_column,
        label_column=label_column,
        include_non_text=True,
    ):
        if candidate in columns and candidate not in seen_candidates:
            seen_candidates.add(candidate)
            fallbacks.append(non_empty(candidate))

    fallbacks.append(reference_expr)
    return "COALESCE(" + ", ".join(fallbacks) + ")"


def _build_reference_search_expressions(
    *,
    table: str,
    reference_column: str,
    label_column: str,
) -> list[str]:
    columns = set(_get_model_columns(table))
    expressions: list[str] = []

    def text_expr(column_name: str) -> str:
        return f"COALESCE(CAST({_quote_identifier(column_name)} AS TEXT), '')"

    if "full_name" in columns:
        expressions.append(text_expr("full_name"))
    elif "first_name" in columns or "last_name" in columns:
        name_parts: list[str] = []
        if "first_name" in columns:
            name_parts.append(text_expr("first_name"))
        if "last_name" in columns:
            name_parts.append(text_expr("last_name"))
        expressions.append("TRIM(" + " || ' ' || ".join(name_parts) + ")")

    for candidate in (
        label_column,
        "name",
        "display_name",
        "short_name",
        "legal_name",
        "company_name",
        "title",
        "part_name",
        "code",
        "client_code",
        "organization_key",
        "invoice_no",
        "lot_no",
        "batch_code",
        "barcode",
        "symbol",
        "unit",
        "category",
        "email",
        "phone",
        "slug",
        "description",
        "resource",
        "action",
        reference_column,
    ):
        if candidate in columns and text_expr(candidate) not in expressions:
            expressions.append(text_expr(candidate))

    for candidate in _fallback_reference_label_columns(
        table,
        reference_column=reference_column,
        label_column=label_column,
        include_non_text=True,
    ):
        expression = text_expr(candidate)
        if candidate in columns and expression not in expressions:
            expressions.append(expression)

    if not expressions:
        expressions.append(text_expr(reference_column))

    return expressions


async def _fetch_reference_options(
    db: Database,
    table: str,
    reference_column: str,
    label_column: str,
    actor: CurrentActor | None = None,
    department_id: str | list[str] | None = None,
) -> list[dict[str, str]]:
    return await _query_reference_options(
        db=db,
        table=table,
        reference_column=reference_column,
        label_column=label_column,
        actor=actor,
        department_id=department_id,
    )


async def _query_reference_options(
    *,
    db: Database,
    table: str,
    reference_column: str,
    label_column: str,
    search: str | None = None,
    values: list[str] | None = None,
    limit: int = 200,
    department_id: str | list[str] | None = None,
    actor: CurrentActor | None = None,
) -> list[dict[str, str]]:
    normalized_values = [value.strip() for value in (values or []) if value and value.strip()]
    if isinstance(department_id, list):
        normalized_department_ids = [
            value.strip() for value in department_id if value and value.strip()
        ]
    else:
        single = str(department_id or "").strip()
        normalized_department_ids = [single] if single else []
    label_expression = _build_reference_label_expression(
        table=table,
        reference_column=reference_column,
        label_column=label_column,
    )
    search_expressions = _build_reference_search_expressions(
        table=table,
        reference_column=reference_column,
        label_column=label_column,
    )

    clauses: list[str] = []
    params: list[Any] = []
    cursor = 1

    model_table = Base.metadata.tables.get(table)
    if (
        actor is not None
        and model_table is not None
        and "organization_id" in model_table.columns
        and "super_admin" not in actor.roles
    ):
        clauses.append(f"{_quote_identifier('organization_id')} = ${cursor}")
        params.append(actor.organization_id)
        cursor += 1

    if normalized_department_ids and model_table is not None and "department_id" in model_table.columns:
        if len(normalized_department_ids) == 1:
            clauses.append(f"{_quote_identifier('department_id')} = ${cursor}")
            params.append(normalized_department_ids[0])
        else:
            clauses.append(f"{_quote_identifier('department_id')} = ANY(${cursor}::uuid[])")
            params.append(normalized_department_ids)
        cursor += 1

    if (
        model_table is not None
        and table == "department_modules"
        and "is_department_assignable" in model_table.columns
    ):
        clauses.append(f"{_quote_identifier('is_department_assignable')} = true")

    value_clause = ""
    if normalized_values:
        placeholders = ", ".join(f"${index}" for index in range(cursor, cursor + len(normalized_values)))
        value_clause = f"CAST({_quote_identifier(reference_column)} AS TEXT) IN ({placeholders})"
        params.extend(normalized_values)
        cursor += len(normalized_values)

    search_text = (search or "").strip().lower()
    search_clause = ""
    if search_text:
        search_parts: list[str] = []
        for expression in search_expressions:
            search_parts.append(f"LOWER({expression}) LIKE ${cursor}")
            params.append(f"%{search_text}%")
            cursor += 1
        search_clause = "(" + " OR ".join(search_parts) + ")"

    if value_clause and search_clause:
        clauses.append(f"({value_clause} OR {search_clause})")
    elif value_clause:
        clauses.append(value_clause)
    elif search_clause:
        clauses.append(search_clause)

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_placeholder = f"${cursor}"
    params.append(max(limit, len(normalized_values) or 0))

    query = (
        f"SELECT DISTINCT CAST({_quote_identifier(reference_column)} AS TEXT) AS value, "
        f"{label_expression} AS label "
        f"FROM {_quote_identifier(table)}"
        f"{where_sql} "
        "ORDER BY label, value "
        f"LIMIT {limit_placeholder}"
    )
    rows = await db.fetch(query, *params)
    return [{"value": str(row["value"]), "label": str(row["label"])} for row in rows]


async def _build_resource_meta(
    *,
    db: Database,
    prefix: str,
    service_factory: Callable[[Database], BaseService],
    actor: CurrentActor | None = None,
    department_scope: str | list[str] | None = None,
) -> dict[str, Any]:
    service = service_factory(db)
    repository = service.repository
    table = repository.table
    primary_key_columns = await _fetch_primary_key_columns(db, table)
    foreign_keys = await _fetch_foreign_keys(db, table)
    column_rows = await _fetch_column_rows(db, table)
    reference_cache: dict[tuple[str, str], dict[str, Any]] = {}
    fields: list[dict[str, Any]] = []
    field_indexes: dict[str, int] = {}

    def upsert_field(field_payload: dict[str, Any]) -> None:
        field_name = str(field_payload["name"])
        existing_index = field_indexes.get(field_name)
        if existing_index is None:
            field_indexes[field_name] = len(fields)
            fields.append(field_payload)
            return

        merged = dict(fields[existing_index])
        merged.update(field_payload)
        existing_reference = fields[existing_index].get("reference")
        next_reference = field_payload.get("reference")
        if isinstance(existing_reference, dict) or isinstance(next_reference, dict):
            merged["reference"] = {
                **(existing_reference if isinstance(existing_reference, dict) else {}),
                **(next_reference if isinstance(next_reference, dict) else {}),
            }
        fields[existing_index] = merged

    for column in column_rows:
        name = str(column["column_name"])
        data_type = str(column["data_type"])
        udt_name = str(column["udt_name"])
        is_primary_key = name in primary_key_columns
        has_default = column["column_default"] is not None or bool(column["is_identity"])
        is_nullable = bool(column["is_nullable"])
        is_readonly = is_primary_key or name in AUDIT_COLUMNS
        foreign_key = foreign_keys.get(name)
        reference_payload: dict[str, Any] | None = None

        if foreign_key is not None:
            cache_key = (foreign_key["table"], foreign_key["column"])
            if cache_key not in reference_cache:
                label_column = await _detect_reference_label_column(
                    db,
                    foreign_key["table"],
                    foreign_key["column"],
                )
                referenced_table = Base.metadata.tables.get(foreign_key["table"])
                referenced_has_department = (
                    referenced_table is not None
                    and "department_id" in referenced_table.columns
                )
                reference_department_scope = (
                    department_scope if referenced_has_department and name != "department_id" else None
                )
                reference_cache[cache_key] = {
                    "table": foreign_key["table"],
                    "column": foreign_key["column"],
                    "label_column": label_column,
                    "options": await _fetch_reference_options(
                        db,
                        foreign_key["table"],
                        foreign_key["column"],
                        label_column,
                        actor=actor,
                        department_id=reference_department_scope,
                    ),
                }
            reference_payload = reference_cache[cache_key]
        upsert_field(
            {
                "name": name,
                "label": _humanize_column(name),
                "type": _map_field_type(data_type, udt_name),
                "database_type": udt_name if data_type.lower() == "user-defined" else data_type,
                "nullable": is_nullable,
                "required": not is_nullable and not has_default and not is_readonly,
                "readonly": is_readonly,
                "has_default": has_default,
                "is_primary_key": is_primary_key,
                "is_foreign_key": foreign_key is not None,
                "reference": reference_payload,
            }
        )

    for field in await service.get_additional_meta_fields(db):
        normalized_field = dict(field)
        reference_payload = normalized_field.get("reference")
        if isinstance(reference_payload, dict) and reference_payload.get("table") not in {None, "__static__"}:
            table_name = str(reference_payload["table"])
            reference_column = str(reference_payload.get("column") or "id")
            label_column = str(
                reference_payload.get("label_column")
                or await _detect_reference_label_column(db, table_name, reference_column)
            )
            referenced_table = Base.metadata.tables.get(table_name)
            referenced_has_department = (
                referenced_table is not None and "department_id" in referenced_table.columns
            )
            field_name_for_meta = str(normalized_field.get("name") or "")
            reference_department_scope = (
                department_scope
                if referenced_has_department and field_name_for_meta != "department_id"
                else None
            )
            if "options" not in reference_payload:
                reference_payload["options"] = await _fetch_reference_options(
                    db,
                    table_name,
                    reference_column,
                    label_column,
                    actor=actor,
                    department_id=reference_department_scope,
                )
            reference_payload["label_column"] = label_column
            normalized_field["reference"] = reference_payload

        upsert_field(normalized_field)

    return {
        "resource": prefix,
        "table": table,
        "id_column": repository.id_column,
        "fields": fields,
    }


async def _resolve_reference_payload(
    *,
    db: Database,
    service_factory: Callable[[Database], BaseService],
    field_name: str,
) -> dict[str, Any] | None:
    service = service_factory(db)

    for field in await service.get_additional_meta_fields(db):
        if str(field.get("name")) != field_name:
            continue
        reference_payload = field.get("reference")
        if isinstance(reference_payload, dict):
            resolved_payload = dict(reference_payload)
            reference_table = str(resolved_payload.get("table") or "")
            if reference_table and reference_table != "__static__":
                reference_column = str(resolved_payload.get("column") or "id")
                resolved_payload["column"] = reference_column
                resolved_payload["label_column"] = str(
                    resolved_payload.get("label_column")
                    or await _detect_reference_label_column(db, reference_table, reference_column)
                )
            return resolved_payload
        return None

    table = Base.metadata.tables.get(service.repository.table)
    if table is None or field_name not in table.columns:
        return None

    column = table.columns[field_name]
    foreign_keys = list(column.foreign_keys)
    if not foreign_keys:
        return None

    foreign_key = foreign_keys[0]
    reference_table = foreign_key.column.table.name
    reference_column = foreign_key.column.name
    label_column = await _detect_reference_label_column(db, reference_table, reference_column)
    return {
        "table": reference_table,
        "column": reference_column,
        "label_column": label_column,
        "multiple": False,
    }


def build_crud_router(
    *,
    prefix: str,
    service_factory: Callable[[Database], BaseService],
    permission_prefix: str,
    tags: list[str] | None = None,
    allow_roles: tuple[str, ...] = ("admin", "manager"),
    read_dependency: Callable[..., None] | None = None,
    write_dependency: Callable[..., None] | None = None,
    create_dependency: Callable[..., None] | None = None,
    delete_dependency: Callable[..., None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix=f"/{prefix}", tags=tags or [prefix])

    read_dep = read_dependency or require_access(f"{permission_prefix}.read", roles=allow_roles)
    write_dep = write_dependency or require_access(f"{permission_prefix}.write", roles=allow_roles)
    create_dep = create_dependency or require_access(f"{permission_prefix}.create", roles=allow_roles)
    delete_dep = delete_dependency or require_access(f"{permission_prefix}.delete", roles=allow_roles)
    audit_dep = require_access("audit.read", roles=allow_roles)

    @router.get(
        "",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(read_dep)],
    )
    async def list_items(
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        order_by: str | None = Query(default=None),
        search: str | None = Query(default=None, min_length=1),
        department_id: list[str] | None = Query(default=None),
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> dict[str, Any]:
        service = service_factory(db)
        filters: dict[str, Any] | None = None
        normalized_department_ids = [
            value.strip() for value in (department_id or []) if value and value.strip()
        ]
        if normalized_department_ids and service._uses_department_scope():
            filters = {
                "department_id": (
                    normalized_department_ids[0]
                    if len(normalized_department_ids) == 1
                    else normalized_department_ids
                )
            }
        result = await service.list_with_pagination(
            filters=filters,
            search=search,
            limit=limit,
            offset=offset,
            order_by=order_by,
            actor=current_actor,
        )
        return _ensure_ok(result)

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(create_dep)],
    )
    async def create_item(
        payload: dict[str, Any],
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> Any:
        service = service_factory(db)
        result = await service.create(payload, actor=current_actor)
        return _ensure_ok(result)

    @router.get(
        "/meta",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(read_dep)],
    )
    async def get_resource_meta(
        department_id: list[str] | None = Query(default=None),
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> dict[str, Any]:
        normalized_department_ids = [
            value.strip() for value in (department_id or []) if value and value.strip()
        ]
        scope_param: str | list[str] | None = (
            normalized_department_ids
            if len(normalized_department_ids) > 1
            else normalized_department_ids[0]
            if len(normalized_department_ids) == 1
            else None
        )
        return await _build_resource_meta(
            db=db,
            prefix=prefix,
            service_factory=service_factory,
            actor=current_actor,
            department_scope=scope_param,
        )

    @router.get(
        "/meta/reference-options",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(read_dep)],
    )
    async def get_reference_options(
        field: str = Query(..., min_length=1),
        search: str | None = Query(default=None),
        values: list[str] = Query(default=[]),
        limit: int = Query(default=25, ge=1, le=100),
        department_id: list[str] | None = Query(default=None),
        item_type: str | None = Query(default=None),
        category_id: str | None = Query(default=None),
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> dict[str, Any]:
        service = service_factory(db)
        reference_payload = await _resolve_reference_payload(
            db=db,
            service_factory=service_factory,
            field_name=field,
        )
        if reference_payload is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reference field not found")

        normalized_department_ids = [
            value.strip() for value in (department_id or []) if value and value.strip()
        ]
        custom_department_id: str | None = (
            normalized_department_ids[0] if len(normalized_department_ids) == 1 else None
        )
        generic_department_scope: str | list[str] | None
        if len(normalized_department_ids) > 1:
            generic_department_scope = normalized_department_ids
        elif len(normalized_department_ids) == 1:
            generic_department_scope = normalized_department_ids[0]
        else:
            generic_department_scope = None

        custom_options = await service.get_reference_options(
            field_name=field,
            db=db,
            actor=current_actor,
            search=search,
            values=values,
            limit=limit,
            extra_params={
                "department_id": custom_department_id,
                "item_type": item_type,
                "category_id": category_id,
            },
        )

        if custom_options is not None:
            options = custom_options
        elif str(reference_payload.get("table") or "") == "__static__":
            options = list(reference_payload.get("options") or [])
        else:
            options = await _query_reference_options(
                db=db,
                table=str(reference_payload["table"]),
                reference_column=str(reference_payload.get("column") or "id"),
                label_column=str(reference_payload.get("label_column") or "id"),
                search=search,
                values=values,
                limit=limit,
                department_id=generic_department_scope,
                actor=current_actor,
            )

        return {
            "field": field,
            "options": options,
            "multiple": bool(reference_payload.get("multiple")),
        }

    @router.get(
        "/{entity_id}/audit",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(read_dep), Depends(audit_dep)],
    )
    async def list_item_audit(
        entity_id: str,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> dict[str, Any]:
        service = service_factory(db)
        audit_service = AuditLogService(AuditLogRepository(db))
        result = await audit_service.list_entity_history(
            entity_table=service.repository.table,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
            actor=current_actor,
        )
        return _ensure_ok(result)

    @router.get(
        "/{entity_id}",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(read_dep)],
    )
    async def get_item(
        entity_id: str,
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> Any:
        service = service_factory(db)
        result = await service.get_by_id(str(entity_id), actor=current_actor)
        return _ensure_ok(result)

    @router.put(
        "/{entity_id}",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(write_dep)],
    )
    async def update_item(
        entity_id: str,
        payload: dict[str, Any],
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> Any:
        service = service_factory(db)
        result = await service.update(entity_id, payload, actor=current_actor)
        return _ensure_ok(result)

    @router.delete(
        "/{entity_id}",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(delete_dep)],
    )
    async def delete_item(
        entity_id: str,
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> dict[str, bool]:
        service = service_factory(db)
        result = await service.delete(entity_id, actor=current_actor)
        data = _ensure_ok(result)
        if data is False:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
        return {"deleted": data}

    @router.post(
        "/{entity_id}/acknowledge",
        status_code=status.HTTP_200_OK,
        dependencies=[Depends(write_dep)],
    )
    async def acknowledge_item(
        entity_id: str,
        payload: dict[str, Any],
        current_actor: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> Any:
        service = service_factory(db)
        if not service.repository.has_column("status") or not service.repository.has_column("acknowledged_at"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This resource does not support acknowledgment",
            )
        received_quantity = payload.get("received_quantity")
        if received_quantity is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="received_quantity is required",
            )
        result = await service.acknowledge_shipment(
            entity_id,
            received_quantity=received_quantity,
            note=payload.get("note"),
            actor=current_actor,
        )
        return _ensure_ok(result)

    return router
