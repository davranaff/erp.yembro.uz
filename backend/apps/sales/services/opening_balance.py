"""
Сервис синтетического SaleOrder для миграции стартового долга.

Контекст: на Counterparty есть поле `opening_debt_uzs` — долг, перенесённый
из другой ERP. До этого сервиса он жил параллельно стандартному пайплайну —
прибавлялся в aging, в credit_check, имел отдельные TG-уведомления. Это
давало 4 точки рассинхронизации (касса не видела долг, /tasks молчал,
любая правка кода aging/credit могла его потерять).

После рефакторинга `opening_debt` материализуется в полноценный SaleOrder
(`kind=OPENING_BALANCE`):
    - status = CONFIRMED, payment_status = UNPAID
    - amount_uzs = opening_debt
    - date = opening_balance_date (дата миграции)
    - due_date = date (просрочка считается с даты миграции)
    - module/warehouse = NULL — синтетика без отгрузки
    - без SaleItem'ов и стоковых движений
    - без журнальных проводок (открытое сальдо не транзакция)

Дальше всё работает само: касса принимает оплату через `record_payment`
как на любой другой SO, /tasks показывает просрочку, aging бакетирует.

Идемпотентность: на одного контрагента в одной orgе создаём не больше
одного OPENING_BALANCE SO. Повторный вызов либо обновит amount (если SO
ещё не оплачивался), либо отдаст существующий.
"""
from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty

from ..models import SaleOrder


@transaction.atomic
def create_opening_balance_sale(
    *,
    organization,
    customer: Counterparty,
    amount_uzs: Decimal,
    date_: date_cls,
) -> SaleOrder:
    """Создать новый синтетический SaleOrder для стартового долга.

    Не вызывает confirm_sale (там стоковые движения и журналы); создаём
    сразу со статусом CONFIRMED.
    """
    if amount_uzs <= 0:
        raise ValueError("opening balance amount должен быть > 0")
    if customer.kind != Counterparty.Kind.BUYER:
        raise ValueError(
            "opening_balance SaleOrder поддерживается только для kind=buyer; "
            "для поставщиков нужен PurchaseOrder."
        )
    if customer.organization_id != organization.id:
        raise ValueError("Клиент из другой организации.")

    doc_number = next_doc_number(
        SaleOrder, organization=organization, prefix="OPN", on_date=date_
    )
    return SaleOrder.objects.create(
        organization=organization,
        customer=customer,
        kind=SaleOrder.Kind.OPENING_BALANCE,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.UNPAID,
        doc_number=doc_number,
        date=date_,
        due_date=date_,
        amount_uzs=amount_uzs,
        cost_uzs=Decimal("0"),
        paid_amount_uzs=Decimal("0"),
        module=None,
        warehouse=None,
        notes="Перенесённый долг из предыдущей системы (миграция).",
    )


def get_opening_balance_sale(
    counterparty: Counterparty,
) -> Optional[SaleOrder]:
    """Вернуть существующий OPENING_BALANCE SO клиента (если есть).

    Если по какой-то причине их несколько — берём самый свежий по created_at.
    """
    return (
        SaleOrder.objects.filter(
            organization_id=counterparty.organization_id,
            customer=counterparty,
            kind=SaleOrder.Kind.OPENING_BALANCE,
        )
        .order_by("-created_at")
        .first()
    )


@transaction.atomic
def sync_opening_balance_for_counterparty(
    counterparty: Counterparty,
) -> Optional[SaleOrder]:
    """Привести синтетический SO в соответствие с opening_debt_uzs клиента.

    Дёргается из CounterpartyViewSet после save. Идемпотентен:
        - opening_debt_uzs > 0 + SO нет        → создать
        - opening_debt_uzs > 0 + SO есть       → обновить amount/date
                                                 (только если ничего не оплачено)
        - opening_debt_uzs ≤ 0 + SO есть unpaid → отменить (status=CANCELLED)
        - opening_debt_uzs ≤ 0 + SO нет        → no-op

    Поддерживается только для kind=buyer и положительного opening_debt
    (отрицательное → предоплата, нужен синтетический Payment, отдельная ветка).
    """
    if counterparty.kind != Counterparty.Kind.BUYER:
        return None

    opening = Decimal(counterparty.opening_debt_uzs or 0)
    existing = get_opening_balance_sale(counterparty)

    # Долг убрали (или предоплата): отменяем неоплаченный SO, частично
    # оплаченный не трогаем (оплаты уже зафиксированы — пусть остаётся
    # как есть; админ разберётся вручную).
    if opening <= 0:
        if existing and existing.status == SaleOrder.Status.CONFIRMED:
            paid = Decimal(existing.paid_amount_uzs or 0)
            if paid == 0:
                existing.status = SaleOrder.Status.CANCELLED
                existing.save(update_fields=["status", "updated_at"])
        return existing

    # Долг положительный.
    if existing is None:
        return create_opening_balance_sale(
            organization=counterparty.organization,
            customer=counterparty,
            amount_uzs=opening,
            date_=counterparty.opening_balance_date or date_cls.today(),
        )

    # SO уже есть. Если по нему уже что-то оплатили — нельзя менять
    # amount/date задним числом (это сломает aging и аудит платежей).
    paid = Decimal(existing.paid_amount_uzs or 0)
    if paid > 0:
        return existing

    # Чистый unpaid SO — обновляем amount и (опционально) date.
    update_fields = []
    if Decimal(existing.amount_uzs) != opening:
        existing.amount_uzs = opening
        update_fields.append("amount_uzs")
    if counterparty.opening_balance_date and existing.date != counterparty.opening_balance_date:
        existing.date = counterparty.opening_balance_date
        existing.due_date = counterparty.opening_balance_date
        update_fields.extend(["date", "due_date"])
    # Если SO был отменён, а долг снова появился — реактивируем.
    if existing.status == SaleOrder.Status.CANCELLED:
        existing.status = SaleOrder.Status.CONFIRMED
        update_fields.append("status")
    if update_fields:
        update_fields.append("updated_at")
        existing.save(update_fields=update_fields)
    return existing
