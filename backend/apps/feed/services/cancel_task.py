"""
Сервис `cancel_production_task` — отменить производственное задание
(до его исполнения).

Atomic:
    1. Guards: task.status in {PLANNED, PAUSED}. После RUNNING/DONE —
       нельзя (на это есть reverse компенсаций, но сейчас out of scope).
    2. task.status = CANCELLED + reason.
    3. AuditLog.

Ничего не создаёт и не двигает — задача ещё не стартовала.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import ProductionTask


class FeedTaskCancelError(ValidationError):
    pass


@dataclass
class FeedTaskCancelResult:
    task: ProductionTask


@transaction.atomic
def cancel_production_task(
    task: ProductionTask,
    *,
    reason: str = "",
    user=None,
) -> FeedTaskCancelResult:
    task = ProductionTask.objects.select_for_update().get(pk=task.pk)

    if task.status not in (
        ProductionTask.Status.PLANNED,
        ProductionTask.Status.PAUSED,
    ):
        raise FeedTaskCancelError(
            {"status": (
                f"Отмена возможна только из PLANNED/PAUSED, "
                f"текущий: {task.get_status_display()}."
            )}
        )

    task.status = ProductionTask.Status.CANCELLED
    if reason:
        task.notes = (
            (task.notes + f"\nОтмена: {reason}").strip()
            if getattr(task, "notes", "")
            else f"Отмена: {reason}"
        )
    fields = ["status", "updated_at"]
    if hasattr(task, "notes"):
        fields.append("notes")
    task.save(update_fields=fields)

    audit_log(
        organization=task.organization,
        module=task.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=task,
        action_verb=f"cancelled production task {task.doc_number} ({reason})",
    )
    return FeedTaskCancelResult(task=task)
