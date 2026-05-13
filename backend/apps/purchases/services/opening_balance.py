"""
Симметричный аналог `apps/sales/services/opening_balance.py`, но для
поставщиков: `kind=supplier` + `opening_debt_uzs > 0` означает «мы
должны поставщику X на дату Y». Материализуем как синтетический
PurchaseOrder (kind=OPENING_BALANCE).

После этого долг живёт через стандартный AP-пайплайн:
    - касса проводит исходящий Payment с allocations=[{target: PO}]
    - /api/counterparties/balances/ показывает в ap_uzs
    - debt-уведомления, отчёты — всё через PurchaseOrder

См. apps/sales/services/opening_balance.py для архитектурных мотивов.
"""
from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty

from ..models import PurchaseOrder


@transaction.atomic
def create_opening_balance_purchase(
    *,
    organization,
    counterparty: Counterparty,
    amount_uzs: Decimal,
    date_: date_cls,
) -> PurchaseOrder:
    """Создать синтетический PurchaseOrder для стартового долга поставщику."""
    if amount_uzs <= 0:
        raise ValueError("opening balance amount должен быть > 0")
    if counterparty.kind != Counterparty.Kind.SUPPLIER:
        raise ValueError(
            "opening_balance PurchaseOrder поддерживается только для "
            "kind=supplier; для покупателей нужен SaleOrder."
        )
    if counterparty.organization_id != organization.id:
        raise ValueError("Контрагент из другой организации.")

    doc_number = next_doc_number(
        PurchaseOrder, organization=organization,
        prefix="OPN-AP", on_date=date_,
    )
    return PurchaseOrder.objects.create(
        organization=organization,
        counterparty=counterparty,
        kind=PurchaseOrder.Kind.OPENING_BALANCE,
        status=PurchaseOrder.Status.CONFIRMED,
        payment_status=PurchaseOrder.PaymentStatus.UNPAID,
        doc_number=doc_number,
        date=date_,
        amount_uzs=amount_uzs,
        paid_amount_uzs=Decimal("0"),
        module=None,
        warehouse=None,
        notes="Перенесённый долг поставщику из предыдущей системы (миграция).",
    )


def get_opening_balance_purchase(
    counterparty: Counterparty,
) -> Optional[PurchaseOrder]:
    return (
        PurchaseOrder.objects.filter(
            organization_id=counterparty.organization_id,
            counterparty=counterparty,
            kind=PurchaseOrder.Kind.OPENING_BALANCE,
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def sync_opening_balance_for_supplier(
    counterparty: Counterparty,
) -> Optional[PurchaseOrder]:
    """Привести синтетический PO в соответствие с opening_debt_uzs поставщика.

    Идемпотентен:
        - opening_debt_uzs > 0 + PO нет        → создать
        - opening_debt_uzs > 0 + PO есть unpaid → обновить amount/date
        - opening_debt_uzs > 0 + PO частично оплачен → no-op
        - opening_debt_uzs ≤ 0 + PO unpaid     → отменить (CANCELLED)

    Поддерживается только kind=supplier и положительное значение
    (отрицательное → переплата, материализуется как unallocated Payment).
    """
    if counterparty.kind != Counterparty.Kind.SUPPLIER:
        return None

    opening = Decimal(counterparty.opening_debt_uzs or 0)
    existing = get_opening_balance_purchase(counterparty)

    # opening_debt = 0: оставляем существующий PO как есть. После материализации
    # миграционного счёта поле opening_debt_uzs становится историческим
    # snapshot'ом — обнулять его безопасно, но это НЕ должно авто-отменять
    # реальный счёт поставщику. Отмену делает админ явно через UI.
    if opening <= 0:
        return existing

    if existing is None:
        return create_opening_balance_purchase(
            organization=counterparty.organization,
            counterparty=counterparty,
            amount_uzs=opening,
            date_=counterparty.opening_balance_date or date_cls.today(),
        )

    paid = Decimal(existing.paid_amount_uzs or 0)
    if paid > 0:
        return existing

    update_fields = []
    if Decimal(existing.amount_uzs) != opening:
        existing.amount_uzs = opening
        update_fields.append("amount_uzs")
    if (
        counterparty.opening_balance_date
        and existing.date != counterparty.opening_balance_date
    ):
        existing.date = counterparty.opening_balance_date
        update_fields.append("date")
    if existing.status == PurchaseOrder.Status.CANCELLED:
        existing.status = PurchaseOrder.Status.CONFIRMED
        update_fields.append("status")
    if update_fields:
        update_fields.append("updated_at")
        existing.save(update_fields=update_fields)
    return existing
