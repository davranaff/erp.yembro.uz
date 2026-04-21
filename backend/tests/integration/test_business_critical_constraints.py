from __future__ import annotations

import uuid

import pytest

from tests.helpers import extract_data, make_auth_headers


ORG_ID = "11111111-1111-1111-1111-111111111111"
HOME_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
OTHER_DEPARTMENT_ID = "55555555-5555-5555-5555-555555555555"
HOME_POULTRY_TYPE_ID = "b0000000-0000-0000-0000-000000000001"
HOME_CLIENT_ID = "e1111111-0000-0000-0000-000000000001"
HOME_MEDICINE_TYPE_ID = "92111111-1111-1111-1111-111111111101"
HOME_BATCH_ID = "93111111-1111-1111-1111-111111111101"
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
async def test_slaughter_arrival_requires_source(api_client) -> None:
    """External source on slaughter arrival must carry supplier_client_id."""
    response = await api_client.post(
        "/api/v1/slaughter/arrivals",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": ORG_ID,
            "department_id": HOME_DEPARTMENT_ID,
            "source_type": "external",
            "poultry_type_id": HOME_POULTRY_TYPE_ID,
            "arrived_on": "2026-03-24",
            "birds_received": 100,
        },
        headers=_headers("slaughter_arrival"),
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


@pytest.mark.asyncio
async def test_viewer_list_hides_other_department_records(api_client) -> None:
    """Viewer scoped to HOME_DEPARTMENT must not see medicine_batches from other depts.

    All fixture medicine_batches live in department 88881111/88882222 (medicine
    department). A viewer anchored to HOME_DEPARTMENT (44444444) should see an
    empty list, never a batch from elsewhere.
    """
    response = await api_client.get(
        "/api/v1/medicine/batches",
        headers=_headers("medicine_batch", role="viewer"),
    )
    assert response.status_code == 200
    items = extract_data(response).get("items", [])
    foreign = [row for row in items if row.get("department_id") != HOME_DEPARTMENT_ID]
    assert not foreign, f"viewer leaked {len(foreign)} records from other departments"


@pytest.mark.asyncio
async def test_posted_debt_is_immutable(api_client) -> None:
    """Client debts with posting_status='posted' reject user-facing updates.

    Existing fixture rows are marked posted by the F0.8 migration; editing
    them must return a validation error that mentions reversal.
    """
    existing_debt_id = "f1000000-0000-0000-0000-000000000001"
    response = await api_client.put(
        f"/api/v1/core/client-debts/{existing_debt_id}",
        json={"note": "attempt to mutate posted debt"},
        headers=_headers("client_debt"),
    )
    assert response.status_code == 400, response.text
    message = response.json()["error"]["message"]
    assert "posted" in message.lower() or "reversal" in message.lower()


@pytest.mark.asyncio
async def test_viewer_cannot_read_entity_from_other_department(api_client) -> None:
    """Direct GET by id on a cross-department entity must 403/404 for viewer."""
    other_dept_batch_id = "93111111-1111-1111-1111-111111111101"
    response = await api_client.get(
        f"/api/v1/medicine/batches/{other_dept_batch_id}",
        headers=_headers("medicine_batch", role="viewer"),
    )
    assert response.status_code in (403, 404), (
        f"viewer in HOME_DEPT accessed medicine batch from another dept: "
        f"got {response.status_code}"
    )
