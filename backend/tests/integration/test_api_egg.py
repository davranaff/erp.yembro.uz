from __future__ import annotations

import pytest

from tests.helpers import run_crud_flow


EGG_RESOURCES = [
    ("/api/v1/egg/production", "egg_production"),
    ("/api/v1/egg/shipments", "egg_shipment"),
    ("/api/v1/egg/monthly-analytics", "egg_monthly_analytics"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", EGG_RESOURCES)
async def test_egg_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)
