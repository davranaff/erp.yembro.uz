"""
Тесты PayrollAdjustment: учёт в balance, API CRUD.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollAdjustment,
    SalaryRate,
    WorkShift,
)
from apps.payroll.services.balance import compute_balance
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.currency.models import Currency


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="adj-emp@test.local", full_name="Emp", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="Worker",
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


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="adj-admin@test.local", full_name="A", is_active=True)
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


# ─── Service-level: balance with adjustments ─────────────────────────────


def test_bonus_increases_balance(employee, org):
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.BONUS,
        effective_date=date(2026, 4, 10),
        amount_uzs=Decimal("50000"),
        reason="Q1 bonus",
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    # accrued: 1 смена × 100k = 100k
    # bonus: +50k → balance = 150k
    assert bal.accrued_total == Decimal("100000")
    assert bal.adjustments_plus == Decimal("50000")
    assert bal.adjustments_minus == Decimal("0")
    assert bal.balance_uzs == Decimal("150000")


def test_deduction_decreases_balance(employee, org):
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.DEDUCTION,
        effective_date=date(2026, 4, 10),
        amount_uzs=Decimal("30000"),
        reason="Прогул",
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    # 100k − 30k = 70k
    assert bal.adjustments_minus == Decimal("30000")
    assert bal.balance_uzs == Decimal("70000")


def test_correction_plus_and_minus(employee, org):
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.CORRECTION_PLUS,
        effective_date=date(2026, 4, 5),
        amount_uzs=Decimal("20000"),
    )
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.CORRECTION_MINUS,
        effective_date=date(2026, 4, 6),
        amount_uzs=Decimal("10000"),
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    assert bal.balance_uzs == Decimal("110000")  # 100 + 20 − 10


def test_adjustment_outside_period_excluded(employee, org):
    """effective_date после as_of не учитывается."""
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.BONUS,
        effective_date=date(2026, 5, 15),
        amount_uzs=Decimal("100000"),
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    assert bal.adjustments_plus == Decimal("0")
    assert bal.balance_uzs == Decimal("100000")


# ─── API ─────────────────────────────────────────────────────────────────


def test_create_adjustment_via_api(hr_admin, employee):
    api = _client(hr_admin)
    r = api.post("/api/payroll/adjustments/", {
        "employee": str(employee.id),
        "kind": "bonus",
        "effective_date": "2026-04-15",
        "amount_uzs": "50000",
        "reason": "Премия",
    }, format="json")
    assert r.status_code == 201, r.content
    assert PayrollAdjustment.objects.filter(employee=employee).count() == 1


def test_list_filter_by_employee_kind(hr_admin, employee, org):
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.BONUS,
        effective_date=date(2026, 4, 10), amount_uzs=Decimal("10000"),
    )
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.DEDUCTION,
        effective_date=date(2026, 4, 11), amount_uzs=Decimal("5000"),
    )
    api = _client(hr_admin)
    r = api.get(f"/api/payroll/adjustments/?employee={employee.id}&kind=bonus")
    assert r.status_code == 200
    assert r.json()["count"] == 1


def test_balance_endpoint_shows_adjustments(hr_admin, employee, org):
    PayrollAdjustment.objects.create(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.BONUS,
        effective_date=date(2026, 4, 10), amount_uzs=Decimal("25000"),
    )
    api = _client(hr_admin)
    r = api.get(f"/api/payroll/employees/{employee.id}/balance/?as_of=2026-04-30")
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["adjustments_plus"]) == Decimal("25000")
    assert Decimal(body["balance_uzs"]) == Decimal("125000")
