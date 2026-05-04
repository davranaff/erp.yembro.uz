"""
Сервис `reverse_sale` — сторно проведённой продажи.

Atomic:
    1. Guards: status=CONFIRMED, paid_amount_uzs=0.
    2. По каждой исходной OUTGOING StockMovement → INCOMING (возврат);
       возврат остатка в источник партии (batch / feed_batch / vet_stock_batch),
       восстановление state=ACTIVE если был COMPLETED.
    3. Reverse JournalEntry для каждой исходной JE (Dr ↔ Cr swap).
    4. status = CANCELLED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import SaleOrder


class SaleReverseError(ValidationError):
    pass


@dataclass
class SaleReverseResult:
    order: SaleOrder
    reverse_movements: list = field(default_factory=list)
    reverse_journals: list = field(default_factory=list)


def _restore_source(item):
    """Вернуть quantity в источник партии."""
    qty = Decimal(item.quantity)
    if item.batch_id:
        Batch.objects.filter(pk=item.batch_id).update(
            current_quantity=F("current_quantity") + qty
        )
        b = Batch.objects.get(pk=item.batch_id)
        if b.state == Batch.State.COMPLETED and b.current_quantity > 0:
            b.state = Batch.State.ACTIVE
            b.completed_at = None
            b.save(update_fields=["state", "completed_at", "updated_at"])
        return
    if item.feed_batch_id:
        from apps.feed.models import FeedBatch
        FeedBatch.objects.filter(pk=item.feed_batch_id).update(
            current_quantity_kg=F("current_quantity_kg") + qty
        )
        return
    if item.vet_stock_batch_id:
        from apps.vet.models import VetStockBatch
        VetStockBatch.objects.filter(pk=item.vet_stock_batch_id).update(
            current_quantity=F("current_quantity") + qty
        )
        vsb = VetStockBatch.objects.get(pk=item.vet_stock_batch_id)
        if vsb.status == VetStockBatch.Status.DEPLETED and vsb.current_quantity > 0:
            vsb.status = VetStockBatch.Status.AVAILABLE
            vsb.save(update_fields=["status", "updated_at"])


@transaction.atomic
def reverse_sale(order: SaleOrder, *, reason: str = "", user=None) -> SaleReverseResult:
    order = SaleOrder.objects.select_for_update().get(pk=order.pk)
    order = SaleOrder.objects.select_related(
        "organization", "module", "customer", "warehouse",
    ).get(pk=order.pk)

    if order.status != SaleOrder.Status.CONFIRMED:
        raise SaleReverseError(
            {"status": (
                f"Сторно возможно только из CONFIRMED, текущий: "
                f"{order.get_status_display()}."
            )}
        )
    if order.paid_amount_uzs and order.paid_amount_uzs > 0:
        raise SaleReverseError(
            {"payment_status": (
                f"Продажа частично оплачена ({order.paid_amount_uzs} UZS). "
                f"Сначала отмените платежи через reverse_payment."
            )}
        )

    org = order.organization
    so_ct = ContentType.objects.get_for_model(SaleOrder)

    source_movements = list(
        StockMovement.objects.filter(
            source_content_type=so_ct,
            source_object_id=order.id,
            kind=StockMovement.Kind.OUTGOING,
        )
    )
    if not source_movements:
        raise SaleReverseError(
            {"__all__": "Не найдены OUTGOING-движения исходной продажи."}
        )

    source_journals = list(
        JournalEntry.objects.filter(
            source_content_type=so_ct, source_object_id=order.id,
        )
    )
    if not source_journals:
        raise SaleReverseError(
            {"__all__": "Не найдены проводки исходной продажи."}
        )

    now = timezone.now()
    reverse_movements = []
    reverse_journals = []

    # 1. INCOMING-движения (возврат)
    for sm in source_movements:
        rev_sm = StockMovement(
            organization=org,
            module=order.module,
            doc_number=next_doc_number(
                StockMovement, organization=org,
                prefix="СД", on_date=order.date,
            ),
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=sm.nomenclature,
            quantity=sm.quantity,
            unit_price_uzs=sm.unit_price_uzs,
            amount_uzs=sm.amount_uzs,
            warehouse_from=None,
            warehouse_to=sm.warehouse_from,
            counterparty=sm.counterparty,
            batch=sm.batch,
            source_content_type=so_ct,
            source_object_id=order.id,
            created_by=user,
        )
        rev_sm.full_clean(exclude=None)
        rev_sm.save()
        reverse_movements.append(rev_sm)

    # 2. Восстановить остатки источников по items
    for item in order.items.select_related("batch", "feed_batch", "vet_stock_batch"):
        _restore_source(item)

    # 3. Reverse JE — Dr ↔ Cr swap для каждой
    for je in source_journals:
        rev_je = JournalEntry(
            organization=org,
            module=order.module,
            doc_number=next_doc_number(
                JournalEntry, organization=org,
                prefix="ПР", on_date=order.date,
            ),
            entry_date=order.date,
            description=(
                f"Сторно продажи {order.doc_number} · {reason or 'reversal'}"
            ),
            debit_subaccount=je.credit_subaccount,
            credit_subaccount=je.debit_subaccount,
            amount_uzs=je.amount_uzs,
            currency=je.currency,
            amount_foreign=je.amount_foreign,
            exchange_rate=je.exchange_rate,
            source_content_type=so_ct,
            source_object_id=order.id,
            counterparty=order.customer,
            batch=je.batch,
            created_by=user,
        )
        rev_je.full_clean(exclude=None)
        rev_je.save()
        reverse_journals.append(rev_je)

    order.status = SaleOrder.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=org,
        module=order.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=order,
        action_verb=f"reversed sale {order.doc_number} ({reason})",
    )

    return SaleReverseResult(
        order=order,
        reverse_movements=reverse_movements,
        reverse_journals=reverse_journals,
    )
