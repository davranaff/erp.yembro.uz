"""
Тесты автоматического применения налогов с ФОТ.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount
from apps.currency.models import Currency
from apps.modules.models import Module, OrganizationModule
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollAdjustment,
    PayrollPayout,
    SalaryRate,
    WorkShift,
)
from apps.payroll.services.balance import compute_balance
from apps.payroll.services.payout import create_payout
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def cash(org):
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="tax-emp@t.l", full_name="W", is_active=True)
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
        amount=Decimal("1000000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=m,
        shift_date=date(2026, 4, 5), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    return m


def _set_taxes(org, ndfl=12, inps="0.1", esp=25, auto=True):
    om = OrganizationModule.objects.get(organization=org, module__code="hr")
    om.settings_json = {
        "ndfl_pct": str(ndfl),
        "inps_pct": str(inps),
        "esp_pct": str(esp),
        "auto_apply_on_payout": auto,
    }
    om.save()


def test_no_taxes_when_settings_disabled(employee, org, cash):
    """auto_apply_on_payout=False → налоги не создаются."""
    _set_taxes(org, auto=False)
    create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("1000000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
    )
    assert PayrollAdjustment.objects.filter(employee=employee).count() == 0


def test_taxes_applied_when_auto(employee, org, cash):
    _set_taxes(org, ndfl=12, inps="0.1", auto=True)
    create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("1000000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
    )
    adjustments = list(PayrollAdjustment.objects.filter(employee=employee))
    assert len(adjustments) == 2  # НДФЛ + ИНПС
    ndfl = next(a for a in adjustments if a.reason.startswith("НДФЛ"))
    inps = next(a for a in adjustments if a.reason.startswith("ИНПС"))
    assert ndfl.amount_uzs == Decimal("120000.00")  # 12% от 1М
    assert inps.amount_uzs == Decimal("1000.00")    # 0.1% от 1М


def test_taxes_idempotent(employee, org, cash):
    """Повторный вызов не создаёт дубли."""
    _set_taxes(org, ndfl=12, inps="0.1", auto=True)
    p1 = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("1000000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
    )
    from apps.payroll.services.taxes import apply_taxes_for_payout
    apply_taxes_for_payout(p1)  # повторный
    assert PayrollAdjustment.objects.filter(employee=employee).count() == 2


def test_balance_after_taxes(employee, org, cash):
    """Баланс уменьшен на сумму удержаний."""
    _set_taxes(org, ndfl=12, inps="0.1", auto=True)
    # Сначала пополним accrued больше чем выплачиваем
    SalaryRate.objects.filter(employee=employee).update(amount=Decimal("2000000"))
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 6), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    # accrued = 2 × 2M = 4M (т.к. ставка изменилась — обе смены по новой)
    # А вообще rate_at(апрель 5) — rate с effective_from=2026-04-01, amount стал 2M.
    # Выплата 1M → паид 1M.
    create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("1000000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
        on_date=date(2026, 4, 30),
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    # adjustments_minus = 120k + 1k = 121k (НДФЛ + ИНПС)
    assert bal.adjustments_minus == Decimal("121000")
