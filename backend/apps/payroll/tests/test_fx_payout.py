"""
Тесты валютных выплат.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount
from apps.currency.models import Currency
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import CompensationPlan, PayrollPayout, SalaryRate
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
def usd():
    return Currency.objects.get_or_create(
        code="USD", defaults={"numeric_code": "840", "name_ru": "Доллар"},
    )[0]


@pytest.fixture
def cash(org):
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="fx-emp@t.l", full_name="W", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=CompensationPlan.Type.MONTHLY_SALARY,
        currency=uzs,
    )
    return m


def test_fx_payout_creates_payment_with_fx_fields(employee, usd, cash):
    payout = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("12000000"),  # 12M сум
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
        currency=usd,
        exchange_rate=Decimal("12000.000000"),
        amount_foreign=Decimal("1000.00"),
    )
    payout.payment.refresh_from_db()
    assert payout.payment.currency_id == usd.id
    assert payout.payment.amount_foreign == Decimal("1000.00")
    assert payout.payment.exchange_rate == Decimal("12000.000000")


def test_fx_payout_partial_fields_rejected(employee, usd, cash):
    """Если задана только часть FX-полей — ValidationError."""
    from django.core.exceptions import ValidationError as DjErr

    with pytest.raises(DjErr):
        create_payout(
            employee=employee,
            type=PayrollPayout.Type.SALARY,
            amount_uzs=Decimal("12000000"),
            period_from=date(2026, 4, 1),
            period_to=date(2026, 4, 30),
            cash_subaccount=cash,
            currency=usd,
            # exchange_rate и amount_foreign не заданы
        )


def test_payout_without_fx_works(employee, cash):
    """UZS-выплата без FX-полей — payment.currency=None."""
    payout = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("100000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash,
    )
    payout.payment.refresh_from_db()
    assert payout.payment.currency_id is None
    assert payout.payment.amount_foreign is None
