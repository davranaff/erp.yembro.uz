from __future__ import annotations

import re

import pytest

from tests.helpers import build_create_payload, extract_data, make_admin_headers, make_auth_headers


ALI_EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
CASH_ACCOUNT_READ_PERMISSION_ID = "60611111-1111-1111-1111-111111111111"
HOME_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
FACTORY_DEPARTMENT_ID = "55555555-5555-5555-5555-555555555555"
FEED_DEPARTMENT_ID = "77771111-1111-1111-1111-111111111111"
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@pytest.mark.asyncio
async def test_crud_list_supports_text_search_for_large_reference_sets(api_client) -> None:
    response = await api_client.get(
        "/api/v1/hr/employees",
        headers=make_admin_headers(),
        params={"search": "Ali Hamidov", "limit": 24},
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert any(item["id"] == ALI_EMPLOYEE_ID for item in payload["items"])
    assert payload["total"] >= 1


@pytest.mark.asyncio
async def test_reference_options_endpoint_returns_human_labels(api_client) -> None:
    response = await api_client.get(
        "/api/v1/hr/roles/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "permission_ids",
            "search": "cash_account.read",
            "limit": 10,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert payload["field"] == "permission_ids"
    assert any(
        option["value"] == CASH_ACCOUNT_READ_PERMISSION_ID and option["label"] == "cash_account.read"
        for option in payload["options"]
    )


@pytest.mark.asyncio
async def test_reference_options_fallback_to_business_label_not_uuid(api_client) -> None:
    response = await api_client.get(
        "/api/v1/feed/product-shipments/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "client_id",
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert payload["field"] == "client_id"
    assert payload["options"], "Expected at least one client option"

    assert any(
        option["value"] != option["label"] and not UUID_RE.fullmatch(option["label"])
        for option in payload["options"]
    )


@pytest.mark.asyncio
async def test_incubation_run_reference_options_use_generated_non_uuid_labels(api_client) -> None:
    response = await api_client.get(
        "/api/v1/incubation/chick-shipments/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "run_id",
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert payload["field"] == "run_id"
    assert payload["options"], "Expected at least one run option"

    assert any(
        option["value"] != option["label"] and not UUID_RE.fullmatch(option["label"])
        for option in payload["options"]
    )


@pytest.mark.asyncio
async def test_department_module_reference_options_hide_non_assignable_modules(api_client) -> None:
    response = await api_client.get(
        "/api/v1/core/departments/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "module_key",
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {option["value"] for option in payload["options"]}

    assert "egg" in option_values
    assert "feed" in option_values
    assert "core" not in option_values
    assert "finance" not in option_values
    assert "hr" not in option_values


@pytest.mark.asyncio
async def test_currency_reference_options_are_scoped_to_actor_organization(api_client) -> None:
    response = await api_client.get(
        "/api/v1/finance/expenses/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "currency",
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {option["value"] for option in payload["options"]}

    assert payload["field"] == "currency"
    assert "UZS" in option_values
    assert "USD" in option_values
    assert "EUR" not in option_values


@pytest.mark.asyncio
async def test_warehouse_reference_options_are_filtered_by_department(api_client) -> None:
    warehouses_response = await api_client.get(
        "/api/v1/core/warehouses",
        headers=make_admin_headers(),
    )
    assert warehouses_response.status_code == 200, warehouses_response.text

    warehouse_items = extract_data(warehouses_response)["items"]
    expected_values = {
        str(item["id"])
        for item in warehouse_items
        if str(item.get("department_id") or "") == HOME_DEPARTMENT_ID
    }
    other_values = {
        str(item["id"])
        for item in warehouse_items
        if str(item.get("department_id") or "") != HOME_DEPARTMENT_ID
    }
    assert expected_values, "Expected at least one warehouse for the target department"

    response = await api_client.get(
        "/api/v1/inventory/movements/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "warehouse_id",
            "department_id": HOME_DEPARTMENT_ID,
            "limit": 50,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {option["value"] for option in payload["options"]}
    option_labels = {str(option["value"]): str(option["label"]) for option in payload["options"]}
    expected_codes = {
        str(item["id"]): str(item["code"])
        for item in warehouse_items
        if str(item.get("department_id") or "") == HOME_DEPARTMENT_ID and str(item.get("code") or "")
    }

    assert payload["field"] == "warehouse_id"
    assert option_values == expected_values
    assert option_values.isdisjoint(other_values)
    assert expected_codes, "Expected at least one warehouse code for the target department"
    assert all(
        expected_codes[warehouse_id] in option_labels.get(warehouse_id, "")
        for warehouse_id in expected_codes
    )


@pytest.mark.asyncio
async def test_expense_category_reference_options_are_filtered_by_department(api_client) -> None:
    categories_response = await api_client.get(
        "/api/v1/finance/expense-categories",
        headers=make_admin_headers(),
    )
    assert categories_response.status_code == 200, categories_response.text

    category_items = extract_data(categories_response)["items"]
    expected_values = {
        str(item["id"])
        for item in category_items
        if str(item.get("department_id") or "") == FEED_DEPARTMENT_ID
    }
    other_values = {
        str(item["id"])
        for item in category_items
        if str(item.get("department_id") or "") != FEED_DEPARTMENT_ID
    }
    assert expected_values, "Expected at least one expense category for the target department"

    response = await api_client.get(
        "/api/v1/finance/expenses/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "category_id",
            "department_id": FEED_DEPARTMENT_ID,
            "limit": 50,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {option["value"] for option in payload["options"]}

    assert payload["field"] == "category_id"
    assert option_values == expected_values
    assert option_values.isdisjoint(other_values)


@pytest.mark.asyncio
async def test_inventory_item_key_reference_options_are_filtered_by_item_type(api_client) -> None:
    response = await api_client.get(
        "/api/v1/inventory/movements/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "item_key",
            "item_type": "egg",
            "department_id": HOME_DEPARTMENT_ID,
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    assert payload["field"] == "item_key"
    assert payload["options"], "Expected at least one selectable item for egg movements"
    assert all(str(option["value"]).startswith("egg:") for option in payload["options"])
    assert any(option["label"] != option["value"] for option in payload["options"])


@pytest.mark.asyncio
async def test_inventory_item_key_reference_options_include_cross_department_stock_keys(api_client) -> None:
    response = await api_client.get(
        "/api/v1/inventory/movements/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "item_key",
            "item_type": "egg",
            "department_id": FACTORY_DEPARTMENT_ID,
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {str(option["value"]) for option in payload["options"]}
    assert "egg:10111111-1111-1111-1111-111111111111" in option_values
    assert "egg:10222222-2222-2222-2222-222222222222" in option_values


@pytest.mark.asyncio
async def test_currency_defaults_are_applied_from_org_catalog(api_client) -> None:
    currency_headers = make_auth_headers("currency")
    expense_headers = make_auth_headers("expense")

    update_default_response = await api_client.put(
        "/api/v1/core/currencies/32122222-2222-2222-2222-222222222222",
        json={"is_default": True},
        headers=currency_headers,
    )
    assert update_default_response.status_code == 200, update_default_response.text

    payload = await build_create_payload(api_client, "/api/v1/finance/expenses")
    payload.pop("currency", None)

    create_response = await api_client.post(
        "/api/v1/finance/expenses",
        json=payload,
        headers=expense_headers,
    )
    assert create_response.status_code == 201, create_response.text

    created = extract_data(create_response)
    assert created["currency"] == "USD"


@pytest.mark.asyncio
async def test_currency_must_exist_inside_actor_organization(api_client) -> None:
    expense_headers = make_auth_headers("expense")
    payload = await build_create_payload(api_client, "/api/v1/finance/expenses")
    payload["currency"] = "EUR"

    response = await api_client.post(
        "/api/v1/finance/expenses",
        json=payload,
        headers=expense_headers,
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "currency is invalid"


@pytest.mark.asyncio
async def test_cash_transaction_type_reference_options_are_exposed_for_forms(api_client) -> None:
    response = await api_client.get(
        "/api/v1/finance/cash-transactions/meta/reference-options",
        headers=make_admin_headers(),
        params={
            "field": "transaction_type",
            "limit": 20,
        },
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    option_values = {option["value"] for option in payload["options"]}

    assert payload["field"] == "transaction_type"
    assert option_values == {"income", "expense", "transfer_in", "transfer_out", "adjustment"}
