"""
Сервис `reverse_payment` — сторно проведённого платежа.

Создаёт компенсирующую проводку (Dr ↔ Cr поменяны местами), меняет
статус платежа на CANCELLED, пересчитывает payment_status аллоцированных
PurchaseOrder / SaleOrder.

Allocations не удаляются — они нужны для аудита. Но `_recalc_*` фильтрует
по `Payment.status=POSTED`, поэтому после смены статуса на CANCELLED
этот платёж перестаёт влиять на сумму paid.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleOrder

from ..models import Payment, PaymentAllocation
from .post import _recalc_purchase_payment_status, _recalc_sale_payment_status


class PaymentReverseError(ValidationError):
    pass


@dataclass
class PaymentReverseResult:
    payment: Payment
    reverse_journal: JournalEntry
    affected_orders: list


@transaction.atomic
def reverse_payment(
    payment: Payment, *, reason: str = "", user=None
) -> PaymentReverseResult:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    payment = Payment.objects.select_related(
        "organization", "module", "counterparty",
        "cash_subaccount__account", "journal_entry",
    ).get(pk=payment.pk)

    if payment.status != Payment.Status.POSTED:
        raise PaymentReverseError(
            {"status": f"Сторно возможно только из POSTED: {payment.get_status_display()}."}
        )
    if not payment.journal_entry_id:
        raise PaymentReverseError(
            {"__all__": "У платежа нет связанной JournalEntry."}
        )

    org = payment.organization
    source_je = payment.journal_entry
    ct_payment = ContentType.objects.get_for_model(Payment)

    # Reverse JE
    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=payment.date
    )
    reverse_je = JournalEntry(
        organization=org,
        module=payment.module,
        doc_number=je_number,
        entry_date=payment.date,
        description=f"Сторно платежа {payment.doc_number} · {reason or 'reversal'}",
        debit_subaccount=source_je.credit_subaccount,
        credit_subaccount=source_je.debit_subaccount,
        amount_uzs=source_je.amount_uzs,
        currency=source_je.currency,
        amount_foreign=source_je.amount_foreign,
        exchange_rate=source_je.exchange_rate,
        source_content_type=ct_payment,
        source_object_id=payment.id,
        counterparty=payment.counterparty,
        created_by=user,
    )
    reverse_je.full_clean(exclude=None)
    reverse_je.save()

    # Платёж → CANCELLED
    payment.status = Payment.Status.CANCELLED
    payment.save(update_fields=["status", "updated_at"])

    # Пересчёт затронутых PO/SO (аллокации остаются, но _recalc_* учитывают
    # только POSTED платежи — после смены статуса этот платёж выпадет).
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    so_ct = ContentType.objects.get_for_model(SaleOrder)

    affected_orders = []

    po_ids = {
        a.target_object_id
        for a in payment.allocations.filter(target_content_type=po_ct)
    }
    for oid in po_ids:
        try:
            order = PurchaseOrder.objects.select_for_update().get(pk=oid)
        except PurchaseOrder.DoesNotExist:
            continue
        _recalc_purchase_payment_status(order)
        affected_orders.append(order)

    so_ids = {
        a.target_object_id
        for a in payment.allocations.filter(target_content_type=so_ct)
    }
    for oid in so_ids:
        try:
            sale = SaleOrder.objects.select_for_update().get(pk=oid)
        except SaleOrder.DoesNotExist:
            continue
        _recalc_sale_payment_status(sale)
        affected_orders.append(sale)

    audit_log(
        organization=org,
        module=payment.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=payment,
        action_verb=f"reversed payment {payment.doc_number} ({reason})",
    )

    return PaymentReverseResult(
        payment=payment,
        reverse_journal=reverse_je,
        affected_orders=affected_orders,
    )
