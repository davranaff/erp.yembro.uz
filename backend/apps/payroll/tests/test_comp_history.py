"""
Тесты CompensationPlanHistory: смешанный период (тип менялся).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.currency.models import Currency
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    CompensationPlanHistory,
    SalaryRate,
    WorkShift,
)
from apps.payroll.services.accrual import accrue_for_period
from apps.payroll.services.compensation import (
    change_compensation_type,
    compensation_type_at,
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
    u = User.objects.create(email="hist@t.l", full_name="W", is_active=True)
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
    return m


def test_change_type_records_history(employee, uzs):
    h1 = change_compensation_type(
        employee=employee, new_type="per_shift",
        effective_from=date(2026, 4, 1),
    )
    h2 = change_compensation_type(
        employee=employee, new_type="monthly_salary",
        effective_from=date(2026, 6, 1),
    )
    h1.refresh_from_db()
    assert h1.effective_to == date(2026, 5, 31)
    assert h2.effective_to is None


def test_compensation_type_at_returns_current(employee):
    change_compensation_type(
        employee=employee, new_type="per_shift",
        effective_from=date(2026, 4, 1),
    )
    change_compensation_type(
        employee=employee, new_type="monthly_salary",
        effective_from=date(2026, 6, 1),
    )
    assert compensation_type_at(employee, date(2026, 5, 15)) == "per_shift"
    assert compensation_type_at(employee, date(2026, 6, 15)) == "monthly_salary"


def test_accrual_with_mixed_type_period(employee, org, uzs):
    """
    Сотрудник до 1 июня — per_shift, после — monthly_salary.
    Смены в апреле (per_shift) и июле (monthly).

    История создаётся явно (тестовый сотрудник создан после backfill).
    """
    change_compensation_type(
        employee=employee, new_type="per_shift",
        effective_from=date(2026, 4, 1),
    )
    change_compensation_type(
        employee=employee, new_type="monthly_salary",
        effective_from=date(2026, 6, 1),
    )

    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 5), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 7, 7), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(employee, date(2026, 4, 1), date(2026, 7, 31))
    # per_shift: 1 × 100_000 = 100_000
    # monthly_salary: 100_000 / 22 ≈ 4_545.45
    assert res.accrued_uzs > Decimal("100000")
    assert res.accrued_uzs < Decimal("110000")
