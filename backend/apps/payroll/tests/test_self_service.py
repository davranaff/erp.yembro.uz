"""
Тест self-service эндпоинта /api/payroll/me/.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.currency.models import Currency
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollPayout,
    SalaryRate,
    WorkShift,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="me-emp@t.l", full_name="Me", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=CompensationPlan.Type.PER_SHIFT,
        currency=uzs,
    )
    SalaryRate.objects.create(
        organization=org, employee=m,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=m,
        shift_date=date(2026, 4, 5), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    return m


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_me_endpoint_returns_self_data(employee):
    """Сотрудник без hr-прав видит свои данные."""
    api = _client(employee.user)
    r = api.get("/api/payroll/me/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert "balance" in body
    assert "rates" in body
    assert "payouts" in body
    assert "adjustments" in body
    # Ставка 100k
    assert len(body["rates"]) == 1
    assert body["rates"][0]["amount"] == "100000.00"
    # Один shift → accrued = 100k
    assert Decimal(body["balance"]["accrued_total"]) == Decimal("100000")


def test_me_does_not_require_hr_rights(employee):
    """Без hr:r всё равно работает (это self-service)."""
    api = _client(employee.user)
    r = api.get("/api/payroll/me/")
    assert r.status_code == 200
