from __future__ import annotations

import uuid

import pytest

from tests.helpers import build_create_payload, extract_data, make_auth_headers, run_crud_flow


FINANCE_RESOURCES = [
    ("/api/v1/finance/expense-categories", "expense_category"),
    ("/api/v1/finance/expenses", "expense"),
    ("/api/v1/finance/cash-accounts", "cash_account"),
    ("/api/v1/finance/cash-transactions", "cash_transaction"),
]
FACTORY_CATEGORY_ID = "60111111-1111-1111-1111-111111111104"
EGG_CASH_ACCOUNT_ID = "62111111-1111-1111-1111-111111111101"


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", FINANCE_RESOURCES)
async def test_finance_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


@pytest.mark.asyncio
async def test_cash_transaction_type_is_normalized_before_insert(api_client) -> None:
    headers = make_auth_headers("cash_transaction")
    payload = await build_create_payload(api_client, "/api/v1/finance/cash-transactions")
    payload["transaction_type"] = "transfer out"

    response = await api_client.post(
        "/api/v1/finance/cash-transactions",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    created = extract_data(response)
    assert created["transaction_type"] == "transfer_out"


@pytest.mark.asyncio
async def test_cash_transaction_type_returns_validation_error_for_invalid_value(api_client) -> None:
    headers = make_auth_headers("cash_transaction")
    payload = await build_create_payload(api_client, "/api/v1/finance/cash-transactions")
    payload["transaction_type"] = "invalid"

    response = await api_client.post(
        "/api/v1/finance/cash-transactions",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 400, response.text
    error_payload = response.json()
    assert error_payload["ok"] is False
    assert error_payload["error"]["code"] == "validation_error"
    assert "transaction_type is invalid" in error_payload["error"]["message"]


@pytest.mark.asyncio
async def test_cash_transaction_expense_creates_and_updates_linked_expense(api_client) -> None:
    cash_headers = make_auth_headers("cash_transaction")
    expense_headers = make_auth_headers("expense")

    payload = await build_create_payload(api_client, "/api/v1/finance/cash-transactions")
    payload["transaction_type"] = "expense"
    payload["title"] = f"Auto expense {uuid.uuid4().hex[:8]}"
    payload["amount"] = 1234.56
    payload.pop("expense_id", None)

    create_response = await api_client.post(
        "/api/v1/finance/cash-transactions",
        headers=cash_headers,
        json=payload,
    )
    assert create_response.status_code == 201, create_response.text
    created_transaction = extract_data(create_response)

    linked_expense_id = str(created_transaction.get("expense_id") or "").strip()
    assert linked_expense_id
    assert str(created_transaction.get("department_id") or "").strip()
    assert str(created_transaction.get("expense_category_id") or "").strip()

    linked_expense_response = await api_client.get(
        f"/api/v1/finance/expenses/{linked_expense_id}",
        headers=expense_headers,
    )
    assert linked_expense_response.status_code == 200, linked_expense_response.text
    linked_expense = extract_data(linked_expense_response)
    assert float(linked_expense["amount"]) == float(created_transaction["amount"])
    assert str(linked_expense["expense_date"]) == str(created_transaction["transaction_date"])
    assert str(linked_expense["department_id"]) == str(created_transaction["department_id"])
    assert str(linked_expense["category_id"]) == str(created_transaction["expense_category_id"])

    update_response = await api_client.put(
        f"/api/v1/finance/cash-transactions/{created_transaction['id']}",
        headers=cash_headers,
        json={
            "amount": 4321.0,
            "title": f"Updated auto expense {uuid.uuid4().hex[:8]}",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_transaction = extract_data(update_response)
    assert str(updated_transaction["expense_id"]) == linked_expense_id

    updated_expense_response = await api_client.get(
        f"/api/v1/finance/expenses/{linked_expense_id}",
        headers=expense_headers,
    )
    assert updated_expense_response.status_code == 200, updated_expense_response.text
    updated_expense = extract_data(updated_expense_response)
    assert float(updated_expense["amount"]) == float(updated_transaction["amount"])


@pytest.mark.asyncio
async def test_expense_rejects_category_from_another_department(api_client) -> None:
    headers = make_auth_headers("expense")
    payload = await build_create_payload(api_client, "/api/v1/finance/expenses")
    payload["category_id"] = FACTORY_CATEGORY_ID

    response = await api_client.post(
        "/api/v1/finance/expenses",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "expense category must belong to the same department"


@pytest.mark.asyncio
async def test_cash_transaction_rejects_category_from_another_department(api_client) -> None:
    headers = make_auth_headers("cash_transaction")
    payload = await build_create_payload(api_client, "/api/v1/finance/cash-transactions")
    payload["transaction_type"] = "expense"
    payload["cash_account_id"] = EGG_CASH_ACCOUNT_ID
    payload["expense_category_id"] = FACTORY_CATEGORY_ID

    response = await api_client.post(
        "/api/v1/finance/cash-transactions",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "expense category must belong to the same department"
