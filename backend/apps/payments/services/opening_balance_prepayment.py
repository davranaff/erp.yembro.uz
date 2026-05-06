"""
Сервис синтетического Payment'а для миграции стартовой ПРЕДОПЛАТЫ.

Контекст: на Counterparty есть `opening_debt_uzs` со знаком:
    + → клиент должен нам / мы должны поставщику    (материализуется как SO/PO)
    − → клиент уже занёс / мы уже заплатили авансом (этот сервис)

Для отрицательного opening_debt создаём Payment с kind=
OPENING_BALANCE_PREPAYMENT, без allocations, со статусом POSTED.
Никаких журнальных проводок (post_payment этот kind пропускает) — это
исторический факт переноса, а не cash-движение.

После создания Payment живёт в системе как «свободный кредит» для
данного контрагента. Когда у этого клиента появится новая продажа,
кассир может применить часть (или всю) этой предоплаты через
PaymentAllocation → paid_amount_uzs новой SO/PO обновится автоматом
через _recalc_*_payment_status.

Направление:
    kind=buyer    + opening_debt < 0 → Payment(direction=IN)  — клиент занёс нам
    kind=supplier + opening_debt < 0 → Payment(direction=OUT) — мы занесли поставщику
"""
from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty

from ..models import Payment


@transaction.atomic
def create_opening_balance_prepayment(
    *,
    organization,
    counterparty: Counterparty,
    amount_uzs: Decimal,
    date_: date_cls,
    user=None,
) -> Payment:
    """Создать синтетический Payment для миграции стартовой предоплаты.

    amount_uzs — положительное число (модуль предоплаты).
    Направление вычисляется по kind контрагента.
    """
    if amount_uzs <= 0:
        raise ValueError("prepayment amount должен быть > 0")

    if counterparty.kind == Counterparty.Kind.BUYER:
        direction = Payment.Direction.IN
    elif counterparty.kind == Counterparty.Kind.SUPPLIER:
        direction = Payment.Direction.OUT
    else:
        raise ValueError(
            "opening_balance_prepayment поддерживается только для "
            "kind=buyer/supplier."
        )

    if counterparty.organization_id != organization.id:
        raise ValueError("Контрагент из другой организации.")

    doc_number = next_doc_number(
        Payment, organization=organization, prefix="ОБП", on_date=date_,
    )
    # channel формальный — т.к. JE не создаём, выбор канала ни на что не
    # влияет, но поле обязательное в модели. CASH самый нейтральный.
    payment = Payment.objects.create(
        organization=organization,
        module=None,
        doc_number=doc_number,
        date=date_,
        direction=direction,
        channel=Payment.Channel.OTHER,
        kind=Payment.Kind.OPENING_BALANCE_PREPAYMENT,
        status=Payment.Status.DRAFT,  # post_payment ниже переведёт в POSTED
        counterparty=counterparty,
        amount_uzs=amount_uzs,
        notes=(
            "Перенесённая предоплата из предыдущей системы (миграция). "
            "Применяется к будущим документам через allocations."
        ),
        created_by=user,
    )
    # Сразу проводим — kind=OPENING_BALANCE_PREPAYMENT в post_payment
    # пропускает JE/cash и переводит в POSTED.
    from .post import post_payment

    post_payment(payment, user=user)
    payment.refresh_from_db()
    return payment


def get_opening_balance_prepayment(
    counterparty: Counterparty,
) -> Optional[Payment]:
    """Вернуть существующий OPENING_BALANCE_PREPAYMENT Payment контрагента."""
    return (
        Payment.objects.filter(
            organization_id=counterparty.organization_id,
            counterparty=counterparty,
            kind=Payment.Kind.OPENING_BALANCE_PREPAYMENT,
        )
        .order_by("-created_at")
        .first()
    )


def _allocated_amount(payment: Payment) -> Decimal:
    from django.db.models import Sum

    total = payment.allocations.aggregate(s=Sum("amount_uzs"))["s"]
    return total or Decimal("0")


@transaction.atomic
def sync_opening_balance_prepayment_for_counterparty(
    counterparty: Counterparty,
) -> Optional[Payment]:
    """Привести синтетический Payment в соответствие с opening_debt_uzs < 0.

    Идемпотентен:
        - opening < 0 + Payment'а нет     → создать
        - opening < 0 + есть, без allocations + amount другой → обновить amount
        - opening < 0 + есть, частично allocated → no-op (защита аудита)
        - opening ≥ 0 + есть unallocated  → отменить (CANCELLED)
        - opening ≥ 0 + есть allocated    → no-op
    """
    if counterparty.kind not in (
        Counterparty.Kind.BUYER, Counterparty.Kind.SUPPLIER,
    ):
        return None

    raw = Decimal(counterparty.opening_debt_uzs or 0)
    # Препэймент только для отрицательных значений.
    prepay_amount = -raw if raw < 0 else Decimal("0")
    existing = get_opening_balance_prepayment(counterparty)

    if prepay_amount == 0:
        # Кредит «обнулили» — отменяем синтетический Payment если он
        # ещё не был частично использован.
        if existing and existing.status == Payment.Status.POSTED:
            if _allocated_amount(existing) == 0:
                existing.status = Payment.Status.CANCELLED
                existing.save(update_fields=["status", "updated_at"])
        return existing

    if existing is None:
        return create_opening_balance_prepayment(
            organization=counterparty.organization,
            counterparty=counterparty,
            amount_uzs=prepay_amount,
            date_=counterparty.opening_balance_date or date_cls.today(),
        )

    # Payment есть. Если уже частично применили — не трогаем сумму.
    if _allocated_amount(existing) > 0:
        return existing

    # Чистый Payment без аллокаций — можно обновить amount/date.
    update_fields = []
    if Decimal(existing.amount_uzs) != prepay_amount:
        existing.amount_uzs = prepay_amount
        update_fields.append("amount_uzs")
    if (
        counterparty.opening_balance_date
        and existing.date != counterparty.opening_balance_date
    ):
        existing.date = counterparty.opening_balance_date
        update_fields.append("date")
    if existing.status == Payment.Status.CANCELLED:
        existing.status = Payment.Status.POSTED
        update_fields.append("status")
    if update_fields:
        update_fields.append("updated_at")
        existing.save(update_fields=update_fields)
    return existing
