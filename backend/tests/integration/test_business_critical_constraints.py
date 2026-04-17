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
        "/api/v1/egg/quality-checks",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "production_id": production_id,
            "checked_on": NON_CONFLICT_EGG_DATE,
            "status": "passed",
            "grade": "large",
        },
        headers=_headers("egg_quality_check"),
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
async def test_slaughter_processing_requires_source(api_client) -> None:
    response = await api_client.post(
        "/api/v1/slaughter/processings",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "source_type": "external",
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "arrived_on": "2026-03-24",
            "birds_received": 100,
            "processed_on": "2026-03-25",
            "birds_processed": 100,
            "first_sort_count": 60,
            "second_sort_count": 30,
            "bad_count": 10,
        },
        headers=_headers("slaughter_processing"),
    )
    assert response.status_code == 400, response.text
    assert "supplier_client_id is required" in response.json()["error"]["message"]


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
