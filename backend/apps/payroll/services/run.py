"""
PayrollRun: предпросмотр и выполнение массовой ведомости на выплату.

Сценарий:
    1. preview_run(period_from, period_to) — для каждого активного сотрудника
       считаем balance на period_to, формируем строку (employee, due_uzs).
    2. execute_run(...) — атомарно создаёт PayrollRun(status=executed) и
       N PayrollPayout через create_payout. Сумма каждой выплаты ≤ balance.
       Сотрудники с balance ≤ 0 пропускаются (нечего платить).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.organizations.models import OrganizationMembership

from ..models import PayrollPayout, PayrollRun
from .balance import compute_balance
from .payout import create_payout


@dataclass
class PreviewLine:
    employee_id: str
    full_name: str
    balance_uzs: Decimal
    due_uzs: Decimal


def preview_run(*, organization, period_from: date, period_to: date) -> List[PreviewLine]:
    """Возвращает список сотрудников с положительным балансом на period_to."""
    if period_to < period_from:
        return []
    qs = OrganizationMembership.objects.filter(
        organization=organization, is_active=True,
    ).select_related("user")
    out: List[PreviewLine] = []
    for m in qs:
        bal = compute_balance(m, period_to)
        if bal.balance_uzs <= 0:
            continue
        out.append(PreviewLine(
            employee_id=str(m.id),
            full_name=m.user.full_name if m.user_id else "",
            balance_uzs=bal.balance_uzs,
            due_uzs=bal.balance_uzs,
        ))
    out.sort(key=lambda x: x.due_uzs, reverse=True)
    return out


@transaction.atomic
def execute_run(
    *,
    organization,
    period_from: date,
    period_to: date,
    cash_subaccount,
    payout_type: str = PayrollPayout.Type.SALARY,
    employee_amounts: dict[str, Decimal] | None = None,
    notes: str = "",
    user=None,
) -> PayrollRun:
    """
    Атомарно создаёт ведомость и N выплат.

    employee_amounts: {employee_id_str: amount_to_pay}. Если None — берётся
    весь positive balance каждого сотрудника. Если задан — используется
    указанная сумма (может быть < balance, но > 0).

    Возвращает PayrollRun с заполненными totals.
    """
    if period_to < period_from:
        raise ValidationError({"period_to": "period_to раньше period_from."})

    preview = preview_run(
        organization=organization,
        period_from=period_from, period_to=period_to,
    )
    # Применяем custom amounts если заданы
    selected: list[tuple[OrganizationMembership, Decimal]] = []
    employee_id_to_membership = {
        str(m.id): m for m in OrganizationMembership.objects.filter(
            organization=organization,
            id__in=[p.employee_id for p in preview],
        ).select_related("user")
    }
    for line in preview:
        m = employee_id_to_membership.get(line.employee_id)
        if m is None:
            continue
        if employee_amounts is not None:
            if line.employee_id not in employee_amounts:
                continue  # юзер не выбрал этого
            amt = Decimal(str(employee_amounts[line.employee_id]))
        else:
            amt = line.due_uzs
        if amt <= 0:
            continue
        if amt > line.balance_uzs:
            raise ValidationError({
                line.employee_id: f"Сумма {amt} больше баланса {line.balance_uzs}.",
            })
        selected.append((m, amt))

    if not selected:
        raise ValidationError({"detail": "Нет сотрудников для выплаты."})

    run = PayrollRun.objects.create(
        organization=organization,
        period_from=period_from,
        period_to=period_to,
        payout_type=payout_type,
        cash_subaccount=cash_subaccount,
        status=PayrollRun.Status.DRAFT,
        notes=notes,
        created_by=user,
    )

    total = Decimal("0")
    for m, amt in selected:
        payout = create_payout(
            employee=m,
            type=payout_type,
            amount_uzs=amt,
            period_from=period_from,
            period_to=period_to,
            cash_subaccount=cash_subaccount,
            channel="cash",
            notes=f"Ведомость {run.id}",
            user=user,
        )
        payout.run = run
        payout.save(update_fields=["run", "updated_at"])
        total += amt

    run.status = PayrollRun.Status.EXECUTED
    run.employees_count = len(selected)
    run.total_amount_uzs = total
    run.executed_at = timezone.now()
    run.save(update_fields=[
        "status", "employees_count", "total_amount_uzs", "executed_at", "updated_at",
    ])
    audit_log(
        organization=organization,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=run,
        action_verb=f"payroll run {run.period_from}..{run.period_to} = {total}"[:64],
    )
    return run
