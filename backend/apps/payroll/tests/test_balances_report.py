"""
Тест endpoint'а /api/payroll/balances/ — bulk-сводка балансов.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.currency.models import Currency
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollAdjustment,
    SalaryRate,
    WorkShift,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="bal-admin@test.local", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="HR",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def _make_employee(org, uzs, email, *, with_balance: bool = False):
    u = User.objects.create(email=email, full_name=email.split("@")[0], is_active=True)
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
    if with_balance:
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


def test_balances_returns_all_active(hr_admin, org, uzs):
    e1 = _make_employee(org, uzs, "alice@t.l", with_balance=True)
    e2 = _make_employee(org, uzs, "bob@t.l", with_balance=False)
    api = _client(hr_admin)
    r = api.get("/api/payroll/balances/?as_of=2026-04-30")
    assert r.status_code == 200
    body = r.json()
    ids = {row["employee_id"] for row in body["rows"]}
    assert str(e1.id) in ids and str(e2.id) in ids
    # Сортировка: alice (баланс 100k) выше bob (0)
    alice_idx = next(i for i, r in enumerate(body["rows"]) if r["employee_id"] == str(e1.id))
    bob_idx = next(i for i, r in enumerate(body["rows"]) if r["employee_id"] == str(e2.id))
    assert alice_idx < bob_idx


def test_balances_totals(hr_admin, org, uzs):
    _make_employee(org, uzs, "x@t.l", with_balance=True)
    _make_employee(org, uzs, "y@t.l", with_balance=True)
    api = _client(hr_admin)
    r = api.get("/api/payroll/balances/?as_of=2026-04-30")
    assert r.status_code == 200
    body = r.json()
    # 2 сотрудника по 100k начислено
    assert body["totals"]["total_accrued_uzs"] >= 200000


def test_balances_excludes_inactive_by_default(hr_admin, org, uzs):
    e1 = _make_employee(org, uzs, "active@t.l")
    e2 = _make_employee(org, uzs, "inactive@t.l")
    e2.is_active = False
    e2.save()
    api = _client(hr_admin)
    r = api.get("/api/payroll/balances/")
    ids = {row["employee_id"] for row in r.json()["rows"]}
    assert str(e1.id) in ids
    assert str(e2.id) not in ids
    # С флагом include_inactive
    r2 = api.get("/api/payroll/balances/?include_inactive=1")
    ids2 = {row["employee_id"] for row in r2.json()["rows"]}
    assert str(e2.id) in ids2


def test_balances_requires_hr(org, uzs):
    """Без hr:r → 403."""
    u = User.objects.create(email="no-hr@t.l", full_name="N", is_active=True)
    OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="N",
    )
    api = _client(u)
    r = api.get("/api/payroll/balances/")
    assert r.status_code == 403
