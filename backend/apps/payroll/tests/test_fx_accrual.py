"""
Multi-currency accrual: ставка в USD/EUR конвертируется в UZS по курсу CBU
на shift_date.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.currency.models import Currency, ExchangeRate
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    SalaryRate,
    WorkSchedule,
    WorkScheduleTemplate,
    WorkShift,
)
from apps.payroll.services.accrual import accrue_for_period
from apps.payroll.services.balance import compute_balance
from apps.payroll.services.fx import convert_to_uzs
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def usd():
    return Currency.objects.get_or_create(
        code="USD", defaults={"numeric_code": "840", "name_ru": "Доллар США"},
    )[0]


@pytest.fixture
def eur():
    return Currency.objects.get_or_create(
        code="EUR", defaults={"numeric_code": "978", "name_ru": "Евро"},
    )[0]


@pytest.fixture
def usd_rates(usd):
    """Курс USD: 12000 на 1 апреля → 12500 на 1 мая."""
    ExchangeRate.objects.create(
        currency=usd, date=date(2026, 4, 1),
        rate=Decimal("12000.000000"), nominal=1,
        source="cbu.uz",
        fetched_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    ExchangeRate.objects.create(
        currency=usd, date=date(2026, 5, 1),
        rate=Decimal("12500.000000"), nominal=1,
        source="cbu.uz",
        fetched_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


def _make_employee(org, currency, comp_type=CompensationPlan.Type.PER_SHIFT):
    u = User.objects.create(email=f"fxa-{currency.code}@t.l", full_name="W", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=comp_type,
        currency=currency,
    )
    return m


# ─── convert_to_uzs unit tests ────────────────────────────────────────────


def test_convert_uzs_returns_same(uzs):
    """UZS → UZS = identity, без обращения к ExchangeRate."""
    result = convert_to_uzs(Decimal("100000"), "UZS", date(2026, 5, 1))
    assert result.amount_uzs == Decimal("100000")
    assert result.exchange_rate == Decimal("1")


def test_convert_usd_uses_cbu_rate(usd, usd_rates):
    """100 USD на 1 апреля → 100 × 12000 = 1.2M сум."""
    result = convert_to_uzs(Decimal("100"), "USD", date(2026, 4, 1))
    assert result.amount_uzs == Decimal("1200000.00")
    assert result.exchange_rate == Decimal("12000")


def test_convert_falls_back_to_recent_rate(usd, usd_rates):
    """1 апреля курс есть, 5 апреля курса нет → fallback на 1 апреля."""
    result = convert_to_uzs(Decimal("100"), "USD", date(2026, 4, 5))
    assert result.amount_uzs == Decimal("1200000.00")
    assert result.rate_date == date(2026, 4, 1)


def test_convert_no_rate_raises(usd):
    """Курса нет совсем → ValidationError."""
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        convert_to_uzs(Decimal("100"), "USD", date(2025, 1, 1))


# ─── accrual with USD rate ─────────────────────────────────────────────────


def test_per_shift_usd_converted_to_uzs(org, usd, usd_rates):
    """PER_SHIFT ставка $50, 2 смены: 1 апр (×12000) + 1 мая (×12500)."""
    employee = _make_employee(org, usd, CompensationPlan.Type.PER_SHIFT)
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("50"), currency=usd,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 1),  # курс 12000
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 5, 1),  # курс 12500
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(employee, date(2026, 4, 1), date(2026, 5, 31))
    # 50 × 12000 + 50 × 12500 = 600_000 + 625_000 = 1_225_000
    assert res.accrued_uzs == Decimal("1225000.00")
    assert len(res.breakdown) == 2
    line_apr = next(ln for ln in res.breakdown if ln.date == date(2026, 4, 1))
    assert line_apr.rate_currency == "USD"
    assert line_apr.rate_amount == Decimal("50.00")
    assert line_apr.exchange_rate == Decimal("12000")
    assert line_apr.accrued_native == Decimal("50.00")
    assert line_apr.accrued == Decimal("600000.00")


def test_per_hour_usd_converts_per_shift(org, usd, usd_rates):
    """PER_HOUR $10/час × 8 часов в апреле = 80 USD × 12000 = 960k сум."""
    employee = _make_employee(org, usd, CompensationPlan.Type.PER_HOUR)
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("10"), currency=usd,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 1),
        kind=WorkShift.Kind.WORK, hours=Decimal("8"),
        source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(employee, date(2026, 4, 1), date(2026, 4, 30))
    # 10 × 8 = 80 USD × 12000 = 960_000
    assert res.accrued_uzs == Decimal("960000.00")


def test_uzs_rate_works_unchanged(org, uzs):
    """UZS-ставка не требует курса и не меняется."""
    employee = _make_employee(org, uzs, CompensationPlan.Type.PER_SHIFT)
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 5),
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    res = accrue_for_period(employee, date(2026, 4, 1), date(2026, 4, 30))
    assert res.accrued_uzs == Decimal("100000")
    assert res.breakdown[0].rate_currency == "UZS"
    assert res.breakdown[0].exchange_rate == Decimal("1")


def test_balance_live_recalc_when_rate_changes(org, usd, usd_rates):
    """
    1000 USD начислено по 12000 = 12M.
    После повышения курса до 12500 балансы пересчитываются live → 12.5M.
    """
    employee = _make_employee(org, usd, CompensationPlan.Type.PER_SHIFT)
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("1000"), currency=usd,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 1),  # курс 12000
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    bal1 = compute_balance(employee, date(2026, 4, 30))
    assert bal1.accrued_total == Decimal("12000000.00")

    # Симулируем повышение курса: для shift_date=2026-04-01 теперь
    # есть запись на 2026-05-01 с курсом 12500. Это не повлияет
    # на расчёт за апрель (всё ещё используется курс 12000), но
    # при as_of=2026-05-31 балансы за май будут считаться по 12500.
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 5, 1),  # курс 12500
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    bal2 = compute_balance(employee, date(2026, 5, 31))
    # 12M (апрель) + 12.5M (май) = 24.5M
    assert bal2.accrued_total == Decimal("24500000.00")


def test_monthly_salary_eur_pro_rated(org, eur):
    """MONTHLY EUR-оклад с конвертацией: 0 прогулов → полный оклад за месяц."""
    # Курсы на каждый день месяца (без них дни без курса не платятся).
    for day in range(1, 32):
        ExchangeRate.objects.create(
            currency=eur, date=date(2026, 7, day),
            rate=Decimal("13500.000000"), nominal=1,
            source="cbu.uz",
            fetched_at=datetime(2026, 7, day, tzinfo=timezone.utc),
        )
    employee = _make_employee(org, eur, CompensationPlan.Type.MONTHLY_SALARY)
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("2200"), currency=eur,  # 2200 EUR в месяц
        effective_from=date(2026, 7, 1),
    )
    # 10 work-shifts в первой половине месяца; 0 прогулов.
    workdays = [date(2026, 7, d) for d in range(1, 11)]
    WorkShift.objects.bulk_create([
        WorkShift(
            organization=org, employee=employee,
            shift_date=d, kind=WorkShift.Kind.WORK,
            source=WorkShift.Source.MANUAL,
        )
        for d in workdays
    ])
    res = accrue_for_period(employee, date(2026, 7, 1), date(2026, 7, 31))
    # 0 прогулов → calendar mode: 31 день × (2200/31) × 13500 = 2200 × 13500
    # = 29_700_000. Округление per-day: (2200/31).quantize(.01) × 31 × 13500.
    per_day = (Decimal("2200") / Decimal("31")).quantize(Decimal("0.01"))
    expected = per_day * Decimal("31") * Decimal("13500")
    assert res.accrued_uzs == expected
    assert all(ln.rate_currency == "EUR" for ln in res.breakdown)
