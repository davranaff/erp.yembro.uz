from __future__ import annotations

import asyncio
from copy import deepcopy

from app.scripts.load_fixtures import FIXTURES_DIR, _load_fixture_rows, _print_summary, _truncate_and_load


PRIMARY_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
PRIMARY_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
PRIMARY_ROLE_ID = "50444444-4444-4444-4444-444444444444"
PRIMARY_EMPLOYEE_ID = "70444444-4444-4444-4444-444444444444"
PRIMARY_CURRENCY_ID = "32111111-1111-1111-1111-111111111111"
PRIMARY_POULTRY_TYPE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PRIMARY_CLIENT_ID = "77777777-7777-7777-7777-777777777777"
PRIMARY_EXPENSE_CATEGORY_ID = "80111111-1111-1111-1111-111111111111"
PRIMARY_FEED_TYPE_ID = "01010101-0101-0101-0101-010101010101"
PRIMARY_MEDICINE_TYPE_ID = "10101010-1010-1010-1010-101010101010"


def _find_required_row(
    rows_by_table: dict[str, list[dict[str, object]]],
    table_name: str,
    *,
    id_value: str,
) -> dict[str, object]:
    for row in rows_by_table.get(table_name, []):
        if str(row.get("id") or "") == id_value:
            return deepcopy(row)
    raise ValueError(f"Required row {id_value!r} was not found in fixture table {table_name!r}")


def _build_minimal_rows() -> dict[str, list[dict[str, object]]]:
    source_rows = _load_fixture_rows(FIXTURES_DIR)

    organization = _find_required_row(
        source_rows,
        "organizations",
        id_value=PRIMARY_ORGANIZATION_ID,
    )
    department = _find_required_row(
        source_rows,
        "departments",
        id_value=PRIMARY_DEPARTMENT_ID,
    )
    warehouse = next(
        (
            deepcopy(row)
            for row in source_rows.get("warehouses", [])
            if str(row.get("department_id") or "") == PRIMARY_DEPARTMENT_ID
            and bool(row.get("is_default", False))
        ),
        None,
    )
    if warehouse is None:
        raise ValueError(f"Default warehouse for department {PRIMARY_DEPARTMENT_ID!r} was not found")
    role = _find_required_row(
        source_rows,
        "roles",
        id_value=PRIMARY_ROLE_ID,
    )
    employee = _find_required_row(
        source_rows,
        "employees",
        id_value=PRIMARY_EMPLOYEE_ID,
    )
    currency = _find_required_row(
        source_rows,
        "currencies",
        id_value=PRIMARY_CURRENCY_ID,
    )
    poultry_type = _find_required_row(
        source_rows,
        "poultry_types",
        id_value=PRIMARY_POULTRY_TYPE_ID,
    )
    client = _find_required_row(
        source_rows,
        "clients",
        id_value=PRIMARY_CLIENT_ID,
    )
    expense_category = _find_required_row(
        source_rows,
        "expense_categories",
        id_value=PRIMARY_EXPENSE_CATEGORY_ID,
    )
    feed_type = _find_required_row(
        source_rows,
        "feed_types",
        id_value=PRIMARY_FEED_TYPE_ID,
    )
    medicine_type = _find_required_row(
        source_rows,
        "medicine_types",
        id_value=PRIMARY_MEDICINE_TYPE_ID,
    )

    employee.pop("position_id", None)
    employee["department_id"] = PRIMARY_DEPARTMENT_ID

    return {
        "organizations": [organization],
        "department_modules": deepcopy(source_rows.get("department_modules", [])),
        "workspace_resources": deepcopy(source_rows.get("workspace_resources", [])),
        "departments": [department],
        "warehouses": [warehouse],
        "clients": [client],
        "currencies": [currency],
        "poultry_types": [poultry_type],
        "roles": [role],
        "employees": [employee],
        "employee_roles": [
            {
                "employee_id": PRIMARY_EMPLOYEE_ID,
                "role_id": PRIMARY_ROLE_ID,
            }
        ],
        "expense_categories": [expense_category],
        "feed_types": [feed_type],
        "medicine_types": [medicine_type],
    }


async def _main() -> None:
    rows_by_table = _build_minimal_rows()
    inserted_counts = await _truncate_and_load(rows_by_table)
    _print_summary(rows_by_table, inserted_counts)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
