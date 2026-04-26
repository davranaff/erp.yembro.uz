"""
Сервис `close_batch` — формально закрыть партию.

Проверяет что партия действительно пуста (current_quantity == 0) или
принудительно обнуляет остаток (list/off — write-off через отдельный
StockMovement; тут `force=True` без движения — только пометка).

Вызывается обычно внутри других сервисов (hatch, post_slaughter_shift),
но доступен как standalone для кейсов:
    - инкубация остановлена без вывода (см. cancel_incubation_run)
    - партия обнулилась падежом (и теперь надо формально её закрыть)
    - ручное закрытие хвостов «по нулям»

Atomic:
    1. Guards:
       - batch.state = ACTIVE (нельзя закрыть дважды).
       - если `force=False`: current_quantity == 0.
    2. state = COMPLETED, completed_at = closed_on (default today).
    3. Закрываем последний открытый BatchChainStep (exited_at, quantity_out).
    4. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import Batch, BatchChainStep


class BatchCloseError(ValidationError):
    pass


@dataclass
class BatchCloseResult:
    batch: Batch
    closed_chain_step: Optional[BatchChainStep]


@transaction.atomic
def close_batch(
    batch: Batch,
    *,
    closed_on: Optional[date_type] = None,
    force: bool = False,
    reason: str = "",
    user=None,
) -> BatchCloseResult:
    batch = Batch.objects.select_for_update().get(pk=batch.pk)

    if batch.state != Batch.State.ACTIVE:
        raise BatchCloseError(
            {"state": f"Партия уже не активна: {batch.get_state_display()}."}
        )

    if not force and batch.current_quantity != 0:
        raise BatchCloseError(
            {"current_quantity": (
                f"Остаток {batch.current_quantity} ≠ 0 — используйте "
                f"force=True или проведите списание."
            )}
        )

    when = closed_on or timezone.localdate()

    if force and batch.current_quantity != 0:
        batch.current_quantity = Decimal("0")

    batch.state = Batch.State.COMPLETED
    batch.completed_at = when
    if reason:
        note = f"[close {when}] {reason}"
        batch.notes = (batch.notes + "\n" + note).strip() if batch.notes else note

    batch.save(update_fields=[
        "state", "current_quantity", "completed_at", "notes", "updated_at"
    ])

    # Закрыть последний открытый chain-step
    open_step = (
        BatchChainStep.objects.select_for_update()
        .filter(batch=batch, exited_at__isnull=True)
        .order_by("-sequence")
        .first()
    )
    if open_step is not None:
        open_step.exited_at = timezone.now()
        open_step.quantity_out = Decimal("0")
        open_step.accumulated_cost_at_exit = batch.accumulated_cost_uzs
        open_step.save(update_fields=[
            "exited_at", "quantity_out", "accumulated_cost_at_exit", "updated_at"
        ])

    audit_log(
        organization=batch.organization,
        module=batch.current_module or batch.origin_module,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=batch,
        action_verb=f"closed batch {batch.doc_number} ({reason or 'manual close'})",
    )

    return BatchCloseResult(batch=batch, closed_chain_step=open_step)
