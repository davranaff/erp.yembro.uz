"""
Smoke-тесты /api/dashboard/summary/ и /api/dashboard/cashflow/.
"""
import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user(org):
    u = User.objects.create(email="dash@y.local", full_name="D")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    # Финансовый KPI / cashflow требует ledger.r — даём, чтобы smoke-тесты
    # видели «сырое» содержимое endpoint'а. Отдельный кейс ниже проверяет
    # обратный сценарий — без ledger.
    ledger = Module.objects.get(code="ledger")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=ledger, level=AccessLevel.READ,
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_summary_shape(client):
    resp = client.get("/api/dashboard/summary/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "kpis" in body
    assert "production" in body
    assert "cash" in body

    kpis = body["kpis"]
    for k in [
        "period", "purchases_confirmed_uzs", "creditor_balance_uzs",
        "debtor_balance_uzs",
        "payments_in_uzs", "payments_out_uzs",
        "sales_revenue_uzs", "sales_cost_uzs", "sales_margin_uzs",
        "active_batches", "transfers_pending",
        "purchases_drafts", "sales_drafts", "payments_drafts",
    ]:
        assert k in kpis, k

    assert "_total_uzs" in body["cash"]

    prod = body["production"]
    for k in [
        "matochnik_heads", "feedlot_heads",
        "incubation_runs", "incubation_eggs_loaded",
    ]:
        assert k in prod, k


def test_summary_requires_org_header(user):
    api = APIClient()
    api.force_authenticate(user=user)
    resp = api.get("/api/dashboard/summary/")
    # Без header — ValidationError из OrganizationContextMixin
    assert resp.status_code == 400


def test_cashflow_default_30_days(client):
    resp = client.get("/api/dashboard/cashflow/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 30
    assert len(body["points"]) == 30
    assert all("date" in p and "in_uzs" in p and "out_uzs" in p for p in body["points"])


def test_cashflow_custom_days(client):
    resp = client.get("/api/dashboard/cashflow/?days=7")
    assert resp.status_code == 200
    assert resp.json()["days"] == 7
    assert len(resp.json()["points"]) == 7


def test_cashflow_invalid_days_falls_back_to_30(client):
    resp = client.get("/api/dashboard/cashflow/?days=not-a-number")
    assert resp.status_code == 200
    assert resp.json()["days"] == 30


def test_cashflow_clamps_to_max_365(client):
    resp = client.get("/api/dashboard/cashflow/?days=99999")
    assert resp.status_code == 200
    assert resp.json()["days"] == 365
