from __future__ import annotations

import pytest

from tests.helpers import build_create_payload, extract_data, make_auth_headers, run_crud_flow


FEED_RESOURCES = [
    ("/api/v1/feed/types", "feed_type"),
    ("/api/v1/feed/ingredients", "feed_ingredient"),
    ("/api/v1/feed/arrivals", "feed_arrival"),
    ("/api/v1/feed/formulas", "feed_formula"),
    ("/api/v1/feed/formula-ingredients", "feed_formula_ingredient"),
    ("/api/v1/feed/raw-arrivals", "feed_raw_arrival"),
    ("/api/v1/feed/production-batches", "feed_production_batch"),
    ("/api/v1/feed/raw-consumptions", "feed_raw_consumption"),
    ("/api/v1/feed/product-shipments", "feed_product_shipment"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", FEED_RESOURCES)
async def test_feed_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


@pytest.mark.asyncio
async def test_feed_ingredient_delete_returns_descriptive_conflict_for_real_dependencies(api_client) -> None:
    response = await api_client.delete(
        "/api/v1/feed/ingredients/06171717-1717-1717-1717-171717171717",
        headers=make_auth_headers("feed_ingredient"),
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    message = str(payload["error"]["message"])
    assert message.startswith("Cannot delete this ingredient because it is still used in ")
    assert "formula ingredients (2)" in message
    assert "raw arrivals (2)" in message
    assert "raw consumptions (" in message


@pytest.mark.asyncio
async def test_feed_arrival_create_autofills_organization_and_department_from_actor(api_client) -> None:
    headers = make_auth_headers("feed_arrival")
    me_response = await api_client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200, me_response.text
    me_payload = extract_data(me_response)

    payload = await build_create_payload(api_client, "/api/v1/feed/arrivals")
    payload.pop("organization_id", None)
    payload.pop("department_id", None)

    create_response = await api_client.post("/api/v1/feed/arrivals", json=payload, headers=headers)
    assert create_response.status_code == 201, create_response.text
    created = extract_data(create_response)
    assert created["organization_id"] == me_payload["organizationId"]
    assert created["department_id"] == me_payload["departmentId"]

    delete_response = await api_client.delete(
        f"/api/v1/feed/arrivals/{created['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 200, delete_response.text
