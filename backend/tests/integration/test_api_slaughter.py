from __future__ import annotations

from decimal import Decimal

import pytest

from tests.helpers import build_create_payload, extract_data, make_admin_headers, make_auth_headers, run_crud_flow


SLAUGHTER_RESOURCES = [
    ("/api/v1/slaughter/processings", "slaughter_processing"),
    ("/api/v1/slaughter/semi-products", "slaughter_semi_product"),
    ("/api/v1/slaughter/semi-product-shipments", "slaughter_semi_product_shipment"),
    ("/api/v1/slaughter/quality-checks", "slaughter_quality_check"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", SLAUGHTER_RESOURCES)
async def test_slaughter_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


async def _find_debt_by_item_key(api_client, *, path: str, item_key: str) -> dict | None:
    response = await api_client.get(path, headers=make_admin_headers())
    assert response.status_code == 200
    items = extract_data(response)["items"]
    for item in items:
        if str(item.get("item_key") or "") == item_key:
            return item
    return None


@pytest.mark.asyncio
async def test_slaughter_shipment_auto_creates_and_removes_client_debt(api_client) -> None:
    headers = make_auth_headers("slaughter_semi_product_shipment")
    payload = await build_create_payload(api_client, "/api/v1/slaughter/semi-product-shipments")
    payload["unit_price"] = 25.5
    payload["quantity"] = 4

    create_response = await api_client.post(
        "/api/v1/slaughter/semi-product-shipments",
        headers=headers,
        json=payload,
    )
    assert create_response.status_code == 201, create_response.text
    shipment = extract_data(create_response)
    shipment_id = str(shipment["id"])

    debt = await _find_debt_by_item_key(
        api_client,
        path="/api/v1/core/client-debts",
        item_key=f"slaughter_shipment:{shipment_id}",
    )
    assert debt is not None, "auto-AR client_debt should be created on shipment create"
    assert Decimal(str(debt["amount_total"])) == Decimal("102.00")
    assert str(debt["client_id"]) == str(shipment["client_id"])
    assert str(debt["currency"]) == str(shipment["currency"])

    update_response = await api_client.put(
        f"/api/v1/slaughter/semi-product-shipments/{shipment_id}",
        headers=headers,
        json={"unit_price": 30.0, "quantity": 5},
    )
    assert update_response.status_code == 200, update_response.text

    updated_debt = await _find_debt_by_item_key(
        api_client,
        path="/api/v1/core/client-debts",
        item_key=f"slaughter_shipment:{shipment_id}",
    )
    assert updated_debt is not None
    assert Decimal(str(updated_debt["amount_total"])) == Decimal("150.00")

    delete_response = await api_client.delete(
        f"/api/v1/slaughter/semi-product-shipments/{shipment_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    deleted_debt = await _find_debt_by_item_key(
        api_client,
        path="/api/v1/core/client-debts",
        item_key=f"slaughter_shipment:{shipment_id}",
    )
    assert deleted_debt is None, "auto-AR client_debt should be removed on shipment delete"


@pytest.mark.asyncio
async def test_external_slaughter_arrival_auto_creates_and_removes_supplier_debt(api_client) -> None:
    headers = make_auth_headers("slaughter_processing")
    list_response = await api_client.get(
        "/api/v1/slaughter/processings",
        headers=make_admin_headers(),
    )
    items = extract_data(list_response)["items"]
    external_items = [
        item for item in items if str(item.get("source_type") or "") == "external"
    ]
    if not external_items:
        pytest.skip("no external slaughter processing fixture available")

    template = external_items[0]
    template_payload = await build_create_payload(api_client, "/api/v1/slaughter/processings")
    template_payload["source_type"] = "external"
    template_payload["factory_shipment_id"] = None
    template_payload["supplier_client_id"] = template["supplier_client_id"]
    template_payload["arrival_total_weight_kg"] = 100.0
    template_payload["arrival_unit_price"] = 5.0
    template_payload["arrival_currency"] = template.get("arrival_currency") or "UZS"

    create_response = await api_client.post(
        "/api/v1/slaughter/processings",
        headers=headers,
        json=template_payload,
    )
    assert create_response.status_code == 201, create_response.text
    processing = extract_data(create_response)
    processing_id = str(processing["id"])

    debt = await _find_debt_by_item_key(
        api_client,
        path="/api/v1/finance/supplier-debts",
        item_key=f"slaughter_arrival:{processing_id}",
    )
    assert debt is not None, "auto-AP supplier_debt should be created on external arrival"
    assert Decimal(str(debt["amount_total"])) == Decimal("500.00")
    assert str(debt["client_id"]) == str(template["supplier_client_id"])

    delete_response = await api_client.delete(
        f"/api/v1/slaughter/processings/{processing_id}",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text

    deleted_debt = await _find_debt_by_item_key(
        api_client,
        path="/api/v1/finance/supplier-debts",
        item_key=f"slaughter_arrival:{processing_id}",
    )
    assert deleted_debt is None, "auto-AP supplier_debt should be removed on processing delete"
