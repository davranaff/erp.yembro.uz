from __future__ import annotations

from datetime import date, timedelta
import uuid

import pytest

from tests.helpers import (
    assert_delete_conflict,
    extract_data,
    make_admin_headers,
    make_auth_headers,
    run_crud_flow,
)


CORE_RESOURCES = [
    ("/api/v1/core/organizations", "organization"),
    ("/api/v1/core/department-modules", "department_module"),
    ("/api/v1/core/departments", "department"),
    ("/api/v1/core/warehouses", "warehouse"),
    ("/api/v1/core/clients", "client"),
    ("/api/v1/core/client-debts", "client_debt"),
    ("/api/v1/core/currencies", "currency"),
    ("/api/v1/core/poultry-types", "poultry_type"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", CORE_RESOURCES)
async def test_core_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


@pytest.mark.asyncio
async def test_department_delete_returns_conflict_when_record_has_real_dependencies(api_client) -> None:
    await assert_delete_conflict(
        api_client,
        "/api/v1/core/departments",
        "department",
        "77771111-1111-1111-1111-111111111111",
    )


@pytest.mark.asyncio
async def test_workspace_modules_metadata_endpoint_returns_seeded_modules(api_client) -> None:
    response = await api_client.get(
        "/api/v1/core/workspace-modules",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    module_map = {item["key"]: item for item in payload["items"]}

    assert {"core", "egg", "finance", "hr"} <= set(module_map)
    assert bool(module_map["core"]["is_department_assignable"]) is False
    assert module_map["egg"]["analytics_section_key"] == "egg_farm"
    assert any(
        resource["permission_prefix"] == "egg_production"
        for resource in module_map["egg"]["resources"]
    )
    egg_resources = {
        str(resource.get("key") or "").strip().lower(): resource
        for resource in module_map["egg"]["resources"]
    }
    assert "warehouses" in egg_resources
    assert str(egg_resources["warehouses"].get("api_module_key") or "").strip().lower() == "core"
    assert str(egg_resources["warehouses"].get("permission_prefix") or "").strip().lower() == "warehouse"
    assert not any(
        str(resource.get("api_module_key") or "").strip().lower() == "finance"
        for resource in module_map["egg"]["resources"]
    )
    finance_resource_keys = {
        str(resource.get("key") or "").strip().lower()
        for resource in module_map["finance"]["resources"]
    }
    assert {"cash-transactions", "expenses", "client-debts", "currencies"} <= finance_resource_keys

    feed_resource_keys = {
        str(resource.get("key") or "").strip().lower()
        for resource in module_map["feed"]["resources"]
    }
    assert "warehouses" in feed_resource_keys
    assert "client-debts" not in {
        str(resource.get("key") or "").strip().lower()
        for resource in module_map["egg"]["resources"]
    }
    core_resource_keys = {
        str(resource.get("key") or "").strip().lower()
        for resource in module_map["core"]["resources"]
    }
    assert "client-debts" not in core_resource_keys
    assert "currencies" not in core_resource_keys


@pytest.mark.asyncio
async def test_client_notification_context_and_bulk_send_endpoint(api_client) -> None:
    context_response = await api_client.get(
        "/api/v1/core/clients/77777777-7777-7777-7777-777777777777/notification-context",
        headers=make_auth_headers("client"),
    )
    assert context_response.status_code == 200, context_response.text
    context_payload = extract_data(context_response)
    assert context_payload["client"]["id"] == "77777777-7777-7777-7777-777777777777"
    assert len(context_payload["templates"]) >= 1

    bulk_response = await api_client.post(
        "/api/v1/core/clients/notify/bulk",
        json={
            "client_ids": [
                "77777777-7777-7777-7777-777777777777",
                "88888888-8888-8888-8888-888888888888",
            ],
            "template_key": "debt_reminder",
            "channel": "telegram",
        },
        headers=make_auth_headers("client"),
    )
    assert bulk_response.status_code == 200, bulk_response.text
    bulk_payload = extract_data(bulk_response)
    assert bulk_payload["total"] == 2
    assert len(bulk_payload["items"]) == 2


@pytest.mark.asyncio
async def test_client_debt_rejects_due_date_before_issue_date(api_client) -> None:
    debt_id = "40404040-4040-4040-4040-404040404041"
    current_response = await api_client.get(
        f"/api/v1/core/client-debts/{debt_id}",
        headers=make_auth_headers("client_debt"),
    )
    assert current_response.status_code == 200, current_response.text
    current_payload = extract_data(current_response)
    issued_on = date.fromisoformat(str(current_payload["issued_on"]))
    invalid_due_on = (issued_on - timedelta(days=1)).isoformat()

    response = await api_client.put(
        f"/api/v1/core/client-debts/{debt_id}",
        json={
            "due_on": invalid_due_on,
        },
        headers=make_auth_headers("client_debt"),
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "due_on cannot be before issued_on"


@pytest.mark.asyncio
async def test_departments_accept_database_backed_module_keys(api_client) -> None:
    department_module_headers = make_auth_headers("department_module")
    department_headers = make_auth_headers("department")
    module_id = str(uuid.uuid4())
    module_key = f"custom-{uuid.uuid4().hex[:8]}"

    create_module_response = await api_client.post(
        "/api/v1/core/department-modules",
        json={
            "id": module_id,
            "key": module_key,
            "name": "Custom department module",
            "description": "Created by integration test",
            "icon": "waypoints",
            "sort_order": 99,
            "is_active": True,
        },
        headers=department_module_headers,
    )
    assert create_module_response.status_code == 201
    created_module = extract_data(create_module_response)
    assert created_module["key"] == module_key

    first_department_id = str(uuid.uuid4())
    create_department_response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": first_department_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "Custom module department",
            "code": f"CM-{uuid.uuid4().hex[:6]}",
            "module_key": module_key,
            "icon": "waypoints",
            "description": "Department on dynamic module",
            "is_active": True,
        },
        headers=department_headers,
    )
    assert create_department_response.status_code == 201
    created_department = extract_data(create_department_response)
    assert created_department["module_key"] == module_key

    deactivate_module_response = await api_client.put(
        f"/api/v1/core/department-modules/{module_id}",
        json={"is_active": False},
        headers=department_module_headers,
    )
    assert deactivate_module_response.status_code == 200

    second_department_response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "Inactive module department",
            "code": f"IM-{uuid.uuid4().hex[:6]}",
            "module_key": module_key,
            "icon": "waypoints",
            "description": "Should fail",
            "is_active": True,
        },
        headers=department_headers,
    )
    assert second_department_response.status_code == 400
    error_payload = second_department_response.json()
    raw_error = error_payload.get("error")
    error_message = error_payload.get("detail")
    if error_message is None and isinstance(raw_error, dict):
        error_message = raw_error.get("message")
    if error_message is None and isinstance(raw_error, str):
        error_message = raw_error
    assert error_message == "module_key is inactive"


@pytest.mark.asyncio
async def test_departments_reject_non_assignable_workspace_modules(api_client) -> None:
    response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "Finance department should fail",
            "code": f"FN-{uuid.uuid4().hex[:6]}",
            "module_key": "finance",
            "icon": "coins",
            "description": "Should not be allowed",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "module_key cannot be assigned to departments"


@pytest.mark.asyncio
async def test_departments_reject_second_root_department_for_same_module(api_client) -> None:
    response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": "Second egg root",
            "code": f"EG-{uuid.uuid4().hex[:6]}",
            "module_key": "egg",
            "icon": "waypoints",
            "description": "Should fail because egg already has a root department",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["message"] == "Only one root department is allowed for each module"


@pytest.mark.asyncio
async def test_departments_allow_nested_department_under_existing_module_root(api_client) -> None:
    response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "parent_department_id": "44444444-4444-4444-4444-444444444444",
            "name": "Egg nested integration department",
            "code": f"EN-{uuid.uuid4().hex[:6]}",
            "module_key": "egg",
            "icon": "waypoints",
            "description": "Nested department should still be allowed",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert response.status_code == 201, response.text
    payload = extract_data(response)
    assert payload["parent_department_id"] == "44444444-4444-4444-4444-444444444444"
    assert payload["module_key"] == "egg"


@pytest.mark.asyncio
async def test_departments_generate_uuid_when_create_payload_has_no_id(api_client) -> None:
    response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "parent_department_id": "44444444-4444-4444-4444-444444444444",
            "name": "Egg nested department without explicit id",
            "code": f"EI-{uuid.uuid4().hex[:6]}",
            "module_key": "egg",
            "icon": "waypoints",
            "description": "Backend should generate id automatically",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert response.status_code == 201, response.text
    payload = extract_data(response)
    assert uuid.UUID(payload["id"])


@pytest.mark.asyncio
async def test_department_create_auto_creates_default_warehouse(api_client) -> None:
    department_id = str(uuid.uuid4())
    create_response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": department_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "parent_department_id": "77771111-1111-1111-1111-111111111111",
            "name": "Warehouse seeded department",
            "code": f"WHS-{uuid.uuid4().hex[:5]}",
            "module_key": "feed",
            "icon": "warehouse",
            "description": "Should receive a default warehouse",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert create_response.status_code == 201, create_response.text

    warehouse_list_response = await api_client.get(
        "/api/v1/core/warehouses",
        headers=make_admin_headers(),
    )
    assert warehouse_list_response.status_code == 200, warehouse_list_response.text
    warehouses = extract_data(warehouse_list_response)["items"]
    matching = [warehouse for warehouse in warehouses if warehouse["department_id"] == department_id]
    assert len(matching) == 1
    assert bool(matching[0]["is_default"]) is True
    assert matching[0]["name"] == "Asosiy ombor"


@pytest.mark.asyncio
async def test_department_create_syncs_missing_permissions_for_department_organization(api_client) -> None:
    organization_id = "11111111-1111-1111-1111-111111111111"
    target_permission_code = "dashboard.read"

    initial_permissions_response = await api_client.get(
        "/api/v1/hr/permissions",
        headers=make_admin_headers(),
    )
    assert initial_permissions_response.status_code == 200, initial_permissions_response.text
    initial_permissions = extract_data(initial_permissions_response)["items"]

    permission_to_delete = next(
        (
            item
            for item in initial_permissions
            if str(item.get("organization_id")) == organization_id
            and str(item.get("code")).strip().lower() == target_permission_code
        ),
        None,
    )
    assert permission_to_delete is not None

    delete_response = await api_client.delete(
        f"/api/v1/hr/permissions/{permission_to_delete['id']}",
        headers=make_admin_headers(),
    )
    assert delete_response.status_code == 200, delete_response.text

    create_department_response = await api_client.post(
        "/api/v1/core/departments",
        json={
            "id": str(uuid.uuid4()),
            "organization_id": organization_id,
            "parent_department_id": "44444444-4444-4444-4444-444444444444",
            "name": "Department permission sync trigger",
            "code": f"PS-{uuid.uuid4().hex[:6]}",
            "module_key": "egg",
            "icon": "waypoints",
            "description": "Should trigger organization permission sync",
            "is_active": True,
        },
        headers=make_auth_headers("department"),
    )
    assert create_department_response.status_code == 201, create_department_response.text

    synced_permissions_response = await api_client.get(
        "/api/v1/hr/permissions",
        headers=make_admin_headers(),
    )
    assert synced_permissions_response.status_code == 200, synced_permissions_response.text
    synced_permissions = extract_data(synced_permissions_response)["items"]

    recreated_permission = next(
        (
            item
            for item in synced_permissions
            if str(item.get("organization_id")) == organization_id
            and str(item.get("code")).strip().lower() == target_permission_code
        ),
        None,
    )
    assert recreated_permission is not None
    assert bool(recreated_permission.get("is_active")) is True
