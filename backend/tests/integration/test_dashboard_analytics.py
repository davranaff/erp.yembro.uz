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
        "current_stock",
        "shipment_volume",
        "eggs_to_incubation",
        "feed_consumed",
        "medicine_consumed",
        "client_base",
        "total_expenses",
        "financial_result",
        "net_cashflow",
        "cash_balance",
    } <= kpis

    chart_keys = {chart["key"] for chart in egg_module["charts"]}
    assert {
        "egg_output_daily",
        "egg_monthly_flow",
        "egg_destination_flow",
        "farm_feed_supply",
        "farm_medicine_usage",
        "egg_revenue_daily",
        "egg_finance_overview",
        "egg_expense_categories",
    } <= chart_keys

    table_keys = {table["key"] for table in egg_module["tables"]}
    assert {
        "egg_clients",
        "egg_destination_balance",
        "egg_feed_types",
        "egg_client_registry",
        "egg_recent_shipments",
        "egg_expense_categories_table",
        "egg_cash_accounts",
        "egg_recent_expenses",
    } <= table_keys


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
        "raw_arrivals",
        "raw_consumed",
        "product_output",
        "product_shipped",
        "client_base",
        "sales_revenue",
        "stock_total",
        "total_expenses",
        "financial_result",
        "net_cashflow",
        "cash_balance",
    } <= kpis

    chart_keys = {chart["key"] for chart in feed_module["charts"]}
    assert {
        "feed_raw_flow",
        "feed_product_flow",
        "feed_shipment_rate",
        "feed_revenue",
        "feed_ingredient_mix",
        "feed_finance_overview",
        "feed_expense_categories",
    } <= chart_keys

    table_keys = {table["key"] for table in feed_module["tables"]}
    assert {
        "feed_formulas",
        "feed_clients",
        "feed_client_registry",
        "feed_low_raw_stock",
        "feed_recent_batches",
        "feed_recent_shipments",
        "feed_expense_categories_table",
        "feed_cash_accounts",
        "feed_recent_expenses",
    } <= table_keys


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
        "medicine_arrivals",
        "medicine_consumed",
        "client_base",
        "current_stock",
        "expiring_batches",
        "expired_batches",
        "turnover_rate",
        "total_expenses",
        "financial_result",
        "net_cashflow",
        "cash_balance",
    } <= kpis

    chart_keys = {chart["key"] for chart in vet_module["charts"]}
    assert {
        "medicine_flow",
        "medicine_stock",
        "medicine_expiry",
        "medicine_turnover_rate",
        "medicine_finance_overview",
        "medicine_expense_categories",
    } <= chart_keys

    table_keys = {table["key"] for table in vet_module["tables"]}
    assert {
        "medicine_suppliers",
        "medicine_client_registry",
        "medicine_expiry_batches",
        "medicine_recent_batches",
        "medicine_latest_consumptions",
        "medicine_expense_categories_table",
        "medicine_cash_accounts",
        "medicine_recent_expenses",
    } <= table_keys


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
        "birds_arrived",
        "birds_processed",
        "first_sort_total",
        "second_sort_total",
        "bad_total",
        "semi_product_output",
        "shipment_volume",
        "client_base",
        "total_expenses",
        "financial_result",
        "net_cashflow",
        "cash_balance",
    } <= kpis

    chart_keys = {chart["key"] for chart in slaughter_module["charts"]}
    assert {
        "slaughter_flow",
        "slaughter_quality",
        "slaughter_semi_products",
        "slaughter_process_rate",
        "slaughter_semi_flow",
        "slaughter_revenue",
        "slaughter_finance_overview",
        "slaughter_expense_categories",
    } <= chart_keys

    table_keys = {table["key"] for table in slaughter_module["tables"]}
    assert {
        "slaughter_top_products",
        "slaughter_clients",
        "slaughter_client_registry",
        "slaughter_recent_arrivals",
        "slaughter_recent_processings",
        "slaughter_recent_shipments",
        "slaughter_expense_categories_table",
        "slaughter_cash_accounts",
        "slaughter_recent_expenses",
    } <= table_keys
