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
    """0 прогулов → calendar mode: оплачиваются все 31 день месяца."""
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
    # 0 прогулов → calendar mode: per-day = 4_400_000/31 округлено до 0.01,
    # итог = 31 × per_day (с накопленной копеечной погрешностью).
    per_day = (Decimal("4400000") / Decimal("31")).quantize(Decimal("0.01"))
    assert res.accrued_uzs == per_day * Decimal("31")


def test_accrue_monthly_absence_excludes_only_that_day(employee_monthly, uzs, org):
    """Прогул отнимает только этот день; остальные оплачиваются в calendar-mode.

    HR-флоу: ничего автоматически не «срезается» (выходные/праздники продолжают
    оплачиваться). Чтобы вычесть пропущенный день, HR явно ставит kind=absence
    в табеле — этот один день уходит в 0, остальные 30 дней июля платятся
    по rate/31.
    """
    from apps.payroll.models import WorkShift

    set_rate(
        employee=employee_monthly,
        amount=Decimal("4400000"),
        effective_from=date(2026, 7, 1),
        currency=uzs,
    )
    WorkShift.objects.create(
        organization=org, employee=employee_monthly,
        shift_date=date(2026, 7, 15), kind=WorkShift.Kind.ABSENCE,
        source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(
        employee_monthly, date(2026, 7, 1), date(2026, 7, 31)
    )
    # 30 дней × (4_400_000 / 31) с copyek-округлением.
    per_day = (Decimal("4400000") / Decimal("31")).quantize(Decimal("0.01"))
    assert res.accrued_uzs == per_day * Decimal("30")


def test_accrue_monthly_hours_pro_rata(employee_monthly, uzs, org):
    """Если у смены задано hours отличное от стандарта (8) — pro-rata."""
    from apps.payroll.models import WorkShift

    set_rate(
        employee=employee_monthly,
        amount=Decimal("4400000"),
        effective_from=date(2026, 7, 1),
        currency=uzs,
    )
    # 0 прогулов, calendar mode. Один день из 31 — половинка (4ч/8ч).
    workdays = [date(2026, 7, d) for d in range(1, 31)]
    _make_shifts(employee_monthly, workdays)
    # 31 июля — half-day (4 часа)
    WorkShift.objects.create(
        organization=org, employee=employee_monthly,
        shift_date=date(2026, 7, 31), kind=WorkShift.Kind.WORK,
        hours=Decimal("4"),
        source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(
        employee_monthly, date(2026, 7, 1), date(2026, 7, 31)
    )
    # 30 полных + 1 × 0.5 = 30.5 дней; (4_400_000 / 31) × 30.5
    # = 141_935.48 × 30.5 = 4_329_032.14 (точное округление)
    expected = (Decimal("4400000") / Decimal("31")).quantize(Decimal("0.01")) * Decimal("30")
    expected += (Decimal("4400000") / Decimal("31") * Decimal("0.5")).quantize(Decimal("0.01"))
    assert res.accrued_uzs == expected


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
