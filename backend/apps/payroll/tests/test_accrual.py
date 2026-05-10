from datetime import date
from decimal import Decimal

import pytest

from apps.payroll.models import WorkScheduleTemplate, WorkShift, WorkSchedule
from apps.payroll.services.accrual import accrue_for_period
from apps.payroll.services.rates import set_rate

pytestmark = pytest.mark.django_db


def _make_shifts(employee, dates, kind=WorkShift.Kind.WORK, hours=None):
    objs = [
        WorkShift(
            organization=employee.organization,
            employee=employee,
            shift_date=d,
            kind=kind,
            source=WorkShift.Source.MANUAL,
            hours=hours,
        )
        for d in dates
    ]
    WorkShift.objects.bulk_create(objs)


def test_accrue_per_shift_simple(employee_per_shift, uzs):
    set_rate(
        employee=employee_per_shift,
        amount=Decimal("100000"),
        effective_from=date(2026, 5, 1),
        currency=uzs,
    )
    _make_shifts(
        employee_per_shift,
        [date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 8)],
    )
    res = accrue_for_period(
        employee_per_shift, date(2026, 5, 1), date(2026, 5, 31)
    )
    assert res.accrued_uzs == Decimal("300000")
    assert len(res.breakdown) == 3


def test_accrue_per_shift_rate_change(employee_per_shift, uzs):
    set_rate(
        employee=employee_per_shift,
        amount=Decimal("100000"),
        effective_from=date(2026, 5, 1),
        currency=uzs,
    )
    set_rate(
        employee=employee_per_shift,
        amount=Decimal("150000"),
        effective_from=date(2026, 5, 15),
        currency=uzs,
    )
    _make_shifts(
        employee_per_shift,
        [date(2026, 5, 4), date(2026, 5, 14), date(2026, 5, 15), date(2026, 5, 20)],
    )
    res = accrue_for_period(
        employee_per_shift, date(2026, 5, 1), date(2026, 5, 31)
    )
    # 2 смены × 100k + 2 × 150k
    assert res.accrued_uzs == Decimal("500000")


def test_accrue_monthly_pro_rated(employee_monthly, uzs, org):
    # Берём июль 2026 — нет UZ-праздников, fallback 22 рабочих дня.
    # Ставка 4_400_000/мес → 200_000 за день. Отрабатываем 10 дней.
    set_rate(
        employee=employee_monthly,
        amount=Decimal("4400000"),
        effective_from=date(2026, 7, 1),
        currency=uzs,
    )
    workdays = [date(2026, 7, d) for d in range(1, 11)]
    _make_shifts(employee_monthly, workdays)
    res = accrue_for_period(
        employee_monthly, date(2026, 7, 1), date(2026, 7, 31)
    )
    # 10 * (4_400_000 / 22) = 2_000_000
    assert res.accrued_uzs == Decimal("2000000.00")


def test_accrue_per_shift_skips_non_work_days(employee_per_shift, uzs):
    set_rate(
        employee=employee_per_shift,
        amount=Decimal("100000"),
        effective_from=date(2026, 5, 1),
        currency=uzs,
    )
    _make_shifts(employee_per_shift, [date(2026, 5, 4)], kind=WorkShift.Kind.VACATION)
    _make_shifts(employee_per_shift, [date(2026, 5, 5)], kind=WorkShift.Kind.WORK)
    res = accrue_for_period(employee_per_shift, date(2026, 5, 1), date(2026, 5, 31))
    assert res.accrued_uzs == Decimal("100000")
