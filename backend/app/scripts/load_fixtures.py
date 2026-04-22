from __future__ import annotations

import asyncio
from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, Integer, JSON, Numeric, SmallInteger, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql.schema import Table

import app.models  # noqa: F401
from app.core.config import get_settings
from app.db.pool import Database
from app.models import Base
from app.utils.password import hash_password, is_hashed_password


FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
FIXTURE_LOAD_ORDER = [
    "organizations",
    "department_modules",
    "workspace_resources",
    "departments",
    "warehouses",
    "currencies",
    "poultry_types",
    "measurement_units",
    "clients",
    "client_debts",
    "supplier_debts",
    "debt_payments",
    "client_categories",
    "positions",
    "roles",
    "permissions",
    "employees",
    "employee_roles",
    "role_permissions",
    "egg_production",
    "egg_shipments",
    "expense_categories",
    "expenses",
    "cash_accounts",
    "employee_advances",
    "cash_transactions",
    "feed_types",
    "feed_ingredients",
    "feed_formulas",
    "feed_formula_ingredients",
    "feed_arrivals",
    "feed_consumptions",
    "feed_raw_arrivals",
    "feed_production_batches",
    "feed_raw_consumptions",
    "feed_product_shipments",
    "incubation_batches",
    "incubation_runs",
    "chick_shipments",
    "chick_arrivals",
    "factory_flocks",
    "factory_daily_logs",
    "factory_shipments",
    "medicine_types",
    "medicine_batches",
    "factory_medicine_usages",
    "factory_vaccination_plans",
    "slaughter_arrivals",
    "slaughter_processings",
    "slaughter_semi_products",
    "slaughter_quality_checks",
    "slaughter_semi_product_shipments",
    "stock_movements",
]
ROLLING_DATE_ACTIVITY_TABLE_EXCLUSIONS: set[str] = set()
ROLLING_DATE_ACTIVITY_COLUMN_EXCLUSIONS = {"created_at", "updated_at", "changed_at", "expiry_date"}
ROLLING_DATE_FALSE_VALUES = {"0", "false", "off", "no"}
DEFAULT_ROLLING_LAG_DAYS = 2
RELATIVE_NOW_EXPRESSION = re.compile(
    r"^now(?:\(\s*(?:(?P<sign>[+-])\s*(?P<amount>\d+)\s*(?P<unit>[dwmy]))?\s*\)|\s*(?P<sign2>[+-])\s*(?P<amount2>\d+)\s*(?P<unit2>[dwmy]))?$",
    re.IGNORECASE,
)
ISO_DATE_LITERAL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LAST_TEMPORAL_SHIFT_DAYS = 0


def _is_truthy_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ROLLING_DATE_FALSE_VALUES


def _fixture_today() -> date:
    raw_value = os.getenv("APP_FIXTURE_NOW_DATE")
    if raw_value:
        return date.fromisoformat(raw_value.strip())
    return date.today()


def _fixture_now() -> datetime:
    raw_value = os.getenv("APP_FIXTURE_NOW_DATETIME")
    if raw_value:
        return _normalize_datetime(raw_value.strip())
    return datetime.now(timezone.utc).replace(microsecond=0)


def _shift_date_by_months(value: date, months: int) -> date:
    month_index = (value.year * 12 + (value.month - 1)) + months
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _shift_date_by_years(value: date, years: int) -> date:
    target_year = value.year + years
    day = min(value.day, monthrange(target_year, value.month)[1])
    return date(target_year, value.month, day)


def _shift_datetime_by_months(value: datetime, months: int) -> datetime:
    shifted = _shift_date_by_months(value.date(), months)
    return value.replace(year=shifted.year, month=shifted.month, day=shifted.day)


def _shift_datetime_by_years(value: datetime, years: int) -> datetime:
    shifted = _shift_date_by_years(value.date(), years)
    return value.replace(year=shifted.year, month=shifted.month, day=shifted.day)


def _resolve_relative_now_parts(raw_value: str) -> tuple[int, str] | None:
    match = RELATIVE_NOW_EXPRESSION.match(raw_value.strip())
    if match is None:
        return None

    sign = (match.group("sign") or match.group("sign2") or "+").strip()
    amount_text = (match.group("amount") or match.group("amount2") or "0").strip()
    unit = (match.group("unit") or match.group("unit2") or "d").strip().lower()
    multiplier = -1 if sign == "-" else 1
    return multiplier * int(amount_text), unit


def _resolve_relative_now_date(raw_value: object) -> date | None:
    if not isinstance(raw_value, str):
        return None

    resolved = _resolve_relative_now_parts(raw_value)
    if resolved is None:
        return None

    amount, unit = resolved
    base = _fixture_today()
    if unit == "d":
        return base + timedelta(days=amount)
    if unit == "w":
        return base + timedelta(weeks=amount)
    if unit == "m":
        return _shift_date_by_months(base, amount)
    if unit == "y":
        return _shift_date_by_years(base, amount)
    return None


def _resolve_relative_now_datetime(raw_value: object) -> datetime | None:
    if not isinstance(raw_value, str):
        return None

    resolved = _resolve_relative_now_parts(raw_value)
    if resolved is None:
        return None

    amount, unit = resolved
    base = _fixture_now()
    if unit == "d":
        return base + timedelta(days=amount)
    if unit == "w":
        return base + timedelta(weeks=amount)
    if unit == "m":
        return _shift_datetime_by_months(base, amount)
    if unit == "y":
        return _shift_datetime_by_years(base, amount)
    return None


def _parse_iso_date_literal(raw_value: object) -> date | None:
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if not isinstance(raw_value, str):
        return None

    normalized = raw_value.strip()
    if not ISO_DATE_LITERAL.match(normalized):
        return None

    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def _parse_iso_datetime_literal(raw_value: object) -> datetime | None:
    if isinstance(raw_value, datetime):
        return raw_value
    if not isinstance(raw_value, str):
        return None

    normalized = raw_value.strip()
    if not normalized:
        return None

    try:
        return _normalize_datetime(normalized)
    except ValueError:
        return None


def _format_shifted_datetime(original_value: object, shifted_value: datetime) -> object:
    if isinstance(original_value, datetime):
        return shifted_value
    if not isinstance(original_value, str):
        return shifted_value

    if original_value.strip().endswith("Z"):
        return shifted_value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return shifted_value.isoformat()


def _resolve_rolling_lag_days() -> int:
    raw_value = os.getenv("APP_FIXTURE_ROLLING_LAG_DAYS")
    if raw_value is None or not raw_value.strip():
        return DEFAULT_ROLLING_LAG_DAYS

    try:
        return max(int(raw_value.strip()), 0)
    except ValueError:
        return DEFAULT_ROLLING_LAG_DAYS


def _resolve_fixture_temporal_shift_days(rows_by_table: dict[str, list[dict[str, object]]]) -> int:
    if not _is_truthy_env("APP_FIXTURE_ROLLING_DATES", True):
        return 0

    activity_dates: list[date] = []
    for table_name, rows in rows_by_table.items():
        if table_name in ROLLING_DATE_ACTIVITY_TABLE_EXCLUSIONS:
            continue

        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue

        for row in rows:
            for column_name, value in row.items():
                if column_name in ROLLING_DATE_ACTIVITY_COLUMN_EXCLUSIONS:
                    continue

                column = table.columns.get(column_name)
                if column is None:
                    continue

                if isinstance(column.type, DateTime):
                    parsed_datetime = _parse_iso_datetime_literal(value)
                    if parsed_datetime is not None:
                        activity_dates.append(parsed_datetime.date())
                    continue

                if isinstance(column.type, Date):
                    parsed_date = _parse_iso_date_literal(value)
                    if parsed_date is not None:
                        activity_dates.append(parsed_date)

    if not activity_dates:
        return 0

    source_latest_date = max(activity_dates)
    target_latest_date = _fixture_today() - timedelta(days=_resolve_rolling_lag_days())
    return (target_latest_date - source_latest_date).days


def _shift_temporal_value(value: object, *, column_type: object, shift_days: int) -> object:
    if shift_days == 0:
        return value

    if _resolve_relative_now_date(value) is not None or _resolve_relative_now_datetime(value) is not None:
        return value

    if isinstance(column_type, DateTime):
        parsed_datetime = _parse_iso_datetime_literal(value)
        if parsed_datetime is None:
            return value
        shifted_datetime = parsed_datetime + timedelta(days=shift_days)
        return _format_shifted_datetime(value, shifted_datetime)

    if isinstance(column_type, Date):
        parsed_date = _parse_iso_date_literal(value)
        if parsed_date is None:
            return value
        shifted_date = parsed_date + timedelta(days=shift_days)
        return shifted_date.isoformat()

    return value


def _roll_fixture_temporal_values(rows_by_table: dict[str, list[dict[str, object]]]) -> dict[str, list[dict[str, object]]]:
    global _LAST_TEMPORAL_SHIFT_DAYS

    shift_days = _resolve_fixture_temporal_shift_days(rows_by_table)
    _LAST_TEMPORAL_SHIFT_DAYS = shift_days

    if shift_days == 0:
        return rows_by_table

    rolled_rows: dict[str, list[dict[str, object]]] = defaultdict(list)
    for table_name, rows in rows_by_table.items():
        table = Base.metadata.tables.get(table_name)
        if table is None:
            rolled_rows[table_name].extend(rows)
            continue

        for row in rows:
            rolled_row: dict[str, object] = {}
            for column_name, value in row.items():
                column = table.columns.get(column_name)
                if column is None:
                    rolled_row[column_name] = value
                    continue
                rolled_row[column_name] = _shift_temporal_value(
                    value,
                    column_type=column.type,
                    shift_days=shift_days,
                )
            rolled_rows[table_name].append(rolled_row)

    return dict(rolled_rows)


def _split_key_value(line: str) -> tuple[str, str]:
    key, separator, value = line.partition(":")
    if not separator:
        raise ValueError(f"Invalid fixture line: {line!r}")
    return key.strip(), value.strip()


def _parse_scalar(raw_value: str) -> object:
    if raw_value in {"null", "~"}:
        return None

    if raw_value == "true":
        return True

    if raw_value == "false":
        return False

    if (raw_value.startswith('"') and raw_value.endswith('"')) or (
        raw_value.startswith("'") and raw_value.endswith("'")
    ):
        return raw_value[1:-1]

    if raw_value.lstrip("-").isdigit():
        return int(raw_value)

    if raw_value.count(".") == 1:
        left, right = raw_value.split(".", 1)
        if left.lstrip("-").isdigit() and right.isdigit():
            return Decimal(raw_value)

    return raw_value


def _parse_fixture_file(path: Path) -> dict[str, list[dict[str, object]]]:
    parsed: dict[str, list[dict[str, object]]] = {}
    current_section: str | None = None
    current_item: dict[str, object] | None = None

    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if raw_line.startswith("  - "):
            if current_section is None:
                raise ValueError(f"{path}:{lineno}: item without section")
            current_item = {}
            parsed[current_section].append(current_item)
            key, raw_value = _split_key_value(raw_line[4:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("- "):
            if current_section is None:
                raise ValueError(f"{path}:{lineno}: item without section")
            current_item = {}
            parsed[current_section].append(current_item)
            key, raw_value = _split_key_value(raw_line[2:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("    "):
            if current_item is None:
                raise ValueError(f"{path}:{lineno}: attribute without item")
            key, raw_value = _split_key_value(raw_line[4:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if raw_line.startswith("  "):
            if current_item is None:
                raise ValueError(f"{path}:{lineno}: attribute without item")
            key, raw_value = _split_key_value(raw_line[2:])
            current_item[key] = _parse_scalar(raw_value)
            continue

        if not raw_line.startswith(" "):
            if not stripped.endswith(":"):
                raise ValueError(f"{path}:{lineno}: expected section header")
            current_section = stripped[:-1]
            parsed.setdefault(current_section, [])
            current_item = None
            continue

        raise ValueError(f"{path}:{lineno}: unsupported indentation")

    return parsed


def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value or 0))


def _stock_movement_row(
    *,
    organization_id: object,
    department_id: object,
    warehouse_id: object = None,
    item_type: str,
    item_key: str,
    movement_kind: str,
    quantity: Decimal,
    unit: object,
    occurred_on: object,
    reference_table: str,
    reference_id: object,
    counterparty_department_id: object = None,
    counterparty_warehouse_id: object = None,
    note: object = None,
) -> dict[str, object] | None:
    if quantity <= 0:
        return None

    resolved_scope_key = warehouse_id if warehouse_id is not None else department_id
    movement_id = uuid5(
        NAMESPACE_URL,
        "|".join(
            [
                str(reference_table),
                str(reference_id),
                movement_kind,
                str(resolved_scope_key),
                item_type,
                item_key,
            ]
        ),
    )
    return {
        "id": movement_id,
        "organization_id": organization_id,
        "department_id": department_id,
        "warehouse_id": warehouse_id,
        "counterparty_department_id": counterparty_department_id,
        "counterparty_warehouse_id": counterparty_warehouse_id,
        "item_type": item_type,
        "item_key": item_key,
        "movement_kind": movement_kind,
        "quantity": quantity,
        "unit": unit,
        "occurred_on": occurred_on,
        "reference_table": reference_table,
        "reference_id": reference_id,
        "note": None if note in (None, "") else str(note),
    }


def _normalize_warehouse_code_seed(raw_value: object | None) -> str:
    candidate = str(raw_value or "").strip().upper()
    normalized = re.sub(r"[^A-Z0-9]+", "-", candidate).strip("-")
    return normalized or "WH"


def _build_default_warehouse_rows(
    rows_by_table: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    warehouse_rows = list(rows_by_table.get("warehouses", []))
    warehouse_by_department = {
        str(row["department_id"]): row
        for row in warehouse_rows
        if row.get("department_id") is not None
    }
    code_counters: dict[tuple[str, str], int] = {}

    for row in warehouse_rows:
        organization_id = str(row.get("organization_id") or "")
        code = str(row.get("code") or "").strip().upper()
        if organization_id and code:
            code_counters[(organization_id, code)] = max(code_counters.get((organization_id, code), 0), 1)

    for department in rows_by_table.get("departments", []):
        department_id = str(department.get("id") or "")
        if not department_id or department_id in warehouse_by_department:
            continue

        organization_id = str(department.get("organization_id") or "")
        base_seed = _normalize_warehouse_code_seed(department.get("code") or department.get("name"))
        base_code = (f"{base_seed}-WH"[:80]).rstrip("-") or "WH"
        counter_key = (organization_id, base_code)
        next_counter = code_counters.get(counter_key, 0) + 1
        code_counters[counter_key] = next_counter
        if next_counter == 1:
            code = base_code
        else:
            suffix = f"-{next_counter}"
            allowed_base_length = max(1, 80 - len(suffix))
            code = f"{base_code[:allowed_base_length].rstrip('-')}{suffix}"

        warehouse_row = {
            "id": uuid5(NAMESPACE_URL, f"warehouse|{department_id}|default"),
            "organization_id": organization_id,
            "department_id": department_id,
            "name": "Asosiy ombor",
            "code": code,
            "description": f"Default warehouse for {department.get('name') or 'department'}",
            "is_default": True,
            "is_active": bool(department.get("is_active", True)),
        }
        warehouse_rows.append(warehouse_row)
        warehouse_by_department[department_id] = warehouse_row

    return warehouse_rows


def _apply_default_warehouses_to_stock_movements(
    rows_by_table: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    default_warehouse_by_department = {
        str(row["department_id"]): row
        for row in rows_by_table.get("warehouses", [])
        if row.get("department_id") is not None and bool(row.get("is_default", False))
    }
    normalized_rows: list[dict[str, object]] = []

    for row in rows_by_table.get("stock_movements", []):
        next_row = dict(row)
        department_id = str(next_row.get("department_id") or "")
        if not department_id:
            raise ValueError("Stock movement is missing department_id")

        warehouse_row = default_warehouse_by_department.get(department_id)
        if warehouse_row is None:
            raise ValueError(f"Department {department_id!r} does not have a default warehouse")
        next_row["warehouse_id"] = warehouse_row["id"]

        counterparty_department_id = next_row.get("counterparty_department_id")
        if counterparty_department_id is not None:
            counterparty_warehouse = default_warehouse_by_department.get(str(counterparty_department_id))
            if counterparty_warehouse is None:
                raise ValueError(
                    f"Counterparty department {counterparty_department_id!r} does not have a default warehouse"
                )
            next_row["counterparty_warehouse_id"] = counterparty_warehouse["id"]
        else:
            next_row["counterparty_warehouse_id"] = None

        normalized_rows.append(next_row)

    return normalized_rows


def _build_generated_stock_movements(
    rows_by_table: dict[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    stock_rows = list(rows_by_table.get("stock_movements", []))
    formula_feed_type_by_id = {
        str(row["id"]): str(row["feed_type_id"])
        for row in rows_by_table.get("feed_formulas", [])
        if row.get("id") is not None and row.get("feed_type_id") is not None
    }

    for row in rows_by_table.get("egg_production", []):
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="egg",
            item_key=f"egg:{row['id']}",
            movement_kind="incoming",
            quantity=(
                _decimal_value(row.get("eggs_collected"))
                - _decimal_value(row.get("eggs_broken"))
                - _decimal_value(row.get("eggs_rejected"))
            ),
            unit="pcs",
            occurred_on=row["produced_on"],
            reference_table="egg_production",
            reference_id=row["id"],
            note=row.get("note"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("egg_shipments", []):
        production_id = row.get("production_id")
        if production_id is None:
            continue
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="egg",
            item_key=f"egg:{production_id}",
            movement_kind="outgoing",
            quantity=_decimal_value(row.get("eggs_count")),
            unit=row.get("unit") or "pcs",
            occurred_on=row["shipped_on"],
            reference_table="egg_shipments",
            reference_id=row["id"],
            note=row.get("invoice_no"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("incubation_batches", []):
        production_id = row.get("production_id")
        if production_id is None:
            continue
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="egg",
            item_key=f"egg:{production_id}",
            movement_kind="outgoing",
            quantity=_decimal_value(row.get("eggs_arrived")),
            unit="pcs",
            occurred_on=row["arrived_on"],
            reference_table="incubation_batches",
            reference_id=row["id"],
            note=row.get("batch_code"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("incubation_runs", []):
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="chick",
            item_key=f"chick_run:{row['id']}",
            movement_kind="incoming",
            quantity=_decimal_value(row.get("chicks_hatched")) - _decimal_value(row.get("chicks_destroyed")),
            unit="pcs",
            occurred_on=row.get("end_date") or row["start_date"],
            reference_table="incubation_runs",
            reference_id=row["id"],
            note=row.get("note"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("chick_shipments", []):
        run_id = row.get("run_id")
        if run_id is None:
            continue
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="chick",
            item_key=f"chick_run:{run_id}",
            movement_kind="outgoing",
            quantity=_decimal_value(row.get("chicks_count")),
            unit="pcs",
            occurred_on=row["shipped_on"],
            reference_table="chick_shipments",
            reference_id=row["id"],
            note=row.get("invoice_no"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("feed_production_batches", []):
        formula_id = str(row.get("formula_id") or "")
        if not formula_feed_type_by_id.get(formula_id):
            raise ValueError(f"Unknown feed formula for production batch: {formula_id}")
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="feed",
            item_key=f"feed_product:{row['id']}",
            movement_kind="incoming",
            quantity=_decimal_value(row.get("actual_output")),
            unit=row.get("unit") or "kg",
            occurred_on=row.get("finished_on") or row["started_on"],
            reference_table="feed_production_batches",
            reference_id=row["id"],
            note=row.get("batch_code"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("feed_product_shipments", []):
        production_batch_id = row.get("production_batch_id")
        item_key_target = str(production_batch_id) if production_batch_id else str(row["feed_type_id"])
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="feed",
            item_key=f"feed_product:{item_key_target}",
            movement_kind="outgoing",
            quantity=_decimal_value(row.get("quantity")),
            unit=row.get("unit") or "kg",
            occurred_on=row["shipped_on"],
            reference_table="feed_product_shipments",
            reference_id=row["id"],
            note=row.get("invoice_no"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("medicine_batches", []):
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="medicine",
            item_key=f"medicine_batch:{row['id']}",
            movement_kind="incoming",
            quantity=_decimal_value(row.get("received_quantity")),
            unit=row.get("unit") or "pcs",
            occurred_on=row["arrived_on"],
            reference_table="medicine_batches",
            reference_id=row["id"],
            note=row.get("batch_code"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("slaughter_semi_products", []):
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="semi_product",
            item_key=f"semi_product:{row['id']}",
            movement_kind="incoming",
            quantity=_decimal_value(row.get("quantity")),
            unit=row.get("unit") or "kg",
            occurred_on=row["produced_on"],
            reference_table="slaughter_semi_products",
            reference_id=row["id"],
            note=row.get("code"),
        )
        if movement is not None:
            stock_rows.append(movement)

    for row in rows_by_table.get("slaughter_semi_product_shipments", []):
        semi_product_id = row.get("semi_product_id")
        if semi_product_id is None:
            continue
        movement = _stock_movement_row(
            organization_id=row["organization_id"],
            department_id=row["department_id"],
            item_type="semi_product",
            item_key=f"semi_product:{semi_product_id}",
            movement_kind="outgoing",
            quantity=_decimal_value(row.get("quantity")),
            unit=row.get("unit") or "kg",
            occurred_on=row["shipped_on"],
            reference_table="slaughter_semi_product_shipments",
            reference_id=row["id"],
            note=row.get("invoice_no"),
        )
        if movement is not None:
            stock_rows.append(movement)

    return stock_rows


def _load_fixture_rows(fixtures_dir: Path) -> dict[str, list[dict[str, object]]]:
    rows_by_table: dict[str, list[dict[str, object]]] = defaultdict(list)
    for path in sorted(fixtures_dir.glob("*.yaml")):
        for table_name, rows in _parse_fixture_file(path).items():
            rows_by_table[table_name].extend(rows)

    prepared_rows = _roll_fixture_temporal_values(dict(rows_by_table))
    prepared_rows["warehouses"] = _build_default_warehouse_rows(prepared_rows)
    prepared_rows["stock_movements"] = _build_generated_stock_movements(prepared_rows)
    prepared_rows["stock_movements"] = _apply_default_warehouses_to_stock_movements(prepared_rows)
    _resolve_measurement_unit_ids(prepared_rows)
    _backfill_cash_transaction_structure(prepared_rows)
    return prepared_rows


def _backfill_cash_transaction_structure(
    rows_by_table: dict[str, list[dict[str, object]]],
) -> None:
    """Populate F0.6 structured fields for cash_transactions rows in fixtures.

    Fixtures stay readable with just cash_account_id + amount + currency;
    this helper derives `department_id` from the account and snapshots
    `amount_in_base` (= amount, rate=1.0) so the NOT NULL columns load.
    """
    from decimal import Decimal

    account_dept: dict[str, str] = {
        str(row["id"]): str(row["department_id"])
        for row in rows_by_table.get("cash_accounts", [])
        if row.get("department_id") is not None
    }

    currency_index: dict[tuple[str, str], str] = {}
    for row in rows_by_table.get("currencies", []):
        currency_index[(str(row["organization_id"]), str(row["code"]).upper())] = str(row["id"])

    for row in rows_by_table.get("cash_transactions", []):
        if not row.get("department_id"):
            cash_account_id = str(row.get("cash_account_id") or "")
            if cash_account_id and cash_account_id in account_dept:
                row["department_id"] = account_dept[cash_account_id]

        if not row.get("counterparty_type") and row.get("counterparty_client_id"):
            row["counterparty_type"] = "client"
            row["counterparty_id"] = row["counterparty_client_id"]

        if row.get("expense_id") and not row.get("source_type"):
            row["source_type"] = "expense"
            row["source_id"] = row["expense_id"]

        if row.get("amount_in_base") is None:
            amount = Decimal(str(row.get("amount") or 0))
            rate = Decimal(str(row.get("exchange_rate_to_base") or "1.0"))
            row["amount_in_base"] = str((amount * rate).quantize(Decimal("0.01")))

        if row.get("exchange_rate_to_base") is None:
            row["exchange_rate_to_base"] = "1.0"

        if row.get("status") is None:
            row["status"] = "posted"

        if not row.get("currency_id"):
            org = str(row.get("organization_id") or "")
            code = str(row.get("currency") or "").upper()
            if org and code:
                cid = currency_index.get((org, code))
                if cid is not None:
                    row["currency_id"] = cid


UNIT_FK_TABLES: dict[str, str] = {
    "egg_shipments": "unit",
    "client_debts": "unit",
    "feed_arrivals": "unit",
    "feed_consumptions": "unit",
    "feed_ingredients": "unit",
    "feed_types": "unit",
    "feed_formula_ingredients": "unit",
    "feed_raw_consumptions": "unit",
    "feed_production_batches": "unit",
    "feed_product_shipments": "unit",
    "feed_raw_arrivals": "unit",
    "stock_reorder_levels": "unit",
    "stock_take_lines": "unit",
    "stock_movements": "unit",
    "medicine_consumptions": "unit",
    "medicine_batches": "unit",
    "medicine_arrivals": "unit",
    "supplier_debts": "unit",
    "slaughter_semi_product_shipments": "unit",
    "slaughter_semi_products": "unit",
}

UNIT_ALIASES: dict[str, str] = {
    "pcs": "dona",
    "bosh": "dona",
    "l": "litr",
    "kilogram": "kg",
    "kilogramm": "kg",
}


def _resolve_measurement_unit_ids(rows_by_table: dict[str, list[dict[str, object]]]) -> None:
    """Populate measurement_unit_id FK on every row of unit-bearing tables, using
    measurement_units entries as lookup table. Applied in-place."""
    unit_index: dict[tuple[str, str], str] = {}
    for row in rows_by_table.get("measurement_units", []):
        org = str(row["organization_id"])
        code = str(row["code"]).strip().lower()
        unit_index[(org, code)] = str(row["id"])

    # stock_take_lines has no organization_id — index by stock_take_id → org via parent
    stock_take_org: dict[str, str] = {
        str(row["id"]): str(row["organization_id"])
        for row in rows_by_table.get("stock_takes", [])
    }

    for table, unit_col in UNIT_FK_TABLES.items():
        for row in rows_by_table.get(table, []):
            if row.get("measurement_unit_id"):
                continue
            unit_raw = row.get(unit_col) or "kg"
            unit_code = str(unit_raw).strip().lower()
            unit_code = UNIT_ALIASES.get(unit_code, unit_code)

            org = row.get("organization_id")
            if org is None and table == "stock_take_lines":
                stock_take_id = row.get("stock_take_id")
                if stock_take_id is not None:
                    org = stock_take_org.get(str(stock_take_id))
            if org is None:
                continue
            org = str(org)

            unit_id = unit_index.get((org, unit_code)) or unit_index.get((org, "kg"))
            if unit_id is None:
                continue
            row["measurement_unit_id"] = unit_id


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _normalize_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        return datetime.fromisoformat(value[:-1] + "+00:00")
    return datetime.fromisoformat(value)


def _coerce_legacy_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (int, float, bool, date, datetime, UUID)):
        return value
    s = str(value)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return date.fromisoformat(s)
    try:
        return UUID(s)
    except (ValueError, AttributeError):
        pass
    if isinstance(value, (int, float)):
        return value
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return s


def _coerce_value(table_name: str, column_name: str, value: object, table: Table) -> object:
    if value is None:
        return None

    column = table.columns.get(column_name)
    if column is None:
        raise KeyError(f"Unknown column {column_name!r} for table {table_name!r}")

    if table_name == "employees" and column_name == "password":
        password = str(value)
        return password if is_hashed_password(password) else hash_password(password)

    column_type = column.type

    if isinstance(column_type, PGUUID):
        return value if isinstance(value, UUID) else UUID(str(value))

    if isinstance(column_type, Date):
        resolved_now_date = _resolve_relative_now_date(value)
        if resolved_now_date is not None:
            return resolved_now_date
        return value if isinstance(value, date) else date.fromisoformat(str(value))

    if isinstance(column_type, DateTime):
        resolved_now_datetime = _resolve_relative_now_datetime(value)
        if resolved_now_datetime is not None:
            return resolved_now_datetime
        return value if isinstance(value, datetime) else _normalize_datetime(str(value))

    if isinstance(column_type, Time):
        return value if isinstance(value, time) else time.fromisoformat(str(value))

    if isinstance(column_type, Numeric):
        return value if isinstance(value, Decimal) else Decimal(str(value))

    if isinstance(column_type, (Integer, SmallInteger, BigInteger)):
        return int(value)

    if isinstance(column_type, Float):
        return float(value)

    if isinstance(column_type, Boolean):
        return bool(value)

    if isinstance(column_type, JSON):
        json_value = json.loads(value) if isinstance(value, str) else value
        return json.dumps(json_value)

    return value


async def _truncate_and_load(rows_by_table: dict[str, list[dict[str, object]]]) -> dict[str, int]:
    settings = get_settings()
    db = Database(
        settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()

    try:
        all_tables = Base.metadata.tables
        known_tables = set(all_tables)
        legacy_tables = {
            "feed_arrivals",
            "feed_consumptions",
            "feed_raw_arrivals",
            "feed_raw_consumptions",
            "chick_arrivals",
        }
        unknown_tables = sorted(set(rows_by_table) - known_tables - legacy_tables)
        if unknown_tables:
            raise ValueError(f"Unknown fixture tables: {', '.join(unknown_tables)}")

        missing_in_load_order = sorted(set(rows_by_table) - set(FIXTURE_LOAD_ORDER))
        if missing_in_load_order:
            raise ValueError(f"Fixture load order is not defined for: {', '.join(missing_in_load_order)}")

        all_table_names = set(all_tables) | (legacy_tables & set(rows_by_table))
        quoted_tables = ", ".join(_quote_identifier(t) for t in all_table_names)
        inserted_counts: dict[str, int] = {}

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE")

                for table_name in FIXTURE_LOAD_ORDER:
                    rows = rows_by_table.get(table_name, [])
                    if not rows:
                        continue

                    table = all_tables.get(table_name)

                    for row in rows:
                        columns = list(row.keys())
                        if table is not None:
                            prepared_values = [
                                _coerce_value(table_name, column_name, row[column_name], table)
                                for column_name in columns
                            ]
                        else:
                            prepared_values = [
                                _coerce_legacy_value(row[c]) for c in columns
                            ]
                        quoted_columns = ", ".join(_quote_identifier(column_name) for column_name in columns)
                        placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
                        query = (
                            f"INSERT INTO {_quote_identifier(table_name)} ({quoted_columns}) "
                            f"VALUES ({placeholders})"
                        )
                        await conn.execute(query, *prepared_values)

                    inserted_counts[table_name] = len(rows)

        return inserted_counts
    finally:
        await db.disconnect()


def _print_summary(rows_by_table: dict[str, list[dict[str, object]]], inserted_counts: dict[str, int]) -> None:
    print("Fixtures loaded successfully.")
    print(f"Source directory: {FIXTURES_DIR}")
    if _LAST_TEMPORAL_SHIFT_DAYS != 0:
        direction = "+" if _LAST_TEMPORAL_SHIFT_DAYS > 0 else ""
        print(f"Temporal data shift: {direction}{_LAST_TEMPORAL_SHIFT_DAYS} day(s) (rolling demo mode)")

    for table_name in sorted(inserted_counts):
        print(f"- {table_name}: {inserted_counts[table_name]}")

    employees = rows_by_table.get("employees", [])
    if employees:
        print("Available login credentials:")
        for employee in employees:
            organization_key = employee.get("organization_key")
            password = employee.get("password")
            if organization_key and password:
                print(f"- {organization_key} / {password}")


async def _main() -> None:
    rows_by_table = _load_fixture_rows(FIXTURES_DIR)
    inserted_counts = await _truncate_and_load(rows_by_table)
    _print_summary(rows_by_table, inserted_counts)
    await _sync_module_manager_roles()


async def _sync_module_manager_roles() -> None:
    from app.scripts.sync_role_templates import sync_role_templates_for_organizations

    settings = get_settings()
    db = Database(
        settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()
    try:
        stats = await sync_role_templates_for_organizations(db, dry_run=False, verbose=False)
    finally:
        await db.disconnect()

    print(
        "Module-manager role templates synced: "
        f"created={stats.roles_created}, updated={stats.roles_updated}, "
        f"permission_links={stats.role_permission_links_written}"
    )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
