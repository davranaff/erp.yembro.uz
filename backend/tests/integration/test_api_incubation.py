from __future__ import annotations

import pytest

from tests.helpers import run_crud_flow


INCUBATION_RESOURCES = [
    ("/api/v1/incubation/chick-shipments", "chick_shipment"),
    ("/api/v1/incubation/batches", "incubation_batch"),
    ("/api/v1/incubation/runs", "incubation_run"),
    ("/api/v1/incubation/monthly-analytics", "incubation_monthly_analytics"),
    ("/api/v1/incubation/factory-monthly-analytics", "factory_monthly_analytics"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", INCUBATION_RESOURCES)
async def test_incubation_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)
