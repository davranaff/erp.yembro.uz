from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.payroll.services.rates import rate_at, set_rate

pytestmark = pytest.mark.django_db


def test_set_rate_creates_first(employee_monthly, uzs, hr_user):
    rate = set_rate(
        employee=employee_monthly,
        amount=Decimal("5000000"),
        effective_from=date(2026, 1, 1),
        currency=uzs,
        user=hr_user,
        reason="hire",
    )
    assert rate.amount == Decimal("5000000")
    assert rate.effective_to is None


def test_set_rate_closes_previous(employee_monthly, uzs, hr_user):
    set_rate(
        employee=employee_monthly,
        amount=Decimal("5000000"),
        effective_from=date(2026, 1, 1),
        currency=uzs,
    )
    new_rate = set_rate(
        employee=employee_monthly,
        amount=Decimal("6000000"),
        effective_from=date(2026, 4, 1),
        currency=uzs,
    )
    # старая закрыта 31 марта
    old = (
        rate_at(employee_monthly, date(2026, 3, 31))
    )
    assert old is not None
    assert old.amount == Decimal("5000000")
    assert old.effective_to == date(2026, 3, 31)
    # новая активна с 1 апреля
    cur = rate_at(employee_monthly, date(2026, 4, 1))
    assert cur.amount == new_rate.amount


def test_rate_at_no_match(employee_monthly):
    assert rate_at(employee_monthly, date(2026, 1, 1)) is None


def test_rate_at_outside_interval(employee_monthly, uzs):
    set_rate(
        employee=employee_monthly,
        amount=Decimal("5000000"),
        effective_from=date(2026, 4, 1),
        currency=uzs,
    )
    assert rate_at(employee_monthly, date(2026, 3, 31)) is None
    assert rate_at(employee_monthly, date(2026, 5, 1)).amount == Decimal("5000000")
