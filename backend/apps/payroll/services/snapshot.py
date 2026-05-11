"""
PayrollAccrualSnapshot — кэш балансов для скейла.

API:
    refresh_balance_snapshots(organization=None) — пересчитывает все snapshots.
    get_balance_via_snapshot(employee, as_of, max_age_hours=24) — возвращает
        snapshot если свежий, иначе fallback к compute_balance.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.utils import timezone

from apps.organizations.models import OrganizationMembership

from ..models import PayrollAccrualSnapshot
from .balance import BalanceResult, compute_balance


def refresh_balance_snapshots(organization=None) -> int:
    """
    Пересчитывает snapshots для всех активных сотрудников.
    Возвращает кол-во обновлённых записей.
    """
    qs = OrganizationMembership.objects.filter(is_active=True)
    if organization is not None:
        qs = qs.filter(organization=organization)

    today = date.today()
    now = timezone.now()
    n = 0
    for m in qs.iterator():
        bal = compute_balance(m, today)
        PayrollAccrualSnapshot.objects.update_or_create(
            employee=m,
            defaults={
                "organization": m.organization,
                "as_of": today,
                "accrued_total": bal.accrued_total,
                "paid_total": bal.paid_total,
                "adjustments_plus": bal.adjustments_plus,
                "adjustments_minus": bal.adjustments_minus,
                "balance_uzs": bal.balance_uzs,
                "computed_at": now,
            },
        )
        n += 1
    return n


def get_balance_via_snapshot(
    employee, as_of: date, *, max_age_hours: int = 24,
) -> BalanceResult:
    """
    Если есть свежий snapshot (computed_at < max_age_hours назад)
    и as_of совпадает — возвращаем из snapshot. Иначе — live-расчёт.
    """
    snap: Optional[PayrollAccrualSnapshot] = (
        PayrollAccrualSnapshot.objects.filter(employee=employee).first()
    )
    if snap and snap.as_of == as_of:
        age = timezone.now() - snap.computed_at
        if age <= timedelta(hours=max_age_hours):
            return BalanceResult(
                employee_id=str(employee.id),
                as_of=snap.as_of,
                accrued_total=snap.accrued_total,
                paid_total=snap.paid_total,
                adjustments_plus=snap.adjustments_plus,
                adjustments_minus=snap.adjustments_minus,
                balance_uzs=snap.balance_uzs,
            )
    return compute_balance(employee, as_of)
