from __future__ import annotations

import uuid

import pytest

from tests.helpers import extract_data, make_admin_headers, make_auth_headers


HOME_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"


async def _get_department_warehouses(api_client, department_id: str) -> list[dict[str, object]]:
    response = await api_client.get(
        "/api/v1/core/warehouses",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text
    warehouses = extract_data(response)["items"]
    return [warehouse for warehouse in warehouses if warehouse["department_id"] == department_id]


@pytest.mark.asyncio
async def test_stock_balance_supports_explicit_warehouse_scope(api_client) -> None:
    warehouses = await _get_department_warehouses(api_client, HOME_DEPARTMENT_ID)
    default_warehouse = next(warehouse for warehouse in warehouses if warehouse["is_default"])

    response = await api_client.get(
        f"/api/v1/inventory/stock/balance?item_type=egg&warehouse_id={default_warehouse['id']}",
        headers=make_auth_headers("stock_movement"),
    )
    assert response.status_code == 200, response.text
    payload = extract_data(response)
    assert payload["warehouse_id"] == default_warehouse["id"]
    assert payload["items"]


@pytest.mark.asyncio
async def test_internal_transfer_supports_same_department_between_two_warehouses(api_client) -> None:
    create_warehouse_response = await api_client.post(
        "/api/v1/core/warehouses",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORGANIZATION_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "name": f"Transfer target {uuid.uuid4().hex[:4]}",
            "code": f"TR-{uuid.uuid4().hex[:6]}".upper(),
            "description": "Secondary warehouse for transfer integration test",
            "is_active": True,
        },
        headers=make_auth_headers("warehouse"),
    )
    assert create_warehouse_response.status_code == 201, create_warehouse_response.text
    target_warehouse = extract_data(create_warehouse_response)

    warehouses = await _get_department_warehouses(api_client, HOME_DEPARTMENT_ID)
    default_warehouse = next(warehouse for warehouse in warehouses if warehouse["is_default"])

    balance_response = await api_client.get(
        f"/api/v1/inventory/stock/balance?item_type=egg&warehouse_id={default_warehouse['id']}",
        headers=make_auth_headers("stock_movement"),
    )
    assert balance_response.status_code == 200, balance_response.text
    balance_payload = extract_data(balance_response)
    first_item_key = str(balance_payload["items"][0]["item_key"])

    transfer_response = await api_client.post(
        "/api/v1/inventory/stock/transfer",
        json={
            "item_type": "egg",
            "item_key": first_item_key,
            "quantity": 1,
            "unit": "pcs",
            "from_warehouse_id": default_warehouse["id"],
            "to_warehouse_id": target_warehouse["id"],
        },
        headers=make_auth_headers("stock_movement"),
    )
    assert transfer_response.status_code == 201, transfer_response.text
    transfer_payload = extract_data(transfer_response)
    assert transfer_payload["from_warehouse_id"] == default_warehouse["id"]
    assert transfer_payload["to_warehouse_id"] == target_warehouse["id"]
    assert transfer_payload["from_department_id"] == HOME_DEPARTMENT_ID
    assert transfer_payload["to_department_id"] == HOME_DEPARTMENT_ID


@pytest.mark.asyncio
async def test_internal_transfer_rejects_non_selectable_unit(api_client) -> None:
    create_warehouse_response = await api_client.post(
        "/api/v1/core/warehouses",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORGANIZATION_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "name": f"Transfer target {uuid.uuid4().hex[:4]}",
            "code": f"TR-{uuid.uuid4().hex[:6]}".upper(),
            "description": "Secondary warehouse for transfer integration test",
            "is_active": True,
        },
        headers=make_auth_headers("warehouse"),
    )
    assert create_warehouse_response.status_code == 201, create_warehouse_response.text
    target_warehouse = extract_data(create_warehouse_response)

    warehouses = await _get_department_warehouses(api_client, HOME_DEPARTMENT_ID)
    default_warehouse = next(warehouse for warehouse in warehouses if warehouse["is_default"])

    balance_response = await api_client.get(
        f"/api/v1/inventory/stock/balance?item_type=egg&warehouse_id={default_warehouse['id']}",
        headers=make_auth_headers("stock_movement"),
    )
    assert balance_response.status_code == 200, balance_response.text
    balance_payload = extract_data(balance_response)
    first_item_key = str(balance_payload["items"][0]["item_key"])

    transfer_response = await api_client.post(
        "/api/v1/inventory/stock/transfer",
        json={
            "item_type": "egg",
            "item_key": first_item_key,
            "quantity": 1,
            "unit": "dose",
            "from_warehouse_id": default_warehouse["id"],
            "to_warehouse_id": target_warehouse["id"],
        },
        headers=make_auth_headers("stock_movement"),
    )
    assert transfer_response.status_code == 400, transfer_response.text
    assert transfer_response.json()["error"]["message"] == "unit must be one of: pcs, kg, ltr"
