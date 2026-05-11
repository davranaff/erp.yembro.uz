"""
Управление CompensationPlan + history. Атомарная смена типа оплаты.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from django.db import transaction
from django.db.models import Q

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import CompensationPlan, CompensationPlanHistory


def compensation_type_at(employee, on_date: date) -> Optional[str]:
    """Возвращает compensation_type сотрудника на дату. Fallback к текущему плану."""
    record = (
        CompensationPlanHistory.objects.filter(
            employee=employee, effective_from__lte=on_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .order_by("-effective_from").first()
    )
    if record:
        return record.compensation_type
    plan = getattr(employee, "compensation_plan", None)
    return plan.compensation_type if plan else None


@transaction.atomic
def change_compensation_type(
    *,
    employee,
    new_type: str,
    effective_from: date,
    user=None,
    reason: str = "",
) -> CompensationPlanHistory:
    """
    Меняет тип компенсации сотрудника. Закрывает текущий open-интервал
    в History, создаёт новый, обновляет CompensationPlan.compensation_type.
    """
    CompensationPlanHistory.objects.filter(
        employee=employee, effective_to__isnull=True,
    ).update(effective_to=effective_from - timedelta(days=1))

    history = CompensationPlanHistory.objects.create(
        organization=employee.organization,
        employee=employee,
        compensation_type=new_type,
        effective_from=effective_from,
        reason=reason,
        created_by=user,
    )

    plan = getattr(employee, "compensation_plan", None)
    if plan and plan.compensation_type != new_type:
        plan.compensation_type = new_type
        plan.save(update_fields=["compensation_type", "updated_at"])

    audit_log(
        organization=employee.organization,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=history,
        action_verb=f"compensation_type → {new_type} from {effective_from}"[:64],
    )
    return history
