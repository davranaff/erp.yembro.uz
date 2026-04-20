from __future__ import annotations

import uuid

import pytest

from tests.helpers import TEST_EMPLOYEE_ID, extract_data


DEPARTMENTS_PATH = "/api/v1/core/departments"
VISIBLE_DEPARTMENTS_PATH = "/api/v1/core/visible-departments"
PRIMARY_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
UNRELATED_DEPARTMENT_ID = "55555555-5555-5555-5555-555555555555"
HOME_DEPARTMENT_ID = "44444444-4444-4444-4444-444444444444"
HOME_CHILD_DEPARTMENT_ID = "44441111-1111-1111-1111-111111111111"
SECOND_ORGANIZATION_DEPARTMENT_ID = "66666666-6666-6666-6666-666666666666"
HOME_CHILD_EMPLOYEE_ID = "70888888-8888-8888-8888-888888888888"


def _headers(
    *,
    employee_id: str = TEST_EMPLOYEE_ID,
    role: str = "viewer",
    permissions: str = "",
) -> dict[str, str]:
    return {
        "X-Employee-Id": employee_id,
        "X-Roles": role,
        "X-Permissions": permissions,
    }


@pytest.mark.asyncio
async def test_department_head_can_manage_only_own_scope_and_cannot_delete_headed_department(
    api_client,
) -> None:
    admin_headers = _headers(role="admin")
    head_headers = _headers()
    managed_parent_id = str(uuid.uuid4())
    managed_child_id = str(uuid.uuid4())
    managed_grandchild_id = str(uuid.uuid4())

    response = await api_client.post(
        DEPARTMENTS_PATH,
        json={
            "id": managed_parent_id,
            "organization_id": PRIMARY_ORGANIZATION_ID,
            "parent_department_id": HOME_DEPARTMENT_ID,
            "name": f"Head managed {managed_parent_id[:8]}",
            "code": f"HD-{managed_parent_id[:8]}",
            "module_key": "egg",
            "description": "Managed by department head",
            "head_id": TEST_EMPLOYEE_ID,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.post(
        DEPARTMENTS_PATH,
        json={
            "id": managed_child_id,
            "organization_id": PRIMARY_ORGANIZATION_ID,
            "parent_department_id": managed_parent_id,
            "name": f"Head child {managed_child_id[:8]}",
            "code": f"HC-{managed_child_id[:8]}",
            "module_key": "egg",
            "description": "Nested department managed by head",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.get(DEPARTMENTS_PATH, headers=head_headers)
    assert response.status_code == 200, response.text
    list_payload = extract_data(response)
    visible_ids = {item["id"] for item in list_payload["items"]}
    assert managed_parent_id in visible_ids
    assert managed_child_id in visible_ids
    assert UNRELATED_DEPARTMENT_ID not in visible_ids

    response = await api_client.get(f"{DEPARTMENTS_PATH}/{UNRELATED_DEPARTMENT_ID}", headers=head_headers)
    assert response.status_code == 403, response.text

    response = await api_client.put(
        f"{DEPARTMENTS_PATH}/{managed_parent_id}",
        json={"description": "Updated by department head"},
        headers=head_headers,
    )
    assert response.status_code == 200, response.text
    updated_parent = extract_data(response)
    assert updated_parent["description"] == "Updated by department head"

    response = await api_client.post(
        DEPARTMENTS_PATH,
        json={
            "id": managed_grandchild_id,
            "organization_id": PRIMARY_ORGANIZATION_ID,
            "parent_department_id": managed_child_id,
            "name": f"Head grandchild {managed_child_id[:6]}",
            "code": f"HG-{managed_child_id[:6]}",
            "module_key": "egg",
            "description": "Created by department head",
            "is_active": True,
        },
        headers=head_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.delete(f"{DEPARTMENTS_PATH}/{managed_parent_id}", headers=head_headers)
    assert response.status_code == 403, response.text

    response = await api_client.delete(f"{DEPARTMENTS_PATH}/{managed_child_id}", headers=head_headers)
    assert response.status_code == 200, response.text
    delete_payload = extract_data(response)
    assert delete_payload["deleted"] is True


@pytest.mark.asyncio
async def test_visible_departments_returns_only_home_department_for_regular_employee(api_client) -> None:
    response = await api_client.get(VISIBLE_DEPARTMENTS_PATH, headers=_headers())
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    visible_ids = {item["id"] for item in payload["items"]}

    assert HOME_DEPARTMENT_ID in visible_ids
    assert HOME_CHILD_DEPARTMENT_ID not in visible_ids
    assert UNRELATED_DEPARTMENT_ID not in visible_ids
    assert SECOND_ORGANIZATION_DEPARTMENT_ID not in visible_ids


@pytest.mark.asyncio
async def test_visible_departments_does_not_include_parent_for_subdepartment_employee(api_client) -> None:
    response = await api_client.get(
        VISIBLE_DEPARTMENTS_PATH,
        headers=_headers(employee_id=HOME_CHILD_EMPLOYEE_ID),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    visible_ids = {item["id"] for item in payload["items"]}

    assert HOME_CHILD_DEPARTMENT_ID in visible_ids
    assert HOME_DEPARTMENT_ID not in visible_ids
    assert UNRELATED_DEPARTMENT_ID not in visible_ids


@pytest.mark.asyncio
async def test_visible_departments_returns_all_departments_for_department_managers(api_client) -> None:
    response = await api_client.get(
        VISIBLE_DEPARTMENTS_PATH,
        headers=_headers(permissions="department.write"),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    visible_ids = {item["id"] for item in payload["items"]}

    assert HOME_DEPARTMENT_ID in visible_ids
    assert HOME_CHILD_DEPARTMENT_ID in visible_ids
    assert UNRELATED_DEPARTMENT_ID in visible_ids
    assert SECOND_ORGANIZATION_DEPARTMENT_ID not in visible_ids


@pytest.mark.asyncio
async def test_visible_departments_returns_all_departments_for_admin_role(api_client) -> None:
    response = await api_client.get(
        VISIBLE_DEPARTMENTS_PATH,
        headers=_headers(role="admin"),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    visible_ids = {item["id"] for item in payload["items"]}

    assert HOME_DEPARTMENT_ID in visible_ids
    assert HOME_CHILD_DEPARTMENT_ID in visible_ids
    assert UNRELATED_DEPARTMENT_ID in visible_ids
    assert SECOND_ORGANIZATION_DEPARTMENT_ID not in visible_ids


@pytest.mark.asyncio
async def test_visible_departments_includes_headed_and_descendant_departments(api_client) -> None:
    admin_headers = _headers(role="admin")
    headed_id = str(uuid.uuid4())
    descendant_id = str(uuid.uuid4())

    response = await api_client.post(
        DEPARTMENTS_PATH,
        json={
            "id": headed_id,
            "organization_id": PRIMARY_ORGANIZATION_ID,
            "parent_department_id": HOME_DEPARTMENT_ID,
            "name": f"Headed by test {headed_id[:8]}",
            "code": f"HV-{headed_id[:8]}",
            "module_key": "egg",
            "description": "Department headed for visibility test",
            "head_id": TEST_EMPLOYEE_ID,
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.post(
        DEPARTMENTS_PATH,
        json={
            "id": descendant_id,
            "organization_id": PRIMARY_ORGANIZATION_ID,
            "parent_department_id": headed_id,
            "name": f"Headed descendant {descendant_id[:8]}",
            "code": f"HD-{descendant_id[:8]}",
            "module_key": "egg",
            "description": "Child of headed department",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text

    response = await api_client.get(VISIBLE_DEPARTMENTS_PATH, headers=_headers())
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    visible_ids = {item["id"] for item in payload["items"]}

    assert HOME_DEPARTMENT_ID in visible_ids
    assert headed_id in visible_ids
    assert descendant_id in visible_ids
    assert UNRELATED_DEPARTMENT_ID not in visible_ids
