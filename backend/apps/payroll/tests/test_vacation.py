"""
Тесты оплаты отпуска/больничного по среднему дневному.
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
from apps.payroll.services.accrual import accrue_for_period, average_daily_earnings
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
    u = User.objects.create(email="vac@t.l", full_name="W", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=CompensationPlan.Type.PER_SHIFT,
        currency=uzs,
    )
    CompensationPlanHistory.objects.create(
        organization=org, employee=m,
        compensation_type="per_shift",
        effective_from=date(2025, 1, 1),
    )
    SalaryRate.objects.create(
        organization=org, employee=m,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2025, 1, 1),
    )
    return m


def test_average_daily_earnings_per_shift(employee, org):
    """20 смен × 100k за последний год → avg = 100k."""
    from datetime import timedelta as _td
    base = date(2026, 5, 1)
    for i in range(20):
        WorkShift.objects.create(
            organization=org, employee=employee,
            shift_date=base - _td(days=i + 1),
            kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
        )
    avg = average_daily_earnings(employee, ref_date=base)
    assert avg == Decimal("100000.00")


def test_vacation_paid_at_average(employee, org):
    """В период отпуска accrued берётся из среднего."""
    from datetime import timedelta as _td
    # 20 смен в апреле 2026 (за год до)
    base = date(2026, 5, 1)
    for i in range(20):
        WorkShift.objects.create(
            organization=org, employee=employee,
            shift_date=base - _td(days=i + 30),
            kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
        )
    # Отпуск 5 дней в мае
    vac_dates = [base + _td(days=i) for i in range(5)]
    for d in vac_dates:
        WorkShift.objects.create(
            organization=org, employee=employee,
            shift_date=d, kind=WorkShift.Kind.VACATION,
            source=WorkShift.Source.MANUAL,
        )
    res = accrue_for_period(employee, date(2026, 5, 1), date(2026, 5, 5))
    # 5 дней × 100k средний = 500k
    assert res.accrued_uzs == Decimal("500000.00")
    assert all(line.note.startswith("avg") for line in res.breakdown)


def test_vacation_zero_when_no_history(employee, org):
    """Без истории смен avg=0 → отпуск не оплачивается."""
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 5, 1), kind=WorkShift.Kind.VACATION,
        source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(employee, date(2026, 5, 1), date(2026, 5, 1))
    assert res.accrued_uzs == Decimal("0")
