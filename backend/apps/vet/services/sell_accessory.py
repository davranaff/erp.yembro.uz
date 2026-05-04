"""
Сервис `sell_vet_accessory` — розничная продажа аксессуара (миска,
поилка и т.п.) с public-сканера.

Делает ровно то же что `sell_vet_stock` для препарата:
  1. Guards: accessory.is_active, current_quantity >= qty.
  2. Resolve customer (default: «Розница» Counterparty per org).
  3. SaleOrder + SaleItem(vet_accessory=acc) status=DRAFT.
  4. confirm_sale → JE Дт 62.01 / Кт 90.01 + Дт 90.02 / Кт 41.01 + SM OUTGOING.
  5. AuditLog.

В отличие от препарата:
    - нет проверок expired/recalled (у аксессуаров нет срока годности)
    - нет статус-машины (просто остаток)
    - GL credit идёт на 41.01 (см. `_resolve_inventory_subaccount` в confirm_sale)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale

from ..models import VetAccessory
from .sell import _resolve_or_create_retail_customer


class VetAccessorySellError(ValidationError):
    pass


@dataclass
class VetAccessorySellResult:
    sale_order: SaleOrder
    accessory: VetAccessory
    total_uzs: Decimal
    remaining_qty: Decimal


@transaction.atomic
def sell_vet_accessory(
    *,
    accessory: VetAccessory,
    quantity: Decimal,
    seller_user,
    organization,
    customer: Counterparty | None = None,
    unit_price_uzs: Decimal | None = None,
) -> VetAccessorySellResult:
    accessory = VetAccessory.objects.select_for_update().select_related(
        "module", "warehouse", "nomenclature",
    ).get(pk=accessory.pk)

    if accessory.organization_id != organization.id:
        raise VetAccessorySellError({"__all__": "Аксессуар из другой организации."})
    if not accessory.is_active:
        raise VetAccessorySellError(
            {"accessory": (
                f"Аксессуар {accessory.nomenclature.sku} отключён — продажа невозможна."
            )}
        )

    qty = Decimal(str(quantity))
    if qty <= 0:
        raise VetAccessorySellError({"quantity": "Количество должно быть > 0."})
    if qty > accessory.current_quantity:
        raise VetAccessorySellError(
            {"quantity": (
                f"Доступно только {accessory.current_quantity} штук."
            )}
        )

    if customer is None:
        customer = _resolve_or_create_retail_customer(organization)
    elif customer.organization_id != organization.id:
        raise VetAccessorySellError({"customer": "Покупатель из другой организации."})

    if unit_price_uzs is None:
        unit_price_uzs = accessory.sale_price_uzs
    else:
        unit_price_uzs = Decimal(str(unit_price_uzs))
    if unit_price_uzs <= 0:
        raise VetAccessorySellError({"unit_price_uzs": "Цена должна быть > 0."})

    today = date.today()
    doc_number = next_doc_number(
        SaleOrder, organization=organization, prefix="ПР", on_date=today,
    )
    order = SaleOrder.objects.create(
        organization=organization,
        module=accessory.module,
        doc_number=doc_number,
        date=today,
        customer=customer,
        warehouse=accessory.warehouse,
        status=SaleOrder.Status.DRAFT,
        notes=(
            f"Розничная продажа аксессуара {accessory.nomenclature.sku} "
            f"(barcode {accessory.barcode or '—'}) · продавец {seller_user}"
        ),
        created_by=seller_user,
    )
    SaleItem.objects.create(
        order=order,
        nomenclature=accessory.nomenclature,
        vet_accessory=accessory,
        quantity=qty,
        unit_price_uzs=unit_price_uzs,
    )

    try:
        confirm_sale(order, user=seller_user)
    except Exception as exc:
        raise VetAccessorySellError({"__all__": f"Ошибка проведения продажи: {exc}"})

    order.refresh_from_db()
    accessory.refresh_from_db()

    audit_log(
        organization=organization,
        module=accessory.module,
        actor=seller_user,
        action=AuditLog.Action.POST,
        entity=order,
        action_verb=(
            f"vet accessory retail sale {order.doc_number} · "
            f"{accessory.nomenclature.sku} × {qty}"
        ),
    )

    return VetAccessorySellResult(
        sale_order=order,
        accessory=accessory,
        total_uzs=order.amount_uzs,
        remaining_qty=accessory.current_quantity,
    )
