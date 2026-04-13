from __future__ import annotations

import uuid

import pytest

from tests.helpers import extract_data, make_auth_headers


ORG_ID = "11111111-1111-1111-1111-111111111111"
HOME_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
OTHER_DEPARTMENT_ID = "55555555-5555-5555-5555-555555555555"
HOME_POULTRY_TYPE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
HOME_CLIENT_ID = "77777777-7777-7777-7777-777777777777"
HOME_MEDICINE_TYPE_ID = "10101010-1010-1010-1010-101010101010"
HOME_BATCH_ID = "70707070-7070-7070-7070-707070707070"
HOME_SHIPMENT_ID = "11111111-1111-2222-3333-333333333333"
NON_CONFLICT_EGG_DATE = "2099-03-24"


def _headers(
    permission_prefix: str,
    *,
    role: str = "admin",
    employee_id: str = "70111111-1111-1111-1111-111111111111",
) -> dict[str, str]:
    headers = make_auth_headers(permission_prefix, role=role)
    headers["X-Employee-Id"] = employee_id
    return headers


@pytest.mark.asyncio
async def test_egg_shipment_rejects_negative_stock(api_client) -> None:
    production_id = str(uuid.uuid4())
    shipment_id = str(uuid.uuid4())

    response = await api_client.post(
        "/api/v1/egg/production",
        json={
            "id": production_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "produced_on": NON_CONFLICT_EGG_DATE,
            "eggs_collected": 100,
            "eggs_broken": 0,
            "eggs_rejected": 0,
            "total_shelled": 100,
            "note": "stock test",
        },
        headers=_headers("egg_production"),
    )
    assert response.status_code == 201, response.text

    response = await api_client.post(
        "/api/v1/egg/shipments",
        json={
            "id": shipment_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "production_id": production_id,
            "client_id": HOME_CLIENT_ID,
            "shipped_on": NON_CONFLICT_EGG_DATE,
            "eggs_count": 140,
            "eggs_broken": 0,
            "unit": "pcs",
            "unit_price": 1000,
            "currency": "UZS",
            "invoice_no": f"NEG-STOCK-{uuid.uuid4().hex[:8]}",
        },
        headers=_headers("egg_shipment"),
    )
    assert response.status_code == 400, response.text
    payload = response.json()
    assert payload["error"]["code"] == "validation_error"
    assert "Insufficient stock" in payload["error"]["message"]


@pytest.mark.asyncio
async def test_chick_arrival_requires_source_link_and_enforces_shipment_balance(api_client) -> None:
    missing_link_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/incubation/chick-arrivals",
        json={
            "id": missing_link_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "source_client_id": HOME_CLIENT_ID,
            "arrived_on": "2026-03-24",
            "chicks_count": 50,
            "unit_price": 1200,
            "currency": "UZS",
        },
        headers=_headers("chick_arrival"),
    )
    assert response.status_code == 400, response.text
    assert "Either run_id or chick_shipment_id is required" in response.json()["error"]["message"]

    over_limit_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/incubation/chick-arrivals",
        json={
            "id": over_limit_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "source_client_id": HOME_CLIENT_ID,
            "chick_shipment_id": HOME_SHIPMENT_ID,
            "arrived_on": "2026-03-24",
            "chicks_count": 9999,
            "unit_price": 1200,
            "currency": "UZS",
        },
        headers=_headers("chick_arrival"),
    )
    assert response.status_code == 400, response.text
    assert "Arrival exceeds shipment balance" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_slaughter_arrival_requires_chick_arrival_link(api_client) -> None:
    response = await api_client.post(
        "/api/v1/slaughter/arrivals",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "supplier_client_id": HOME_CLIENT_ID,
            "arrived_on": "2026-03-24",
            "birds_count": 100,
            "average_weight_kg": 2.2,
            "unit_price": 1100,
            "currency": "UZS",
            "invoice_no": f"S-REQ-{uuid.uuid4().hex[:8]}",
        },
        headers=_headers("slaughter_arrival"),
    )
    assert response.status_code == 400, response.text
    assert "chick_arrival_id is required" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_medicine_consumption_updates_remaining_and_blocks_overconsumption(api_client) -> None:
    before_response = await api_client.get(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}",
        headers=_headers("medicine_batch"),
    )
    assert before_response.status_code == 200, before_response.text
    before_batch = extract_data(before_response)
    before_remaining = float(before_batch["remaining_quantity"])

    consume_id = str(uuid.uuid4())
    consume_quantity = 25.0
    response = await api_client.post(
        "/api/v1/medicine/consumptions",
        json={
            "id": consume_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "batch_id": HOME_BATCH_ID,
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "client_id": HOME_CLIENT_ID,
            "consumed_on": "2026-03-24",
            "quantity": consume_quantity,
            "unit": "pcs",
            "purpose": "test consumption",
        },
        headers=_headers("medicine_consumption"),
    )
    assert response.status_code == 201, response.text

    after_response = await api_client.get(
        f"/api/v1/medicine/batches/{HOME_BATCH_ID}",
        headers=_headers("medicine_batch"),
    )
    assert after_response.status_code == 200, after_response.text
    after_batch = extract_data(after_response)
    after_remaining = float(after_batch["remaining_quantity"])
    assert after_remaining == pytest.approx(before_remaining - consume_quantity, rel=0, abs=0.001)

    response = await api_client.post(
        "/api/v1/medicine/consumptions",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "batch_id": HOME_BATCH_ID,
            "consumed_on": "2026-03-24",
            "quantity": 10_000,
            "unit": "pcs",
        },
        headers=_headers("medicine_consumption"),
    )
    assert response.status_code == 400, response.text
    assert "Consumption exceeds remaining batch quantity" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_medicine_consumption_rejects_expired_batch(api_client) -> None:
    expired_batch_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/medicine/batches",
        json={
            "id": expired_batch_id,
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "medicine_type_id": HOME_MEDICINE_TYPE_ID,
            "supplier_client_id": HOME_CLIENT_ID,
            "batch_code": f"EXP-{uuid.uuid4().hex[:8]}",
            "barcode": f"BAR-{uuid.uuid4().hex[:8]}",
            "arrived_on": "2026-01-01",
            "expiry_date": "2026-01-31",
            "received_quantity": 10,
            "remaining_quantity": 10,
            "unit": "pcs",
            "unit_cost": 3000,
            "currency": "UZS",
        },
        headers=_headers("medicine_batch"),
    )
    assert response.status_code == 201, response.text

    response = await api_client.post(
        "/api/v1/medicine/consumptions",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "batch_id": expired_batch_id,
            "consumed_on": "2026-03-24",
            "quantity": 1,
            "unit": "pcs",
        },
        headers=_headers("medicine_consumption"),
    )
    assert response.status_code == 400, response.text
    assert "Cannot consume expired medicine batch" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_non_privileged_user_cannot_create_records_in_other_department(api_client) -> None:
    response = await api_client.post(
        "/api/v1/egg/production",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": OTHER_DEPARTMENT_ID,
            "produced_on": NON_CONFLICT_EGG_DATE,
            "eggs_collected": 55,
            "eggs_broken": 0,
            "eggs_rejected": 0,
            "total_shelled": 55,
            "note": "scope check",
        },
        headers=_headers("egg_production", role="viewer"),
    )
    assert response.status_code == 201, response.text
    created = extract_data(response)
    assert created["department_id"] == HOME_DEPARTMENT_ID
