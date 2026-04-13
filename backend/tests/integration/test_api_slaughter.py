from __future__ import annotations

import pytest

from tests.helpers import run_crud_flow


SLAUGHTER_RESOURCES = [
    ("/api/v1/slaughter/arrivals", "slaughter_arrival"),
    ("/api/v1/slaughter/processings", "slaughter_processing"),
    ("/api/v1/slaughter/semi-products", "slaughter_semi_product"),
    ("/api/v1/slaughter/semi-product-shipments", "slaughter_semi_product_shipment"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path,prefix", SLAUGHTER_RESOURCES)
async def test_slaughter_crud_endpoints_are_protected_and_work(api_client, path: str, prefix: str) -> None:
    await run_crud_flow(api_client, path, prefix)
