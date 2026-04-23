from __future__ import annotations

import pytest

from tests.helpers import TEST_EMPLOYEE_ID, build_create_payload


ALL_RESOURCES = [
    ("/api/v1/core/organizations", "organization"),
    ("/api/v1/core/department-modules", "department_module"),
    ("/api/v1/core/departments", "department"),
    ("/api/v1/core/clients", "client"),
    ("/api/v1/core/poultry-types", "poultry_type"),
    ("/api/v1/egg/production", "egg_production"),
    ("/api/v1/egg/shipments", "egg_shipment"),
    ("/api/v1/finance/expense-categories", "expense_category"),
    ("/api/v1/feed/types", "feed_type"),
    ("/api/v1/feed/ingredients", "feed_ingredient"),
    ("/api/v1/feed/formulas", "feed_formula"),
    ("/api/v1/feed/raw-arrivals", "feed_raw_arrival"),
    ("/api/v1/feed/production-batches", "feed_production_batch"),
    ("/api/v1/feed/raw-consumptions", "feed_raw_consumption"),
    ("/api/v1/feed/product-shipments", "feed_product_shipment"),
    ("/api/v1/hr/employees", "employee"),
    ("/api/v1/hr/positions", "position"),
    ("/api/v1/hr/roles", "role"),
    ("/api/v1/hr/permissions", "permission"),
    ("/api/v1/incubation/chick-shipments", "chick_shipment"),
    ("/api/v1/incubation/batches", "incubation_batch"),
    ("/api/v1/incubation/runs", "incubation_run"),
    ("/api/v1/medicine/batches", "medicine_batch"),
    ("/api/v1/medicine/types", "medicine_type"),
    ("/api/v1/slaughter/processings", "slaughter_processing"),
    ("/api/v1/slaughter/semi-products", "slaughter_semi_product"),
    ("/api/v1/slaughter/semi-product-shipments", "slaughter_semi_product_shipment"),
    ("/api/v1/slaughter/quality-checks", "slaughter_quality_check"),
]


def make_headers(role: str, permissions: list[str] | str | None = None) -> dict[str, str]:
    permissions_value = "" if permissions is None else ",".join(list(permissions) if isinstance(permissions, list) else [permissions])
    return {
        "X-Employee-Id": TEST_EMPLOYEE_ID,
        "X-Roles": role,
        "X-Permissions": permissions_value,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", ALL_RESOURCES)
async def test_manager_or_admin_role_can_access_without_permissions(api_client, path: str, prefix: str) -> None:
    role_headers = make_headers("manager")
    response = await api_client.get(path, headers=role_headers)
    assert response.status_code == 200

    create_payload = await build_create_payload(api_client, path)
    response = await api_client.post(path, json=create_payload, headers=role_headers)
    assert response.status_code == 201

    del_headers = make_headers("admin")
    response = await api_client.get(path, headers=del_headers)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", ALL_RESOURCES)
async def test_viewer_with_required_permissions_has_access(api_client, path: str, prefix: str) -> None:
    headers = make_headers("viewer", [f"{prefix}.read", f"{prefix}.list"])
    response = await api_client.get(path, headers=headers)
    assert response.status_code == 200

    create_payload = await build_create_payload(api_client, path)
    headers = make_headers("viewer", [f"{prefix}.create"])
    response = await api_client.post(path, json=create_payload, headers=headers)
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", ALL_RESOURCES)
async def test_viewer_without_required_permission_is_forbidden(api_client, path: str, prefix: str) -> None:
    headers = make_headers("viewer", ["other.resource"])
    response = await api_client.get(path, headers=headers)
    assert response.status_code == 403

    create_payload = await build_create_payload(api_client, path)
    headers = make_headers("viewer", [f"{prefix}.read"])
    response = await api_client.post(path, json=create_payload, headers=headers)
    assert response.status_code == 403
