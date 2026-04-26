"""
Сервис `cancel_incubation_run` — отменить партию инкубации.

Допустим только из INCUBATING/HATCHING. После TRANSFERRED — нельзя
(уже вышли цыплята — сервис hatch — компенсация отдельно).

Atomic:
    1. Guards: run.status in {INCUBATING, HATCHING}.
    2. Закрыть egg-batch как COMPLETED с current_quantity=0
       (все яйца списаны по причине отмены инкубации).
    3. run.status = CANCELLED + reason в notes.
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

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch

from ..models import IncubationRun
from .writeoff import create_writeoff_je


class IncubationCancelError(ValidationError):
    pass


@dataclass
class IncubationCancelResult:
    run: IncubationRun
    egg_batch: Batch
    writeoff_je: "JournalEntry | None" = None
    writeoff_amount_uzs: Decimal = Decimal("0")


@transaction.atomic
def cancel_incubation_run(
    run: IncubationRun,
    *,
    reason: str = "",
    user=None,
    cancelled_on: Optional[date_type] = None,
) -> IncubationCancelResult:
    run = IncubationRun.objects.select_for_update().get(pk=run.pk)
    run = IncubationRun.objects.select_related(
        "organization", "module", "batch"
    ).get(pk=run.pk)

    if run.status not in (
        IncubationRun.Status.INCUBATING,
        IncubationRun.Status.HATCHING,
    ):
        raise IncubationCancelError(
            {"status": (
                f"Отмена возможна из INCUBATING/HATCHING, "
                f"текущий: {run.get_status_display()}."
            )}
        )

    when = cancelled_on or timezone.localdate()

    egg_batch = Batch.objects.select_for_update().get(pk=run.batch_id)

    # Списываем остаток яиц в 91.02 ДО зануления current_quantity
    # (иначе cost_per_egg = деление на ноль).
    remaining = int(egg_batch.current_quantity) if egg_batch.current_quantity else 0
    writeoff = create_writeoff_je(
        run=run,
        egg_batch=egg_batch,
        eggs_to_writeoff=remaining,
        on_date=when,
        description_prefix=(
            f"Отмена инкубации {run.doc_number}"
            + (f" · {reason}" if reason else "")
        ),
        user=user,
    )

    # Теперь закрываем egg_batch
    egg_batch.refresh_from_db(fields=["accumulated_cost_uzs"])
    egg_batch.current_quantity = Decimal("0")
    egg_batch.state = Batch.State.COMPLETED
    egg_batch.completed_at = when
    if reason:
        note = f"[incubation cancel {run.doc_number}] {reason}"
        egg_batch.notes = (egg_batch.notes + "\n" + note).strip() if egg_batch.notes else note
    egg_batch.save(update_fields=["current_quantity", "state", "completed_at", "notes", "updated_at"])

    run.status = IncubationRun.Status.CANCELLED
    if reason:
        run.notes = (run.notes + f"\nОтмена: {reason}").strip() if run.notes else f"Отмена: {reason}"
    run.save(update_fields=["status", "notes", "updated_at"])

    audit_log(
        organization=run.organization,
        module=run.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=run,
        action_verb=f"cancelled incubation run {run.doc_number} ({reason})",
    )

    return IncubationCancelResult(
        run=run,
        egg_batch=egg_batch,
        writeoff_je=writeoff.journal_entry,
        writeoff_amount_uzs=writeoff.amount_uzs,
    )
