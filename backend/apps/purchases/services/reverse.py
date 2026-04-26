"""
Сервис `reverse_purchase` — сторно проведённого закупа.

В бухгалтерском учёте «отменить» проведённый документ нельзя —
создаётся компенсирующая проводка с противоположными знаками.

Что делает atomic:
    1. Guards:
       - order.status = CONFIRMED (нельзя сторнировать уже PAID/CANCELLED/DRAFT).
       - Закуп не оплачен (paid_amount_uzs == 0) — иначе нужен reverse_payment сначала.
    2. Создать reverse StockMovement (kind=WRITE_OFF) на каждую
       исходную incoming-позицию: списывает обратно со склада.
    3. Создать reverse JournalEntry: меняет местами Dr/Cr исходной проводки.
    4. order.status = CANCELLED.
    5. AuditLog.

Исходные документы (StockMovement, JournalEntry) остаются — они
бухгалтерски иммутабельны. В истории будет: приход → сторно.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import PurchaseOrder


class PurchaseReverseError(ValidationError):
    pass


@dataclass
class PurchaseReverseResult:
    order: PurchaseOrder
    reverse_movements: list
    reverse_journal: JournalEntry


@transaction.atomic
def reverse_purchase(
    order: PurchaseOrder, *, reason: str = "", user=None
) -> PurchaseReverseResult:
    """
    Сторно проведённого закупа: компенсирующие проводки + статус CANCELLED.
    """
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    order = PurchaseOrder.objects.select_related(
        "organization", "module", "counterparty", "warehouse"
    ).get(pk=order.pk)

    if order.status != PurchaseOrder.Status.CONFIRMED:
        raise PurchaseReverseError(
            {"status": f"Сторно возможно только из CONFIRMED, текущий: {order.get_status_display()}."}
        )
    # Гард 1: явная проверка по payment_status — не должно быть зарегистрированных платежей
    if order.payment_status != PurchaseOrder.PaymentStatus.UNPAID:
        raise PurchaseReverseError(
            {
                "payment_status": (
                    f"Закуп в статусе оплаты «{order.get_payment_status_display()}». "
                    f"Сторно возможно только если по закупу нет платежей. "
                    f"Сначала отмените все Payment'ы через reverse_payment."
                )
            }
        )
    # Гард 2: даже если payment_status=UNPAID но paid_amount_uzs>0 (рассинхрон) — запретим
    if order.paid_amount_uzs > 0:
        raise PurchaseReverseError(
            {
                "payment_status": (
                    f"Закуп частично оплачен ({order.paid_amount_uzs} UZS). "
                    f"Сначала отмените платежи через reverse_payment."
                )
            }
        )

    org = order.organization
    ct_order = ContentType.objects.get_for_model(PurchaseOrder)

    # Оригинальные движения
    source_movements = list(
        StockMovement.objects.filter(
            source_content_type=ct_order, source_object_id=order.id,
            kind=StockMovement.Kind.INCOMING,
        )
    )
    if not source_movements:
        raise PurchaseReverseError(
            {"__all__": "Не найдены stock movements исходного закупа."}
        )

    # Оригинальная проводка
    source_je = JournalEntry.objects.filter(
        source_content_type=ct_order, source_object_id=order.id,
    ).first()
    if not source_je:
        raise PurchaseReverseError(
            {"__all__": "Не найдена исходная проводка закупа."}
        )

    now = timezone.now()

    # Reverse stock movements (WRITE_OFF)
    reverse_movements = []
    for sm in source_movements:
        new_number = next_doc_number(
            StockMovement, organization=org, prefix="СД",
            on_date=order.date,
        )
        reverse_sm = StockMovement(
            organization=org,
            module=order.module,
            doc_number=new_number,
            kind=StockMovement.Kind.WRITE_OFF,
            date=now,
            nomenclature=sm.nomenclature,
            quantity=sm.quantity,
            unit_price_uzs=sm.unit_price_uzs,
            amount_uzs=sm.amount_uzs,
            warehouse_from=sm.warehouse_to,  # обратно списываем со склада-получателя
            warehouse_to=None,
            counterparty=sm.counterparty,
            batch=sm.batch,
            source_content_type=ct_order,
            source_object_id=order.id,
            created_by=user,
        )
        reverse_sm.full_clean(exclude=None)
        reverse_sm.save()
        reverse_movements.append(reverse_sm)

    # Reverse JournalEntry: меняем местами Dr/Cr
    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=order.date
    )
    reverse_je = JournalEntry(
        organization=org,
        module=order.module,
        doc_number=je_number,
        entry_date=order.date,
        description=(
            f"Сторно закупа {order.doc_number} · {reason or 'reversal'}"
        ),
        debit_subaccount=source_je.credit_subaccount,  # swap!
        credit_subaccount=source_je.debit_subaccount,
        amount_uzs=source_je.amount_uzs,
        currency=source_je.currency,
        amount_foreign=source_je.amount_foreign,
        exchange_rate=source_je.exchange_rate,
        source_content_type=ct_order,
        source_object_id=order.id,
        counterparty=order.counterparty,
        batch=order.batch,
        created_by=user,
    )
    reverse_je.full_clean(exclude=None)
    reverse_je.save()

    # Статус
    order.status = PurchaseOrder.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=org,
        module=order.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=order,
        action_verb=f"reversed purchase {order.doc_number} ({reason})",
    )

    return PurchaseReverseResult(
        order=order,
        reverse_movements=reverse_movements,
        reverse_journal=reverse_je,
    )
