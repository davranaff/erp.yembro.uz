"""
Сервис `receive_vet_accessory` — приёмка партии аксессуара
(новая поставка миски/поилки/переноски и т.п.).

Atomic-транзакция:
    1. Guards: org match, qty > 0, accessory.is_active.
    2. Weighted-avg recompute себестоимости:
        new_avg = (old_qty * old_cost + new_qty * new_cost)
                  / (old_qty + new_qty)
       Если `unit_cost_uzs` не передана — оставляем текущий cost,
       просто инкрементим количество (например довоз по той же цене).
    3. current_quantity += quantity.
    4. StockMovement INCOMING на склад accessory.
    5. AuditLog.

Без отдельного PurchaseOrder (в отличие от препаратов) — товары
для перепродажи проще и упрощённый комплаенс.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import VetAccessory


class VetAccessoryReceiveError(ValidationError):
    pass


@dataclass
class VetAccessoryReceiveResult:
    accessory: VetAccessory
    stock_movement: StockMovement
    previous_cost_uzs: Decimal
    new_cost_uzs: Decimal


def _q_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q_qty(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def receive_vet_accessory(
    accessory: VetAccessory,
    *,
    quantity: Decimal,
    unit_cost_uzs: Optional[Decimal] = None,
    user=None,
    notes: str = "",
) -> VetAccessoryReceiveResult:
    """Принять `quantity` штук аксессуара. Опционально пересчитать avg-cost.

    Если `unit_cost_uzs` не задан — себестоимость не меняется (довоз).
    Если задан и текущий остаток 0 — сразу `cost = unit_cost_uzs` (нет
    смысла усреднять с нулём).
    """
    if quantity is None or quantity <= 0:
        raise VetAccessoryReceiveError(
            {"quantity": "Количество должно быть больше нуля."}
        )

    # Один запрос с FOR UPDATE + select_related. Раньше второй .get()
    # без select_for_update терял row-lock; два параллельных receive на
    # один аксессуар читали одинаковый old_qty/old_cost и WAC получался
    # неверным.
    #
    # of=("self",) обязателен: select_for_update + select_related на
    # nullable FK (например warehouse → default_gl_subaccount) падает на
    # PostgreSQL outer-join. Блокируем только саму строку VetAccessory.
    accessory = (
        VetAccessory.objects
        .select_for_update(of=("self",))
        .select_related(
            "organization", "module", "warehouse",
            "nomenclature", "nomenclature__unit",
        )
        .get(pk=accessory.pk)
    )

    if not accessory.is_active:
        raise VetAccessoryReceiveError(
            {"__all__": "Аксессуар отключён, приёмка невозможна."}
        )

    org = accessory.organization
    qty = Decimal(quantity)
    old_qty = Decimal(accessory.current_quantity or 0)
    old_cost = Decimal(accessory.cost_per_unit_uzs or 0)

    # Weighted-average себестоимости
    if unit_cost_uzs is None:
        new_cost = old_cost
        movement_unit_price = old_cost
    else:
        new_unit_cost = Decimal(unit_cost_uzs)
        if new_unit_cost < 0:
            raise VetAccessoryReceiveError(
                {"unit_cost_uzs": "Себестоимость не может быть отрицательной."}
            )
        if old_qty <= 0:
            new_cost = _q_money(new_unit_cost)
        else:
            blended = (old_qty * old_cost + qty * new_unit_cost) / (old_qty + qty)
            new_cost = _q_money(blended)
        movement_unit_price = _q_money(new_unit_cost)

    # StockMovement INCOMING — для audit-trail и отчёта по складу
    sm_qty = _q_qty(qty)
    amount = _q_money(movement_unit_price * sm_qty)
    sm_number = next_doc_number(
        StockMovement, organization=org, prefix="СД",
    )
    ct = ContentType.objects.get_for_model(VetAccessory)
    sm = StockMovement(
        organization=org,
        module=accessory.module,
        doc_number=sm_number,
        kind=StockMovement.Kind.INCOMING,
        date=timezone.now(),
        nomenclature=accessory.nomenclature,
        quantity=sm_qty,
        unit_price_uzs=movement_unit_price,
        amount_uzs=amount,
        warehouse_from=None,
        warehouse_to=accessory.warehouse,
        source_content_type=ct,
        source_object_id=accessory.id,
        created_by=user,
    )
    sm.full_clean(exclude=None)
    sm.save()

    # Обновляем запись аксессуара
    VetAccessory.objects.filter(pk=accessory.pk).update(
        current_quantity=F("current_quantity") + qty,
        cost_per_unit_uzs=new_cost,
    )
    accessory.refresh_from_db(fields=["current_quantity", "cost_per_unit_uzs"])

    audit_log(
        organization=org,
        module=accessory.module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=accessory,
        action_verb=(
            f"received {qty} of {accessory.nomenclature.sku} · "
            f"cost {old_cost} → {new_cost}"
            + (f" · {notes}" if notes else "")
        ),
    )

    return VetAccessoryReceiveResult(
        accessory=accessory,
        stock_movement=sm,
        previous_cost_uzs=old_cost,
        new_cost_uzs=new_cost,
    )
