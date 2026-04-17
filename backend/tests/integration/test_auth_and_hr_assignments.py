from __future__ import annotations

import uuid

import pytest

from tests.helpers import extract_data, make_admin_headers, make_auth_headers


ADMIN_USERNAME = "EMP-ADM-00"
ADMIN_PASSWORD = "changeme"
EMPLOYEE_USERNAME = "EMP-ALH-01"
EMPLOYEE_PASSWORD = "changeme"
EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
EMPLOYEE_PRIMARY_ROLE_ID = "50111111-1111-1111-1111-111111111111"
EXPENSE_CATEGORY_READ_PERMISSION_ID = "60411111-1111-1111-1111-111111111111"


async def _login(api_client, username: str, password: str) -> dict[str, object]:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return extract_data(response)


def _bearer_headers(access_token: str, *, role_override: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {access_token}"}
    if role_override is not None:
        headers["X-Roles"] = role_override
    return headers


@pytest.mark.asyncio
async def test_auth_login_me_refresh_and_bearer_claims_are_server_verified(api_client) -> None:
    session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    access_token = str(session["accessToken"])
    refresh_token = str(session["refreshToken"])

    response = await api_client.get(
        "/api/v1/auth/me",
        headers=_bearer_headers(access_token, role_override="viewer"),
    )
    assert response.status_code == 200, response.text
    me = extract_data(response)
    assert me["employeeId"] == session["employeeId"]
    assert "admin" in me["roles"]

    response = await api_client.get(
        "/api/v1/hr/permissions",
        headers=_bearer_headers(access_token, role_override="viewer"),
    )
    assert response.status_code == 200, response.text

    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refreshToken": refresh_token},
    )
    assert response.status_code == 200, response.text
    refreshed_session = extract_data(response)
    assert refreshed_session["employeeId"] == session["employeeId"]
    assert refreshed_session["accessToken"] != access_token


@pytest.mark.asyncio
async def test_department_assignment_grants_implicit_read_for_own_module(api_client) -> None:
    employee_session = await _login(api_client, EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD)
    access_token = str(employee_session["accessToken"])

    assert employee_session["departmentId"] == "44444444-4444-4444-4444-444444444444"
    assert employee_session["departmentModuleKey"] == "egg"
    assert "egg_production.read" not in employee_session["permissions"]

    response = await api_client.get(
        "/api/v1/egg/production",
        headers=_bearer_headers(access_token),
    )
    assert response.status_code == 200, response.text

    response = await api_client.get(
        "/api/v1/feed/ingredients",
        headers=_bearer_headers(access_token),
    )
    assert response.status_code == 403, response.text


@pytest.mark.asyncio
async def test_role_permissions_and_employee_roles_can_be_managed_via_crud_fields(api_client) -> None:
    admin_session = await _login(api_client, ADMIN_USERNAME, ADMIN_PASSWORD)
    admin_headers = _bearer_headers(str(admin_session["accessToken"]))

    role_id = str(uuid.uuid4())
    response = await api_client.post(
        "/api/v1/hr/roles",
        json={
            "id": role_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "name": f"Finance reader {role_id[:8]}",
            "slug": f"finance-reader-{role_id[:8]}",
            "description": "Can read finance expense categories",
            "is_active": True,
            "permission_ids": [],
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    created_role = extract_data(response)
    assert created_role["permission_ids"] == []

    response = await api_client.put(
        f"/api/v1/hr/roles/{role_id}",
        json={"permission_ids": [EXPENSE_CATEGORY_READ_PERMISSION_ID]},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    updated_role = extract_data(response)
    assert updated_role["permission_ids"] == [EXPENSE_CATEGORY_READ_PERMISSION_ID]

    employee_session = await _login(api_client, EMPLOYEE_USERNAME, EMPLOYEE_PASSWORD)
    employee_headers = _bearer_headers(str(employee_session["accessToken"]))

    response = await api_client.get("/api/v1/finance/expense-categories", headers=employee_headers)
    assert response.status_code == 403, response.text

    response = await api_client.put(
        f"/api/v1/hr/employees/{EMPLOYEE_ID}",
        json={"role_ids": [EMPLOYEE_PRIMARY_ROLE_ID, role_id]},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    updated_employee = extract_data(response)
    assert sorted(updated_employee["role_ids"]) == sorted([EMPLOYEE_PRIMARY_ROLE_ID, role_id])

    response = await api_client.get("/api/v1/finance/expense-categories", headers=employee_headers)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_employee_password_is_hashed_not_returned_and_blank_update_keeps_existing_hash(
    api_client,
    sqlite_db,
) -> None:
    employee_id = str(uuid.uuid4())
    raw_password = "PlainPass-123!"
    admin_headers = make_admin_headers()

    response = await api_client.post(
        "/api/v1/hr/employees",
        json={
            "id": employee_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "first_name": "Security",
            "last_name": "Case",
            "email": f"security-{employee_id[:8]}@example.com",
            "organization_key": f"EMP-{employee_id[:8].upper()}",
            "password": raw_password,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    created_employee = extract_data(response)
    assert "password" not in created_employee

    stored_row = await sqlite_db.fetchrow(
        "SELECT password FROM employees WHERE id = $1",
        employee_id,
    )
    assert stored_row is not None
    original_hash = str(stored_row["password"])
    assert original_hash
    assert original_hash != raw_password

    response = await api_client.get(f"/api/v1/hr/employees/{employee_id}", headers=admin_headers)
    assert response.status_code == 200, response.text
    fetched_employee = extract_data(response)
    assert "password" not in fetched_employee

    response = await api_client.put(
        f"/api/v1/hr/employees/{employee_id}",
        json={
            "first_name": "Security Updated",
            "password": "",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    updated_employee = extract_data(response)
    assert updated_employee["first_name"] == "Security Updated"
    assert "password" not in updated_employee

    updated_row = await sqlite_db.fetchrow(
        "SELECT password FROM employees WHERE id = $1",
        employee_id,
    )
    assert updated_row is not None
    assert str(updated_row["password"]) == original_hash


@pytest.mark.asyncio
async def test_non_admin_cannot_change_employee_roles_even_with_employee_update_permission(api_client) -> None:
    response = await api_client.put(
        f"/api/v1/hr/employees/{EMPLOYEE_ID}",
        json={"role_ids": [EMPLOYEE_PRIMARY_ROLE_ID]},
        headers=make_auth_headers("employee", role="manager"),
    )
    assert response.status_code == 403, response.text
    payload = response.json()
    assert payload["error"]["code"] == "access_denied"


@pytest.mark.asyncio
async def test_non_admin_cannot_change_role_permissions_even_with_role_update_permission(api_client) -> None:
    response = await api_client.put(
        f"/api/v1/hr/roles/{EMPLOYEE_PRIMARY_ROLE_ID}",
        json={"permission_ids": [EXPENSE_CATEGORY_READ_PERMISSION_ID]},
        headers=make_auth_headers("role", role="manager"),
    )
    assert response.status_code == 403, response.text
    payload = response.json()
    assert payload["error"]["code"] == "access_denied"
