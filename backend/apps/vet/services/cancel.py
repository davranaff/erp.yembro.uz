"""
Сервис `cancel_vet_treatment` — отмена проведённого лечения с реверсом проводок.

Atomic-транзакция:
  1. Guards: treatment не отменён ранее, JournalEntry от apply существует.
  2. Compensating JournalEntry: Дт 10.03 / Кт 20.XX (обратка) на ту же сумму.
  3. StockMovement INCOMING: вернуть на лот current_quantity (если лот не RECALLED).
  4. BatchCostEntry: создать отрицательную запись + откатить Batch.accumulated_cost_uzs.
  5. Batch.withdrawal_period_ends: пересчитать на основе оставшихся активных
     лечений этой партии. Если других нет → None.
  6. treatment.cancelled_at + cancelled_by + cancel_reason.
  7. AuditLog с reason.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchCostEntry
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import VetStockBatch, VetTreatmentLog


class VetTreatmentCancelError(ValidationError):
    pass


@dataclass
class VetTreatmentCancelResult:
    treatment: VetTreatmentLog
    reversal_je: JournalEntry
    reversal_sm: Optional[StockMovement]
    new_withdrawal_end: Optional[object]  # date | None


@transaction.atomic
def cancel_vet_treatment(
    treatment: VetTreatmentLog,
    *,
    reason: str,
    user=None,
) -> VetTreatmentCancelResult:
    if not reason or len(reason.strip()) < 3:
        raise VetTreatmentCancelError(
            {"reason": "Укажите причину отмены (мин. 3 символа)."}
        )

    # 1. Lock + reload
    treatment = VetTreatmentLog.objects.select_for_update().get(pk=treatment.pk)
    treatment = VetTreatmentLog.objects.select_related(
        "organization", "module",
        "drug__nomenclature", "stock_batch",
        "target_batch", "target_block", "target_block__module", "target_herd",
        "unit",
    ).get(pk=treatment.pk)

    if treatment.cancelled_at is not None:
        raise VetTreatmentCancelError(
            {"__all__": "Лечение уже отменено."}
        )

    # 2. Найти оригинальный JE
    ct = ContentType.objects.get_for_model(VetTreatmentLog)
    original_je = (
        JournalEntry.objects
        .filter(source_content_type=ct, source_object_id=treatment.id)
        .order_by("created_at")
        .first()
    )
    if original_je is None:
        raise VetTreatmentCancelError(
            {"__all__": "Не найдена проводка применения — нечего отменять."}
        )

    org = treatment.organization
    cost = original_je.amount_uzs
    now = timezone.now()

    # 3. Compensating JournalEntry: меняем Дт/Кт местами.
    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР",
        on_date=treatment.treatment_date,
    )
    reversal_je = JournalEntry(
        organization=org,
        module=original_je.module,
        doc_number=je_number,
        entry_date=treatment.treatment_date,
        description=(
            f"Сторно вет. применения {treatment.doc_number or ''} · "
            f"{treatment.drug.nomenclature.sku} · причина: {reason}"
        ).strip(),
        debit_subaccount=original_je.credit_subaccount,
        credit_subaccount=original_je.debit_subaccount,
        amount_uzs=cost,
        source_content_type=ct,
        source_object_id=treatment.id,
        batch=treatment.target_batch,
        created_by=user,
    )
    reversal_je.full_clean(exclude=None)
    reversal_je.save()

    # 4. Возврат остатка на лот (только если лот не RECALLED — иначе остаток
    # списан физически и возвращать некуда).
    reversal_sm = None
    stock_batch = treatment.stock_batch
    if stock_batch.status != VetStockBatch.Status.RECALLED:
        VetStockBatch.objects.filter(pk=stock_batch.pk).update(
            current_quantity=F("current_quantity") + treatment.dose_quantity
        )
        stock_batch.refresh_from_db(fields=["current_quantity", "status"])
        # Если был DEPLETED — поднять обратно в AVAILABLE
        if (
            stock_batch.status == VetStockBatch.Status.DEPLETED
            and stock_batch.current_quantity > 0
        ):
            stock_batch.status = VetStockBatch.Status.AVAILABLE
            stock_batch.save(update_fields=["status", "updated_at"])

        sm_number = next_doc_number(
            StockMovement, organization=org, prefix="СД",
            on_date=treatment.treatment_date,
        )
        sm_qty = treatment.dose_quantity.quantize(Decimal("0.001"))
        reversal_sm = StockMovement(
            organization=org,
            module=treatment.module,
            doc_number=sm_number,
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=treatment.drug.nomenclature,
            quantity=sm_qty,
            unit_price_uzs=stock_batch.price_per_unit_uzs,
            amount_uzs=cost,
            warehouse_from=None,
            warehouse_to=stock_batch.warehouse,
            batch=treatment.target_batch,
            source_content_type=ct,
            source_object_id=treatment.id,
            created_by=user,
        )
        reversal_sm.full_clean(exclude=None)
        reversal_sm.save()

    # 5. Откат BatchCostEntry + Batch.accumulated_cost_uzs
    if treatment.target_batch_id and cost > 0:
        BatchCostEntry.objects.create(
            batch=treatment.target_batch,
            category=BatchCostEntry.Category.VET,
            amount_uzs=-cost,
            description=(
                f"Сторно вет. применения {treatment.drug.nomenclature.sku} · "
                f"{treatment.dose_quantity} {treatment.unit.code} · "
                f"причина: {reason}"
            ),
            occurred_at=now,
            module=original_je.module,
            source_content_type=ct,
            source_object_id=treatment.id,
            created_by=user,
        )
        Batch.objects.filter(pk=treatment.target_batch_id).update(
            accumulated_cost_uzs=F("accumulated_cost_uzs") - cost
        )

    # 6. Пересчёт withdrawal_period_ends на batch
    new_end = None
    if treatment.target_batch_id and treatment.withdrawal_period_days > 0:
        batch = Batch.objects.select_for_update().get(pk=treatment.target_batch_id)

        # Соберём максимальную дату каренции из ОСТАЛЬНЫХ активных лечений
        # этой партии (не отменённых, кроме нашего).
        other_active = VetTreatmentLog.objects.filter(
            target_batch=treatment.target_batch,
            cancelled_at__isnull=True,
            withdrawal_period_days__gt=0,
        ).exclude(pk=treatment.pk)

        max_end = None
        for t in other_active:
            candidate = t.treatment_date + timedelta(days=t.withdrawal_period_days)
            if max_end is None or candidate > max_end:
                max_end = candidate

        if batch.withdrawal_period_ends != max_end:
            batch.withdrawal_period_ends = max_end
            batch.save(update_fields=["withdrawal_period_ends", "updated_at"])
        new_end = max_end

    # 7. Помечаем treatment как отменённый
    treatment.cancelled_at = now
    treatment.cancelled_by = user
    treatment.cancel_reason = reason
    treatment.save(
        update_fields=["cancelled_at", "cancelled_by", "cancel_reason", "updated_at"]
    )

    audit_log(
        organization=org,
        module=treatment.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=treatment,
        action_verb=(
            f"cancelled vet treatment {treatment.doc_number or ''} · "
            f"{treatment.drug.nomenclature.sku} · reason: {reason}"
        ).strip(),
    )

    return VetTreatmentCancelResult(
        treatment=treatment,
        reversal_je=reversal_je,
        reversal_sm=reversal_sm,
        new_withdrawal_end=new_end,
    )
