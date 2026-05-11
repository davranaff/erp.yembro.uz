from datetime import date
from decimal import Decimal

import pytest

from apps.payments.models import Payment
from apps.payroll.models import PayrollPayout
from apps.payroll.services.balance import compute_balance
from apps.payroll.services.payout import create_payout
from apps.payroll.services.rates import set_rate

pytestmark = pytest.mark.django_db


def test_create_payout_creates_payment_and_link(
    employee_monthly, uzs, cash_subaccount, hr_user,
):
    payout = create_payout(
        employee=employee_monthly,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("1000000"),
        period_from=date(2026, 5, 1),
        period_to=date(2026, 5, 31),
        cash_subaccount=cash_subaccount,
        on_date=date(2026, 5, 31),
        user=hr_user,
    )
    assert payout.payment_id is not None
    payout.payment.refresh_from_db()
    assert payout.payment.kind == Payment.Kind.SALARY
    assert payout.payment.direction == Payment.Direction.OUT
    assert payout.payment.status == Payment.Status.POSTED
    assert payout.amount_uzs == Decimal("1000000")


def test_balance_after_payout(
    employee_per_shift, uzs, cash_subaccount, hr_user,
):
    from datetime import datetime, timezone
    from apps.payroll.models import WorkShift
    from apps.organizations.models import OrganizationMembership

    # Сдвигаем joined_at в прошлое (auto_now_add не даёт задать в create)
    OrganizationMembership.objects.filter(pk=employee_per_shift.pk).update(
        joined_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    employee_per_shift.refresh_from_db()

    set_rate(
        employee=employee_per_shift,
        amount=Decimal("200000"),
        effective_from=date(2026, 5, 1),
        currency=uzs,
    )
    WorkShift.objects.create(
        organization=employee_per_shift.organization,
        employee=employee_per_shift,
        shift_date=date(2026, 5, 4),
        kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    bal_before = compute_balance(employee_per_shift, date(2026, 5, 31))
    assert bal_before.accrued_total == Decimal("200000")
    assert bal_before.paid_total == Decimal("0")
    assert bal_before.balance_uzs == Decimal("200000")

    create_payout(
        employee=employee_per_shift,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("200000"),
        period_from=date(2026, 5, 1),
        period_to=date(2026, 5, 31),
        cash_subaccount=cash_subaccount,
        on_date=date(2026, 5, 31),
        user=hr_user,
    )
    bal_after = compute_balance(employee_per_shift, date(2026, 5, 31))
    assert bal_after.paid_total == Decimal("200000")
    assert bal_after.balance_uzs == Decimal("0")


def test_create_payout_zero_amount_rejected(
    employee_monthly, cash_subaccount,
):
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        create_payout(
            employee=employee_monthly,
            type=PayrollPayout.Type.SALARY,
            amount_uzs=Decimal("0"),
            period_from=date(2026, 5, 1),
            period_to=date(2026, 5, 31),
            cash_subaccount=cash_subaccount,
        )
