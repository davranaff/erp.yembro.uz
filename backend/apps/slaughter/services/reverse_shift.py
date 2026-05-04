"""
Сервис `reverse_slaughter_shift` — сторно проведённой смены убоя.

Компенсирующие проводки + списание оприходованной ГП. Исходный
source_batch возвращается в состояние «не списан».

Atomic:
    1. Guards: shift.status == POSTED.
    2. По каждому output_batch:
       - reverse StockMovement (WRITE_OFF из output_warehouse).
       - output_batch.state = CANCELLED, current_quantity = 0.
    3. Reverse source_batch write-off:
       - StockMovement INCOMING обратно в source_warehouse
         (восстанавливаем живую птицу).
       - source_batch.state = ACTIVE, current_quantity = initial_quantity
         (возвращаем к значению до смены).
    4. Reverse JournalEntries (Dr/Cr swap) — по каждому JE смены.
    5. shift.status = CANCELLED.
    6. AuditLog.

ВАЖНО: если по output_batch уже были ОПЕРАЦИИ (отгрузка со склада ГП)
— сервис отказывается сторнировать. Операционно: надо сначала вернуть
эти движения.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import SlaughterShift


class SlaughterReverseError(ValidationError):
    pass


@dataclass
class SlaughterReverseResult:
    shift: SlaughterShift
    source_batch: Batch
    reverse_movements: list
    reverse_journals: list


@transaction.atomic
def reverse_slaughter_shift(
    shift: SlaughterShift,
    *,
    reason: str = "",
    user=None,
) -> SlaughterReverseResult:
    shift = SlaughterShift.objects.select_for_update().get(pk=shift.pk)
    shift = SlaughterShift.objects.select_related(
        "organization", "module", "source_batch"
    ).get(pk=shift.pk)

    if shift.status != SlaughterShift.Status.POSTED:
        raise SlaughterReverseError(
            {"status": (
                f"Сторно возможно только из POSTED, "
                f"текущий: {shift.get_status_display()}."
            )}
        )

    org = shift.organization
    source_batch = shift.source_batch

    ct_shift = ContentType.objects.get_for_model(SlaughterShift)

    # 1. Найти все output_batches (child-партии смены) и убедиться что
    #    по ним не было дальнейших движений.
    output_batches = list(
        Batch.objects.select_for_update().filter(
            parent_batch=source_batch,
            origin_module=shift.module,
        )
    )
    for ob in output_batches:
        if ob.current_quantity != ob.initial_quantity:
            raise SlaughterReverseError(
                {"output_batches": (
                    f"По партии ГП {ob.doc_number} уже были движения "
                    f"(остаток {ob.current_quantity}/{ob.initial_quantity}). "
                    f"Сторно невозможно — сначала верните отгрузки."
                )}
            )

    # 2. Оригинальные движения
    orig_movements = list(
        StockMovement.objects.filter(
            source_content_type=ct_shift, source_object_id=shift.id,
        )
    )
    if not orig_movements:
        raise SlaughterReverseError(
            {"__all__": "Не найдены stock movements исходной смены."}
        )

    orig_journals = list(
        JournalEntry.objects.filter(
            source_content_type=ct_shift, source_object_id=shift.id,
        )
    )
    if not orig_journals:
        raise SlaughterReverseError(
            {"__all__": "Не найдены журнальные проводки исходной смены."}
        )

    now = timezone.now()

    # 3. Reverse StockMovement: swap направление (OUT ↔ IN, WRITE_OFF → IN)
    reverse_movements = []
    for sm in orig_movements:
        new_number = next_doc_number(
            StockMovement, organization=org, prefix="СД",
            on_date=shift.shift_date,
        )
        if sm.kind == StockMovement.Kind.INCOMING:
            # Оприходование ГП → списание ГП обратно
            rev_kind = StockMovement.Kind.WRITE_OFF
            wh_from = sm.warehouse_to
            wh_to = None
        elif sm.kind == StockMovement.Kind.OUTGOING:
            # Списание живой птицы → возврат
            rev_kind = StockMovement.Kind.INCOMING
            wh_from = None
            wh_to = sm.warehouse_from
        else:
            continue

        rev_sm = StockMovement(
            organization=org,
            module=shift.module,
            doc_number=new_number,
            kind=rev_kind,
            date=now,
            nomenclature=sm.nomenclature,
            quantity=sm.quantity,
            unit_price_uzs=sm.unit_price_uzs,
            amount_uzs=sm.amount_uzs,
            warehouse_from=wh_from,
            warehouse_to=wh_to,
            counterparty=sm.counterparty,
            batch=sm.batch,
            source_content_type=ct_shift,
            source_object_id=shift.id,
            created_by=user,
        )
        rev_sm.full_clean(exclude=None)
        rev_sm.save()
        reverse_movements.append(rev_sm)

    # 4. Reverse JournalEntries — Dr/Cr swap
    reverse_journals = []
    for je in orig_journals:
        rev_number = next_doc_number(
            JournalEntry, organization=org, prefix="ПР", on_date=shift.shift_date,
        )
        rev_je = JournalEntry(
            organization=org,
            module=shift.module,
            doc_number=rev_number,
            entry_date=shift.shift_date,
            description=f"Сторно смены убоя {shift.doc_number} · {reason or 'reversal'}",
            debit_subaccount=je.credit_subaccount,
            credit_subaccount=je.debit_subaccount,
            amount_uzs=je.amount_uzs,
            currency=je.currency,
            amount_foreign=je.amount_foreign,
            exchange_rate=je.exchange_rate,
            source_content_type=ct_shift,
            source_object_id=shift.id,
            batch=je.batch,
            created_by=user,
        )
        rev_je.full_clean(exclude=None)
        rev_je.save()
        reverse_journals.append(rev_je)

    # 5. Возврат source_batch
    source_batch = Batch.objects.select_for_update().get(pk=source_batch.pk)
    source_batch.state = Batch.State.ACTIVE
    source_batch.current_quantity = source_batch.initial_quantity
    source_batch.completed_at = None
    source_batch.save(update_fields=[
        "state", "current_quantity", "completed_at", "updated_at"
    ])

    # 6. Гасим output_batches
    for ob in output_batches:
        ob.state = Batch.State.REJECTED
        ob.current_quantity = Decimal("0")
        ob.completed_at = timezone.localdate()
        ob.save(update_fields=[
            "state", "current_quantity", "completed_at", "updated_at"
        ])

    # 7. Shift → CANCELLED
    shift.status = SlaughterShift.Status.CANCELLED
    shift.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=org,
        module=shift.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=shift,
        action_verb=f"reversed slaughter shift {shift.doc_number} ({reason})",
    )

    return SlaughterReverseResult(
        shift=shift,
        source_batch=source_batch,
        reverse_movements=reverse_movements,
        reverse_journals=reverse_journals,
    )
