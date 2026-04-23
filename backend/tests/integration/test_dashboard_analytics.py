from __future__ import annotations

import pytest

from tests.helpers import extract_data, make_admin_headers

@pytest.mark.asyncio
async def test_dashboard_analytics_requires_authentication(api_client) -> None:
    response = await api_client.get("/api/v1/dashboard/analytics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_analytics_requires_dashboard_read_for_non_admin(api_client) -> None:
    forbidden_response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers={
            "X-Employee-Id": "70111111-1111-1111-1111-111111111111",
            "X-Roles": "viewer",
            "X-Permissions": "",
        },
    )
    assert forbidden_response.status_code == 403


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_egg_farm_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    egg_module = next(module for module in modules if module["key"] == "egg_farm")

    kpis = {item["key"] for item in egg_module["kpis"]}
    assert {
        "net_eggs",
        "loss_rate",
        "shipment_volume",
        "financial_result",
        "total_expenses",
    } <= kpis

    chart_keys = {chart["key"] for chart in egg_module["charts"]}
    assert {"egg_output_daily"} <= chart_keys

    table_keys = {table["key"] for table in egg_module["tables"]}
    assert {"egg_clients"} <= table_keys


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_incubation_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    incubation_module = next(module for module in modules if module["key"] == "incubation")

    kpis = {item["key"] for item in incubation_module["kpis"]}
    assert {
        "eggs_set",
        "chicks_hatched",
        "hatch_rate",
        "chicks_dispatched",
        "financial_result",
        "total_expenses",
    } <= kpis

    chart_keys = {chart["key"] for chart in incubation_module["charts"]}
    assert {
        "incubation_egg_arrivals",
        "incubation_hatch",
    } <= chart_keys

    table_keys = {table["key"] for table in incubation_module["tables"]}
    assert {
        "incubation_active_batches",
        "incubation_clients",
    } <= table_keys


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_factory_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    factory_module = next(module for module in modules if module["key"] == "factory")

    kpis = {item["key"] for item in factory_module["kpis"]}
    assert {
        "total_birds",
        "mortality_rate",
        "fcr",
        "avg_weight_per_bird",
        "total_shipped",
        "financial_result",
        "total_expenses",
    } <= kpis


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_feed_mill_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    feed_module = next(module for module in modules if module["key"] == "feed_mill")

    kpis = {item["key"] for item in feed_module["kpis"]}
    assert {
        "product_output",
        "product_shipped",
        "shrinkage_pct",
        "financial_result",
        "total_expenses",
    } <= kpis

    table_keys = {table["key"] for table in feed_module["tables"]}
    assert {"feed_low_raw_stock"} <= table_keys


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_vet_pharmacy_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    vet_module = next(module for module in modules if module["key"] == "vet_pharmacy")

    kpis = {item["key"] for item in vet_module["kpis"]}
    assert {
        "expiring_batches",
        "expired_batches",
        "financial_result",
        "total_expenses",
    } <= kpis

    table_keys = {table["key"] for table in vet_module["tables"]}
    assert {"medicine_expiry_batches"} <= table_keys


@pytest.mark.asyncio
async def test_dashboard_analytics_exposes_full_slaughterhouse_operational_flow(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/analytics",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200, response.text

    payload = extract_data(response)
    modules = payload["department_dashboard"]["modules"]
    slaughter_module = next(module for module in modules if module["key"] == "slaughterhouse")

    kpis = {item["key"] for item in slaughter_module["kpis"]}
    assert {
        "birds_processed",
        "net_meat_share_pct",
        "waste_share_pct",
        "shipment_volume",
        "shipment_revenue",
        "financial_result",
        "total_expenses",
    } <= kpis

    chart_keys = {chart["key"] for chart in slaughter_module["charts"]}
    assert {"slaughter_semi_flow"} <= chart_keys

    table_keys = {table["key"] for table in slaughter_module["tables"]}
    assert {"slaughter_clients"} <= table_keys
