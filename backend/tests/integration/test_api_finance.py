from __future__ import annotations

import pytest

from tests.helpers import build_create_payload, extract_data, make_auth_headers, run_crud_flow


FINANCE_RESOURCES = [
    ("/api/v1/finance/expense-categories", "expense_category"),
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
