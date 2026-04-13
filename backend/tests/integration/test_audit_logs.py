from __future__ import annotations

import uuid

import pytest

from tests.helpers import build_create_payload, extract_data


ADMIN_USERNAME = "EMP-ADM-00"
ADMIN_PASSWORD = "changeme"
EMPLOYEE_USERNAME = "EMP-ALH-01"
EMPLOYEE_PASSWORD = "changeme"
EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
EMPLOYEE_PRIMARY_ROLE_ID = "50111111-1111-1111-1111-111111111111"
EXPENSE_CATEGORY_READ_PERMISSION_ID = "60411111-1111-1111-1111-111111111111"
REDACTED_AUDIT_VALUE = "***redacted***"


async def _login(api_client, username: str, password: str) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return extract_data(response)


def _bearer_headers(
    access_token: str,
    *,
    role_override: str | None = None,
    permission_override: str | None = None,
) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if role_override is not None:
        headers["X-Roles"] = role_override
    if permission_override is not None:
        headers["X-Permissions"] = permission_override
    return headers


@pytest.mark.asyncio
async def test_role_audit_history_tracks_create_update_delete_and_relation_changes(api_client) -> None:
    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))

    role_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/hr/roles",
        json={
            "id": role_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": f"Audit role {role_id[:8]}",
            "slug": f"audit-role-{role_id[:8]}",
            "description": "Initial description",
            "is_active": True,
            "permission_ids": [],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.put(
        f"/api/v1/hr/roles/{role_id}",
        json={
            "description": "Updated description",
            "permission_ids": [EXPENSE_CATEGORY_READ_PERMISSION_ID],
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    response = await api_client.delete(
        f"/api/v1/hr/roles/{role_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    response = await api_client.get(
        f"/api/v1/hr/roles/{role_id}/audit",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    history = extract_data(response)
    assert history["total"] == 3

    items = history["items"]
    assert [item["action"] for item in items] == ["delete", "update", "create"]
    assert items[0]["actor_username"] == ADMIN_USERNAME
    assert items[2]["after_data"]["permission_ids"] == []
    assert items[1]["before_data"]["permission_ids"] == []
    assert items[1]["after_data"]["permission_ids"] == [EXPENSE_CATEGORY_READ_PERMISSION_ID]
    assert {"description", "permission_ids"}.issubset(set(items[1]["changed_fields"]))
    assert items[0]["before_data"]["permission_ids"] == [EXPENSE_CATEGORY_READ_PERMISSION_ID]
    assert items[0]["after_data"] is None

    response = await api_client.get(
        f"/api/v1/system/audit?entity_table=roles&entity_id={role_id}",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    audit_feed = extract_data(response)
    assert audit_feed["total"] == 3
    assert {item["entity_id"] for item in audit_feed["items"]} == {role_id}


@pytest.mark.asyncio
async def test_employee_audit_redacts_password_and_keeps_role_ids(api_client) -> None:
    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))

    payload = await build_create_payload(api_client, "/api/v1/hr/employees")
    employee_id = str(payload["id"])
    payload["password"] = "topsecret123"
    payload["role_ids"] = [EMPLOYEE_PRIMARY_ROLE_ID]

    response = await api_client.post(
        "/api/v1/hr/employees",
        json=payload,
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.get(
        f"/api/v1/hr/employees/{employee_id}/audit",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    history = extract_data(response)
    assert history["total"] == 1

    item = history["items"][0]
    assert item["action"] == "create"
    assert item["after_data"]["password"] == REDACTED_AUDIT_VALUE
    assert item["after_data"]["role_ids"] == [EMPLOYEE_PRIMARY_ROLE_ID]


@pytest.mark.asyncio
async def test_auth_me_password_only_change_is_audited(api_client) -> None:
    employee_session = await _login(api_client, EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD)
    employee_headers = _bearer_headers(str(employee_session["accessToken"]))

    response = await api_client.get("/api/v1/auth/me", headers=employee_headers)
    assert response.status_code == 200, response.text
    profile = extract_data(response)

    response = await api_client.patch(
        "/api/v1/auth/me",
        json={
            "firstName": profile["firstName"],
            "lastName": profile["lastName"],
            "email": profile["email"],
            "phone": profile["phone"],
            "currentPassword": EMPLOYEE_PASSWORD,
            "newPassword": "changed-secret-123",
        },
        headers=employee_headers,
    )
    assert response.status_code == 200, response.text

    response = await api_client.post(
        "/api/v1/auth/login",
        json={"username": EMPLOYEE_USERNAME, "password": "changed-secret-123"},
    )
    assert response.status_code == 200, response.text

    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))
    response = await api_client.get(
        f"/api/v1/hr/employees/{EMPLOYEE_ID}/audit",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    history = extract_data(response)
    assert history["total"] == 1

    item = history["items"][0]
    assert item["action"] == "update"
    assert item["actor_username"] == EMPLOYEE_USERNAME
    assert "password" in item["changed_fields"]
    assert item["before_data"]["password"] == REDACTED_AUDIT_VALUE
    assert item["after_data"]["password"] == REDACTED_AUDIT_VALUE


@pytest.mark.asyncio
async def test_entity_audit_endpoint_requires_audit_read_permission(api_client) -> None:
    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))

    role_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/hr/roles",
        json={
            "id": role_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": f"Audit gated role {role_id[:8]}",
            "slug": f"audit-gated-role-{role_id[:8]}",
            "description": "Audit permission gate",
            "is_active": True,
            "permission_ids": [],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    employee_session = await _login(api_client, EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD)
    employee_headers = _bearer_headers(
        str(employee_session["accessToken"]),
        role_override="viewer",
        permission_override="role.read",
    )
    response = await api_client.get(
        f"/api/v1/hr/roles/{role_id}/audit",
        headers=employee_headers,
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_system_audit_feed_supports_changed_at_range_filters(api_client) -> None:
    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))

    role_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/hr/roles",
        json={
            "id": role_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": f"Audit range role {role_id[:8]}",
            "slug": f"audit-range-role-{role_id[:8]}",
            "description": "Range test role",
            "is_active": True,
            "permission_ids": [],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.put(
        f"/api/v1/hr/roles/{role_id}",
        json={"description": "Range test role updated"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text

    response = await api_client.get(
        f"/api/v1/hr/roles/{role_id}/audit",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    history = extract_data(response)
    assert history["total"] == 2

    items = history["items"]
    newest_changed_at = str(items[0]["changed_at"])
    oldest_changed_at = str(items[-1]["changed_at"])

    response = await api_client.get(
        f"/api/v1/system/audit?entity_table=roles&entity_id={role_id}&changed_from={newest_changed_at}",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    filtered_from = extract_data(response)
    assert filtered_from["total"] == 1
    assert [item["action"] for item in filtered_from["items"]] == ["update"]

    response = await api_client.get(
        f"/api/v1/system/audit?entity_table=roles&entity_id={role_id}&changed_to={oldest_changed_at}",
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    filtered_to = extract_data(response)
    assert filtered_to["total"] == 1
    assert [item["action"] for item in filtered_to["items"]] == ["create"]
