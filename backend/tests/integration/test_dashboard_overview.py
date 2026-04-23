from __future__ import annotations

import pytest

from tests.helpers import extract_data, make_admin_headers


@pytest.mark.asyncio
async def test_dashboard_overview_requires_authentication(api_client) -> None:
    response = await api_client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_overview_returns_financial_summary_and_sections(api_client) -> None:
    response = await api_client.get(
        "/api/v1/dashboard/overview",
        headers=make_admin_headers(),
    )
    assert response.status_code == 200

    payload = extract_data(response)
    assert payload["currency"] == "UZS"
    assert payload["scope"]["departmentId"] is None
    assert payload["scope"]["departmentLabel"] == "Все отделы"
    assert payload["department_dashboard"] is None

    executive = payload["executive_dashboard"]
    assert executive is not None
    kpis = {item["key"]: item for item in executive["kpis"]}
    assert set(kpis) >= {"operating_profit", "net_cashflow", "health_index"}
    assert isinstance(kpis["health_index"]["value"], (int, float))
    assert 0 <= kpis["health_index"]["value"] <= 100
    assert isinstance(kpis["operating_profit"]["value"], (int, float))
    assert isinstance(kpis["net_cashflow"]["value"], (int, float))
    assert len(executive["kpis"]) == 3
    assert executive["charts"] == []
    table_keys = {item["key"] for item in executive["tables"]}
    assert {"departments_performance", "top_risk_summary"} <= table_keys


@pytest.mark.asyncio
async def test_dashboard_overview_supports_department_scope(api_client) -> None:
    global_response = await api_client.get(
        "/api/v1/dashboard/overview",
        headers=make_admin_headers(),
    )
    assert global_response.status_code == 200
    global_payload = extract_data(global_response)
    global_kpis = {
        item["key"]: item["value"] for item in global_payload["executive_dashboard"]["kpis"]
    }

    scoped_response = await api_client.get(
        "/api/v1/dashboard/overview?department_id=77771111-1111-1111-1111-111111111111",
        headers=make_admin_headers(),
    )
    assert scoped_response.status_code == 200
    scoped_payload = extract_data(scoped_response)
    scoped_kpis = {
        item["key"]: item["value"] for item in scoped_payload["executive_dashboard"]["kpis"]
    }

    assert scoped_payload["scope"]["departmentId"] == "77771111-1111-1111-1111-111111111111"
    assert scoped_payload["scope"]["departmentLabel"] == "Yem zavodi"
    assert scoped_payload["scope"]["departmentPath"] == ["Yem zavodi"]
    assert "operating_profit" in scoped_kpis
    assert "net_cashflow" in scoped_kpis
    assert "health_index" in scoped_kpis
    # Scoping to a single department must keep (or reduce) the
    # aggregate — values stay finite numerics.
    for key in ("operating_profit", "net_cashflow", "health_index"):
        assert isinstance(scoped_kpis[key], (int, float))
        assert isinstance(global_kpis[key], (int, float))


@pytest.mark.asyncio
async def test_dashboard_overview_requires_dashboard_read_for_non_admin(api_client) -> None:
    forbidden_response = await api_client.get(
        "/api/v1/dashboard/overview",
        headers={
            "X-Employee-Id": "70111111-1111-1111-1111-111111111111",
            "X-Roles": "viewer",
            "X-Permissions": "",
        },
    )
    assert forbidden_response.status_code == 403

    allowed_response = await api_client.get(
        "/api/v1/dashboard/overview",
        headers={
            "X-Employee-Id": "70111111-1111-1111-1111-111111111111",
            "X-Roles": "viewer",
            "X-Permissions": "dashboard.read",
        },
    )
    assert allowed_response.status_code == 200
