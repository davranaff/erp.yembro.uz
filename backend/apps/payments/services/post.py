"""
Сервис `post_payment` — проведение платежа.

Что делает в одной atomic-транзакции:
    1. Проверяет статус (только DRAFT/CONFIRMED → POSTED).
    2. Определяет cash-субсчёт по channel (CASH→50.01, TRANSFER/CLICK→51.01)
       если он не задан явно.
    3. Генерирует doc_number (ПЛ-YYYY-NNNNN) если пуст.
    4. Создаёт JournalEntry:
         OUT: Dr 60.01 (UZS) или 60.02 (FX) / Cr cash_subaccount
         IN : Dr cash_subaccount / Cr 62.01 (UZS) или 62.02 (FX)
       С FX-snapshot в полях JE.
    5. Привязывает journal_entry к Payment.
    6. Пересчитывает paid_amount_uzs на затронутых PurchaseOrder / SaleOrder
       (сумма всех аллокаций к этому документу) и обновляет payment_status:
          paid = 0          → unpaid
          0 < paid < amount → partial
          paid == amount    → paid
          paid > amount     → overpaid
    7. Переводит Payment.status = POSTED, ставит posted_at.

Ключевые инварианты:
    - Сумма аллокаций == amount_uzs платежа (или 0, если аллокаций нет).
    - OUT → аллокации только на PurchaseOrder.
    - IN  → аллокации только на SaleOrder.
    - Повторный post → ValidationError.
    - После POSTED поля snapshot неизменяемы (enforced в сериализаторе).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleOrder

from ..models import Payment, PaymentAllocation


# ─── GL policy ────────────────────────────────────────────────────────────

CASH_SUBACCOUNT_BY_CHANNEL = {
    Payment.Channel.CASH: "50.01",
    Payment.Channel.TRANSFER: "51.01",
    Payment.Channel.CLICK: "51.01",
    # OTHER обязан ставиться явно — сервис требует cash_subaccount.
}

AP_SUBACCOUNT_UZS = "60.01"
AP_SUBACCOUNT_FX = "60.02"
AR_SUBACCOUNT_UZS = "62.01"
AR_SUBACCOUNT_FX = "62.02"


class PaymentPostError(ValidationError):
    """Ошибка проведения платежа — можно ловить отдельно в API."""


@dataclass
class PaymentPostResult:
    payment: Payment
    journal_entry: JournalEntry
    affected_orders: list  # list[PurchaseOrder | SaleOrder]


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise PaymentPostError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


def _resolve_cash_subaccount(payment: Payment) -> GLSubaccount:
    """Взять явно заданный cash_subaccount или вывести по channel."""
    if payment.cash_subaccount_id:
        return payment.cash_subaccount

    code = CASH_SUBACCOUNT_BY_CHANNEL.get(payment.channel)
    if not code:
        raise PaymentPostError(
            {
                "cash_subaccount": (
                    f"Для канала {payment.get_channel_display()} cash_subaccount "
                    f"не задан по умолчанию — укажите явно."
                )
            }
        )
    return _get_subaccount(payment.organization, code)


def _is_fx(payment: Payment) -> bool:
    return (
        payment.currency_id is not None
        and payment.currency.code.upper() != "UZS"
    )


def _validate_allocations(
    payment: Payment, allocations: list[PaymentAllocation]
) -> None:
    """Проверить что сумма аллокаций совпадает с amount_uzs (если они есть)."""
    if not allocations:
        return

    total = sum((a.amount_uzs for a in allocations), Decimal("0"))
    if total != payment.amount_uzs:
        raise PaymentPostError(
            {
                "allocations": (
                    f"Сумма аллокаций ({total}) не равна сумме платежа "
                    f"({payment.amount_uzs})."
                )
            }
        )

    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    so_ct = ContentType.objects.get_for_model(SaleOrder)
    allowed_ct_ids = {po_ct.id, so_ct.id}

    for alloc in allocations:
        if alloc.target_content_type_id not in allowed_ct_ids:
            raise PaymentPostError(
                {
                    "allocations": (
                        "Поддерживается разнесение только на PurchaseOrder или SaleOrder."
                    )
                }
            )

    # Направление платежа ↔ тип документа
    for alloc in allocations:
        if (
            payment.direction == Payment.Direction.OUT
            and alloc.target_content_type_id == so_ct.id
        ):
            raise PaymentPostError(
                {"allocations": "OUT-платёж нельзя разнести на SaleOrder."}
            )
        if (
            payment.direction == Payment.Direction.IN
            and alloc.target_content_type_id == po_ct.id
        ):
            raise PaymentPostError(
                {"allocations": "IN-платёж нельзя разнести на PurchaseOrder."}
            )


def _recalc_purchase_payment_status(order: PurchaseOrder) -> None:
    """
    Пересчитать paid_amount_uzs и payment_status закупа по всем POSTED
    платежам, аллоцированным на него.
    """
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    total = (
        PaymentAllocation.objects.filter(
            target_content_type=po_ct,
            target_object_id=order.id,
            payment__status=Payment.Status.POSTED,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )

    order.paid_amount_uzs = total
    if total <= 0:
        order.payment_status = PurchaseOrder.PaymentStatus.UNPAID
    elif total < order.amount_uzs:
        order.payment_status = PurchaseOrder.PaymentStatus.PARTIAL
    elif total == order.amount_uzs:
        order.payment_status = PurchaseOrder.PaymentStatus.PAID
    else:
        order.payment_status = PurchaseOrder.PaymentStatus.OVERPAID

    order.save(update_fields=["paid_amount_uzs", "payment_status", "updated_at"])


def _recalc_sale_payment_status(order: SaleOrder) -> None:
    """
    Пересчитать paid_amount_uzs и payment_status продажи по всем POSTED
    IN-платежам, аллоцированным на неё.
    """
    so_ct = ContentType.objects.get_for_model(SaleOrder)
    total = (
        PaymentAllocation.objects.filter(
            target_content_type=so_ct,
            target_object_id=order.id,
            payment__status=Payment.Status.POSTED,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )

    order.paid_amount_uzs = total
    if total <= 0:
        order.payment_status = SaleOrder.PaymentStatus.UNPAID
    elif total < order.amount_uzs:
        order.payment_status = SaleOrder.PaymentStatus.PARTIAL
    elif total == order.amount_uzs:
        order.payment_status = SaleOrder.PaymentStatus.PAID
    else:
        order.payment_status = SaleOrder.PaymentStatus.OVERPAID

    order.save(update_fields=["paid_amount_uzs", "payment_status", "updated_at"])


@transaction.atomic
def post_payment(payment: Payment, *, user=None) -> PaymentPostResult:
    """
    Провести платёж. Повторный вызов на POSTED → ValidationError.
    """
    # 1. Row-lock без select_related (outer-join FOR UPDATE не работает на nullable FK)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    payment = Payment.objects.select_related(
        "organization", "counterparty", "currency", "cash_subaccount__account",
        "exchange_rate_source",
    ).get(pk=payment.pk)

    # 2. Статус
    if payment.status == Payment.Status.POSTED:
        raise PaymentPostError(
            {"status": "Платёж уже проведён."}
        )
    if payment.status == Payment.Status.CANCELLED:
        raise PaymentPostError(
            {"status": "Отменённый платёж нельзя провести."}
        )

    # 3. Аллокации (подтянем заранее для валидации)
    allocations = list(payment.allocations.select_related("target_content_type"))
    _validate_allocations(payment, allocations)

    # 3.1. Guard: нельзя одновременно указывать contra_subaccount и allocations
    # (contra — это "прочая" операция, allocation — это разнесение на PO/SO).
    if payment.contra_subaccount_id and allocations:
        raise PaymentPostError(
            {"contra_subaccount": (
                "Нельзя одновременно разносить платёж на PO/SO и указывать "
                "contra_subaccount. Это разные сценарии."
            )}
        )

    # 4. Cash-субсчёт
    cash_sub = _resolve_cash_subaccount(payment)

    # 5. Встречный субсчёт
    is_fx = _is_fx(payment)
    if payment.contra_subaccount_id:
        # Прочие операции (opex/income/salary): Dr/Cr собираются из явного contra.
        counter_sub = payment.contra_subaccount
    elif payment.direction == Payment.Direction.OUT:
        counter_code = AP_SUBACCOUNT_FX if is_fx else AP_SUBACCOUNT_UZS
        counter_sub = _get_subaccount(payment.organization, counter_code)
    else:  # IN
        counter_code = AR_SUBACCOUNT_FX if is_fx else AR_SUBACCOUNT_UZS
        counter_sub = _get_subaccount(payment.organization, counter_code)

    if payment.direction == Payment.Direction.OUT:
        debit_sub, credit_sub = counter_sub, cash_sub
    else:
        debit_sub, credit_sub = cash_sub, counter_sub

    # 6. doc_number
    if not payment.doc_number:
        payment.doc_number = next_doc_number(
            Payment,
            organization=payment.organization,
            prefix="ПЛ",
            on_date=payment.date,
        )

    # 7. JournalEntry
    je_number = next_doc_number(
        JournalEntry,
        organization=payment.organization,
        prefix="ПР",
        on_date=payment.date,
    )
    # Текстовое описание (с fallback если нет counterparty — например opex).
    if payment.kind == Payment.Kind.COUNTERPARTY:
        title = (
            "Оплата поставщику"
            if payment.direction == Payment.Direction.OUT
            else "Поступление от покупателя"
        )
    else:
        title = payment.get_kind_display()
    who = payment.counterparty.name if payment.counterparty_id else (
        payment.contra_subaccount.name if payment.contra_subaccount_id else "—"
    )
    description_parts = [title, who, f"{payment.amount_uzs} UZS"]
    if is_fx:
        description_parts.append(
            f"({payment.amount_foreign} {payment.currency.code} @ {payment.exchange_rate})"
        )
    description = " · ".join(description_parts)

    je = JournalEntry(
        organization=payment.organization,
        module=payment.module,
        doc_number=je_number,
        entry_date=payment.date,
        description=description,
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=payment.amount_uzs,
        currency=payment.currency if is_fx else None,
        amount_foreign=payment.amount_foreign if is_fx else None,
        exchange_rate=payment.exchange_rate if is_fx else None,
        source_content_type=ContentType.objects.get_for_model(Payment),
        source_object_id=payment.id,
        counterparty=payment.counterparty,
        expense_article=payment.expense_article,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # 8. Финализация платежа
    payment.status = Payment.Status.POSTED
    payment.posted_at = timezone.now()
    payment.cash_subaccount = cash_sub
    payment.journal_entry = je
    payment.save(
        update_fields=[
            "doc_number",
            "status",
            "posted_at",
            "cash_subaccount",
            "journal_entry",
            "updated_at",
        ]
    )

    # 9. Пересчёт payment_status на затронутых PO/SO
    affected_orders: list = []
    if allocations:
        po_ct = ContentType.objects.get_for_model(PurchaseOrder)
        so_ct = ContentType.objects.get_for_model(SaleOrder)

        po_ids = {
            a.target_object_id
            for a in allocations
            if a.target_content_type_id == po_ct.id
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
            for a in allocations
            if a.target_content_type_id == so_ct.id
        }
        for oid in so_ids:
            try:
                sale = SaleOrder.objects.select_for_update().get(pk=oid)
            except SaleOrder.DoesNotExist:
                continue
            _recalc_sale_payment_status(sale)
            affected_orders.append(sale)

    audit_log(
        organization=payment.organization,
        module=payment.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=payment,
        action_verb=f"posted payment {payment.doc_number}",
    )

    return PaymentPostResult(
        payment=payment,
        journal_entry=je,
        affected_orders=affected_orders,
    )


@transaction.atomic
def create_and_post_payment(
    *,
    organization,
    direction: str,
    channel: str,
    counterparty,
    amount_uzs: Decimal,
    date,
    module=None,
    currency=None,
    exchange_rate=None,
    exchange_rate_source=None,
    amount_foreign=None,
    cash_subaccount=None,
    expense_article=None,
    allocations: Optional[Iterable[dict]] = None,
    notes: str = "",
    user=None,
) -> PaymentPostResult:
    """
    High-level хелпер: создать Payment + аллокации и сразу провести.
    Используется, когда нужно «оплатить и провести» одним действием
    (например, из POST-action).

    allocations: iterable of {"target": PurchaseOrder, "amount_uzs": Decimal}.
    """
    # doc_number генерируем заранее (поле NOT NULL/NOT BLANK)
    doc_number = next_doc_number(
        Payment, organization=organization, prefix="ПЛ", on_date=date
    )
    payment = Payment(
        organization=organization,
        module=module,
        doc_number=doc_number,
        date=date,
        direction=direction,
        channel=channel,
        status=Payment.Status.DRAFT,
        counterparty=counterparty,
        currency=currency,
        exchange_rate=exchange_rate,
        exchange_rate_source=exchange_rate_source,
        amount_foreign=amount_foreign,
        amount_uzs=amount_uzs,
        cash_subaccount=cash_subaccount,
        expense_article=expense_article,
        notes=notes,
        created_by=user,
    )
    payment.full_clean()
    payment.save()

    if allocations:
        for alloc in allocations:
            target = alloc["target"]
            target_ct = ContentType.objects.get_for_model(type(target))
            PaymentAllocation.objects.create(
                payment=payment,
                target_content_type=target_ct,
                target_object_id=target.id,
                amount_uzs=alloc["amount_uzs"],
                notes=alloc.get("notes", ""),
            )

    return post_payment(payment, user=user)
