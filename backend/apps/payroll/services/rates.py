"""
Управление историей ставок (SalaryRate).

Open-ended интервалы: последняя запись для сотрудника имеет effective_to=NULL.
При установке новой ставки закрываем прошлую (effective_to = new.from − 1 day).
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Q

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import SalaryRate


def rate_at(employee, on_date: date) -> Optional[SalaryRate]:
    """Возвращает действующую ставку сотрудника на дату (или None)."""
    return (
        SalaryRate.objects.filter(employee=employee, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("-effective_from")
        .first()
    )


@transaction.atomic
def set_rate(
    *,
    employee,
    amount: Decimal,
    effective_from: date,
    currency,
    user=None,
    reason: str = "",
) -> SalaryRate:
    """
    Установить новую ставку с заданной даты.

    Поведение:
    - Если в БД нет ставок — просто создаём первую с open-end.
    - Если effective_from позже всех существующих — закрываем все open-end
      записи датой `effective_from − 1 day`, новая ставка становится
      открытой (текущей).
    - Если effective_from внутри/раньше существующих — вставляем «между»:
      закрываем все ставки с effective_from в диапазоне
      [effective_from, ∞) у которых effective_from совпадает с новой
      (исключаем дубль), и подрезаем интервалы. Существующие ставки на
      будущие даты не трогаем (их effective_from > new.from).

    Запрет: точный дубль (две ставки с одинаковым effective_from).
    """
    from django.core.exceptions import ValidationError

    # Запрет точного дубля
    if SalaryRate.objects.filter(
        employee=employee, effective_from=effective_from,
    ).exists():
        raise ValidationError({
            "effective_from": (
                f"Ставка с датой {effective_from} уже существует. "
                "Удалите её или выберите другую дату."
            ),
        })

    # Найти ставку, которая «активна» прямо перед новой датой
    # (effective_from < new.from) — её надо закрыть на (new.from − 1).
    prev_open = (
        SalaryRate.objects.filter(
            employee=employee,
            effective_from__lt=effective_from,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from))
        .order_by("-effective_from")
        .first()
    )
    if prev_open is not None:
        prev_open.effective_to = effective_from - timedelta(days=1)
        prev_open.save(update_fields=["effective_to", "updated_at"])

    # Найти следующую ставку (с effective_from > new.from) —
    # её используем чтобы определить effective_to новой ставки.
    next_rate = (
        SalaryRate.objects.filter(
            employee=employee,
            effective_from__gt=effective_from,
        )
        .order_by("effective_from")
        .first()
    )
    new_effective_to = (
        next_rate.effective_from - timedelta(days=1) if next_rate else None
    )

    rate = SalaryRate.objects.create(
        organization=employee.organization,
        employee=employee,
        amount=amount,
        currency=currency,
        effective_from=effective_from,
        effective_to=new_effective_to,
        reason=reason,
        created_by=user,
    )
    audit_log(
        organization=employee.organization,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=rate,
        action_verb=f"set rate {amount} {currency.code} from {effective_from}"[:64],
    )
    return rate
