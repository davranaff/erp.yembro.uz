"""
Smoke-тесты /api/holding/companies/.
"""
import pytest
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user(org):
    u = User.objects.create(email="hold@y.local", full_name="H")
    OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_returns_companies_for_user(client, org):
    resp = client.get("/api/holding/companies/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "companies" in body
    assert "totals" in body
    codes = [c["code"] for c in body["companies"]]
    assert "DEFAULT" in codes


def test_totals_have_expected_keys(client):
    resp = client.get("/api/holding/companies/")
    assert resp.status_code == 200
    totals = resp.json()["totals"]
    assert "companies" in totals
    assert "modules" in totals
    assert "active_batches" in totals
    assert "purchases_confirmed_uzs" in totals
    assert "creditor_balance_uzs" in totals


def test_no_org_for_other_user_returns_empty():
    """Юзер без membership — пустой список."""
    other = User.objects.create(email="other@y.local", full_name="O")
    api = APIClient()
    api.force_authenticate(user=other)
    resp = api.get("/api/holding/companies/")
    assert resp.status_code == 200
    assert resp.json()["companies"] == []
    assert resp.json()["totals"]["companies"] == 0


def test_unauthenticated_rejected():
    api = APIClient()
    resp = api.get("/api/holding/companies/")
    assert resp.status_code == 401


def test_invalid_period_rejected(client):
    resp = client.get("/api/holding/companies/?period_from=not-a-date")
    assert resp.status_code == 400
