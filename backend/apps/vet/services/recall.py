"""
Сервис `recall_vet_stock_batch` — отзыв (recall) лота препарата.

Atomic-транзакция:
  1. Guards: лот ещё не отозван, статус позволяет (AVAILABLE/EXPIRING_SOON/QUARANTINE/DEPLETED).
  2. Cancel всех связанных VetTreatmentLog (не отменённых ранее) — через
     `cancel_vet_treatment` с reason="recall: <original reason>".
  3. status → RECALLED, recalled_at = now(), recall_reason = reason.
  4. AuditLog с reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import VetStockBatch, VetTreatmentLog
from .cancel import cancel_vet_treatment


class VetRecallError(ValidationError):
    pass


@dataclass
class VetRecallResult:
    stock_batch: VetStockBatch
    cancelled_treatments: List[VetTreatmentLog] = field(default_factory=list)
    write_off_movement: Optional[StockMovement] = None


@transaction.atomic
def recall_vet_stock_batch(
    stock_batch: VetStockBatch,
    *,
    reason: str,
    user=None,
) -> VetRecallResult:
    if not reason or len(reason.strip()) < 3:
        raise VetRecallError(
            {"reason": "Укажите причину отзыва (мин. 3 символа)."}
        )

    # 1. Lock + reload
    stock_batch = VetStockBatch.objects.select_for_update().get(pk=stock_batch.pk)

    if stock_batch.status == VetStockBatch.Status.RECALLED:
        raise VetRecallError({"__all__": "Лот уже отозван."})

    org = stock_batch.organization
    cancelled = []

    # 2. Cancel всех активных лечений с этим лотом
    active_treatments = (
        VetTreatmentLog.objects
        .filter(stock_batch=stock_batch, cancelled_at__isnull=True)
        .select_related("drug__nomenclature")
    )
    for t in active_treatments:
        # Проверим что у лечения есть JE (т.е. оно реально проведено).
        # Если JE нет — просто помечаем cancelled без compensating записей.
        from django.contrib.contenttypes.models import ContentType
        from apps.accounting.models import JournalEntry

        ct = ContentType.objects.get_for_model(VetTreatmentLog)
        has_je = JournalEntry.objects.filter(
            source_content_type=ct, source_object_id=t.id,
        ).exists()
        if has_je:
            cancel_vet_treatment(
                t,
                reason=f"recall лота {stock_batch.doc_number}: {reason}",
                user=user,
            )
            cancelled.append(t)
        else:
            t.cancelled_at = timezone.now()
            t.cancelled_by = user
            t.cancel_reason = f"recall: {reason}"
            t.save(update_fields=[
                "cancelled_at", "cancelled_by", "cancel_reason", "updated_at"
            ])
            cancelled.append(t)

    # 3. Перевод лота в RECALLED.
    # Важно: после cancel'ов остаток мог увеличиться (мы вернули списания).
    # При recall физическая партия списывается со склада → current_quantity = 0.
    stock_batch.refresh_from_db()
    write_off_qty = Decimal(stock_batch.current_quantity or 0)
    stock_batch.status = VetStockBatch.Status.RECALLED
    stock_batch.recalled_at = timezone.now()
    stock_batch.recall_reason = reason
    stock_batch.current_quantity = 0
    stock_batch.save(update_fields=[
        "status", "recalled_at", "recall_reason", "current_quantity", "updated_at"
    ])

    # 4. Compensating WRITE_OFF в журнал склада — иначе остаётся «фантомный»
    # положительный баланс (у нас INCOMING на receive есть, но физически
    # партия больше не существует). Симметрично receive_vet_stock_batch
    # который создаёт INCOMING — recall закрывает баланс.
    write_off_sm = None
    if write_off_qty > 0:
        sm_number = next_doc_number(
            StockMovement, organization=org, prefix="СД",
        )
        price = Decimal(stock_batch.price_per_unit_uzs)
        amount = (write_off_qty * price).quantize(Decimal("0.01"))
        ct = ContentType.objects.get_for_model(VetStockBatch)
        write_off_sm = StockMovement(
            organization=org,
            module=stock_batch.module,
            doc_number=sm_number,
            kind=StockMovement.Kind.WRITE_OFF,
            date=timezone.now(),
            nomenclature=stock_batch.drug.nomenclature,
            quantity=write_off_qty,
            unit_price_uzs=price,
            amount_uzs=amount,
            warehouse_from=stock_batch.warehouse,
            warehouse_to=None,
            source_content_type=ct,
            source_object_id=stock_batch.id,
            created_by=user,
        )
        write_off_sm.full_clean(exclude=None)
        write_off_sm.save()

    audit_log(
        organization=org,
        module=stock_batch.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=stock_batch,
        action_verb=(
            f"recalled vet stock batch {stock_batch.doc_number} · "
            f"reason: {reason} · cancelled treatments: {len(cancelled)}"
        ),
    )

    return VetRecallResult(
        stock_batch=stock_batch,
        cancelled_treatments=cancelled,
        write_off_movement=write_off_sm,
    )
