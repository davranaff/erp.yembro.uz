"""
Расчёт текущего баланса сотрудника по ЗП.

balance_uzs = accrued_total + adjustments_plus − adjustments_minus − paid_total
    accrued_total = Σ accrue_for_period(joined_at..as_of)
    paid_total = Σ PayrollPayout.amount_uzs
                  где payment.status=POSTED и payment.date <= as_of
                  (фильтруем по фактической дате выплаты, а не period_to:
                  аванс за май, выданный 8 мая, не должен исключаться при
                  as_of=10 мая только потому что period_to=31 мая)
    adjustments_plus = Σ PayrollAdjustment(kind ∈ POSITIVE) до as_of
    adjustments_minus = Σ PayrollAdjustment(kind ∈ NEGATIVE) до as_of
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from apps.payments.models import Payment

from ..models import PayrollAdjustment, PayrollPayout
from .accrual import accrue_for_period


@dataclass
class BalanceResult:
    employee_id: str
    as_of: date
    accrued_total: Decimal
    paid_total: Decimal
    adjustments_plus: Decimal
    adjustments_minus: Decimal
    balance_uzs: Decimal


def compute_balance(employee, as_of: date) -> BalanceResult:
    from ..models import SalaryRate
    joined = employee.joined_at.date() if employee.joined_at else as_of
    first_rate_date = (
        SalaryRate.objects.filter(employee=employee)
        .order_by("effective_from")
        .values_list("effective_from", flat=True)
        .first()
    )
    # Start accrual from whichever is earlier: membership creation or first salary rate.
    # Handles the case where a salary is backdated (effective_from < joined_at).
    start = min(joined, first_rate_date) if first_rate_date else joined
    if start > as_of:
        start = as_of
    accrued = accrue_for_period(employee, start, as_of)
    accrued_total = accrued.accrued_uzs

    paid_total = (
        PayrollPayout.objects.filter(
            employee=employee,
            payment__status=Payment.Status.POSTED,
            payment__date__lte=as_of,
        )
        .aggregate(total=Sum("amount_uzs"))
        .get("total")
        or Decimal("0")
    )
    adj_plus = (
        PayrollAdjustment.objects.filter(
            employee=employee,
            kind__in=PayrollAdjustment.POSITIVE_KINDS,
            effective_date__lte=as_of,
        ).aggregate(total=Sum("amount_uzs")).get("total")
        or Decimal("0")
    )
    adj_minus = (
        PayrollAdjustment.objects.filter(
            employee=employee,
            kind__in=PayrollAdjustment.NEGATIVE_KINDS,
            effective_date__lte=as_of,
        ).aggregate(total=Sum("amount_uzs")).get("total")
        or Decimal("0")
    )
    return BalanceResult(
        employee_id=str(employee.id),
        as_of=as_of,
        accrued_total=accrued_total,
        paid_total=paid_total,
        adjustments_plus=adj_plus,
        adjustments_minus=adj_minus,
        balance_uzs=accrued_total + adj_plus - adj_minus - paid_total,
    )
