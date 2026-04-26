"""
Ручное создание StockMovement.

Обычные движения создаются как побочный эффект бизнес-сервисов
(`confirm_purchase`, `accept_transfer` и т.п.) — у них есть `source_content_type`,
по которому видно происхождение.

Здесь создаётся «голое» движение без source — для случаев когда
кладовщик правит остаток вручную (исправление инвентаризации,
ручное списание брака, прямой приход без закупа и т.п.).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services.numbering import next_doc_number

from ..models import StockMovement


class StockMovementCreateError(ValidationError):
    pass


def _q_money(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q_qty(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@dataclass
class StockMovementCreateResult:
    movement: StockMovement


@transaction.atomic
def create_manual_movement(
    *,
    organization,
    module,
    kind: str,
    nomenclature,
    quantity,
    unit_price_uzs,
    warehouse_from=None,
    warehouse_to=None,
    counterparty=None,
    batch=None,
    date_value=None,
    user=None,
) -> StockMovementCreateResult:
    """
    Создать движение по складу вручную (без привязки к закупу/продаже).

    Проверки:
        - kind ∈ Kind
        - INCOMING требует warehouse_to
        - OUTGOING требует warehouse_from
        - WRITE_OFF требует warehouse_from
        - TRANSFER требует оба
        - quantity > 0, unit_price_uzs >= 0
        - все связанные сущности из этой же organization

    Возвращает:
        StockMovementCreateResult(movement=...)

    Документ-номер генерируется автоматически (СД-YYYY-NNNNN).
    """
    if kind not in StockMovement.Kind.values:
        raise StockMovementCreateError(
            {"kind": f"Неизвестный тип движения: {kind}."}
        )

    qty = _q_qty(quantity)
    price = _q_money(unit_price_uzs)
    if qty <= 0:
        raise StockMovementCreateError(
            {"quantity": "Количество должно быть > 0."}
        )
    if price < 0:
        raise StockMovementCreateError(
            {"unit_price_uzs": "Цена не может быть отрицательной."}
        )

    if module.organization_id and module.organization_id != organization.id:
        raise StockMovementCreateError(
            {"module": "Модуль из другой организации."}
        )

    for wh in (warehouse_from, warehouse_to):
        if wh is not None and wh.organization_id != organization.id:
            raise StockMovementCreateError(
                {"warehouse": "Склад из другой организации."}
            )

    if counterparty is not None and counterparty.organization_id != organization.id:
        raise StockMovementCreateError(
            {"counterparty": "Контрагент из другой организации."}
        )

    if batch is not None and batch.organization_id != organization.id:
        raise StockMovementCreateError(
            {"batch": "Партия из другой организации."}
        )

    when = date_value or timezone.now()

    doc_number = next_doc_number(
        StockMovement,
        organization=organization,
        prefix="СД",
        on_date=when.date() if hasattr(when, "date") else when,
    )

    movement = StockMovement(
        organization=organization,
        module=module,
        doc_number=doc_number,
        kind=kind,
        date=when,
        nomenclature=nomenclature,
        quantity=qty,
        unit_price_uzs=price,
        amount_uzs=_q_money(qty * price),
        warehouse_from=warehouse_from,
        warehouse_to=warehouse_to,
        counterparty=counterparty,
        batch=batch,
        created_by=user,
    )
    movement.full_clean(exclude=None)
    movement.save()
    return StockMovementCreateResult(movement=movement)


def is_manual_movement(movement: StockMovement) -> bool:
    """
    Определяет, было ли движение создано вручную (а не сервисом-источником
    типа confirm_purchase). Только manual движения можно удалять напрямую.
    """
    return movement.source_content_type_id is None and movement.source_object_id is None


@transaction.atomic
def delete_manual_movement(movement: StockMovement, *, user=None) -> None:
    """
    Удалить вручную созданное движение. Движения, порождённые сервисами,
    удалять нельзя — для их отмены нужны соответствующие reverse-сервисы
    (reverse_purchase, reverse_sale и т.д.).
    """
    if not is_manual_movement(movement):
        raise StockMovementCreateError(
            {
                "__all__": (
                    "Это движение создано автоматически по документу-источнику. "
                    "Удаление возможно только через сторно исходного документа."
                )
            }
        )
    movement.delete()
