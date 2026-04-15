from __future__ import annotations

import uuid

import pytest

from tests.helpers import extract_data, make_admin_headers, make_auth_headers, run_crud_flow


HR_RESOURCES = [
    ("/api/v1/hr/employees", "employee"),
    ("/api/v1/hr/positions", "position"),
    ("/api/v1/hr/roles", "role"),
    ("/api/v1/hr/permissions", "permission"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", HR_RESOURCES)
async def test_hr_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)


@pytest.mark.asyncio
async def test_positions_are_managed_at_organization_scope(api_client) -> None:
    response = await api_client.get(
        "/api/v1/hr/positions",
        headers=make_auth_headers("position", role="viewer"),
    )
    assert response.status_code == 200, response.text

    items = extract_data(response)["items"]
    item_ids = {str(item["id"]) for item in items}
    organization_ids = {str(item["organization_id"]) for item in items}

    assert organization_ids == {"11111111-1111-1111-1111-111111111111"}
    assert "40111111-1111-1111-1111-111111111111" in item_ids
    assert "40222222-2222-2222-2222-222222222222" in item_ids
    assert len(items) > 1


@pytest.mark.asyncio
async def test_employee_work_times_accept_time_strings(api_client, sqlite_db) -> None:
    employee_id = str(uuid.uuid4())
    headers = make_admin_headers()

    response = await api_client.post(
        "/api/v1/hr/employees",
        json={
            "id": employee_id,
            "organization_id": "11111111-1111-1111-1111-111111111111",
            "first_name": "Time",
            "last_name": "Keeper",
            "email": f"time-{employee_id[:8]}@example.com",
            "organization_key": f"EMP-TIME-{employee_id[:8].upper()}",
            "password": "TempPass-123!",
            "work_start_time": "09:00",
            "work_end_time": "18:30",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    created = extract_data(response)
    assert str(created["work_start_time"]).startswith("09:00")
    assert str(created["work_end_time"]).startswith("18:30")

    stored_row = await sqlite_db.fetchrow(
        "SELECT work_start_time, work_end_time FROM employees WHERE id = $1",
        employee_id,
    )
    assert stored_row is not None
    assert str(stored_row["work_start_time"]).startswith("09:00")
    assert str(stored_row["work_end_time"]).startswith("18:30")

    response = await api_client.put(
        f"/api/v1/hr/employees/{employee_id}",
        json={
            "work_start_time": "08:15",
            "work_end_time": "17:45",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    updated = extract_data(response)
    assert str(updated["work_start_time"]).startswith("08:15")
    assert str(updated["work_end_time"]).startswith("17:45")
