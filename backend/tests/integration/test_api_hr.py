from __future__ import annotations

import pytest

from tests.helpers import run_crud_flow


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
