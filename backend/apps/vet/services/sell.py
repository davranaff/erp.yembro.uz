"""
Сервис `sell_vet_stock` — розничная продажа лота препарата с public-сканера.

Atomic-транзакция:
  1. Guards: лот в AVAILABLE, current_quantity >= quantity, не RECALLED/EXPIRED.
  2. Resolve customer (default: «Розница» Counterparty per org).
  3. Создать SaleOrder + SaleItem(vet_stock_batch=лот) status=DRAFT.
  4. Подтвердить через apps/sales.confirm_sale_order
     → JE Дт 62.01 / Кт 90.01 + Дт 90.02 / Кт 10.03 + StockMovement OUTGOING
       + декремент current_quantity лота.
  5. Если current_quantity = 0 → DEPLETED.
  6. AuditLog с seller_user.

Используется на public endpoint /api/vet/public/sell/.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale

from ..models import VetStockBatch


RETAIL_COUNTERPARTY_CODE = "RETAIL"
RETAIL_COUNTERPARTY_NAME = "Розничный покупатель"


class VetSellError(ValidationError):
    pass


@dataclass
class VetSellResult:
    sale_order: SaleOrder
    stock_batch: VetStockBatch
    total_uzs: Decimal
    remaining_qty: Decimal


def _resolve_or_create_retail_customer(organization) -> Counterparty:
    """Возвращает Counterparty «Розница» для org, создаёт если нет."""
    customer, _ = Counterparty.objects.get_or_create(
        organization=organization,
        code=RETAIL_COUNTERPARTY_CODE,
        defaults={
            "name": RETAIL_COUNTERPARTY_NAME,
            "kind": Counterparty.Kind.BUYER,
            "is_active": True,
        },
    )
    return customer


@transaction.atomic
def sell_vet_stock(
    *,
    stock_batch: VetStockBatch,
    quantity: Decimal,
    seller_user,
    organization,
    customer: Counterparty | None = None,
    unit_price_uzs: Decimal | None = None,
) -> VetSellResult:
    # 1. Lock + validate
    stock_batch = VetStockBatch.objects.select_for_update().select_related(
        "drug__nomenclature", "warehouse", "unit",
    ).get(pk=stock_batch.pk)

    if stock_batch.organization_id != organization.id:
        raise VetSellError({"__all__": "Лот из другой организации."})

    if stock_batch.status != VetStockBatch.Status.AVAILABLE:
        raise VetSellError(
            {"stock_batch": (
                f"Лот {stock_batch.doc_number} в статусе "
                f"{stock_batch.get_status_display()} — недоступен для продажи."
            )}
        )

    if stock_batch.is_expired:
        raise VetSellError(
            {"stock_batch": "Лот истёк, продажа запрещена."}
        )

    qty = Decimal(str(quantity))
    if qty <= 0:
        raise VetSellError({"quantity": "Количество должно быть > 0."})
    if qty > stock_batch.current_quantity:
        raise VetSellError(
            {"quantity": (
                f"Доступно только {stock_batch.current_quantity} "
                f"{stock_batch.unit.code}."
            )}
        )

    # 2. Customer
    if customer is None:
        customer = _resolve_or_create_retail_customer(organization)
    elif customer.organization_id != organization.id:
        raise VetSellError({"customer": "Покупатель из другой организации."})

    # 3. Цена
    if unit_price_uzs is None:
        unit_price_uzs = stock_batch.price_per_unit_uzs
    else:
        unit_price_uzs = Decimal(str(unit_price_uzs))
    if unit_price_uzs <= 0:
        raise VetSellError({"unit_price_uzs": "Цена должна быть > 0."})

    # 4. SaleOrder
    today = date.today()
    doc_number = next_doc_number(
        SaleOrder, organization=organization, prefix="ПР", on_date=today,
    )
    order = SaleOrder.objects.create(
        organization=organization,
        module=stock_batch.module,
        doc_number=doc_number,
        date=today,
        customer=customer,
        warehouse=stock_batch.warehouse,
        status=SaleOrder.Status.DRAFT,
        notes=(
            f"Розничная продажа лот {stock_batch.doc_number} "
            f"(barcode {stock_batch.barcode or '—'}) · продавец {seller_user}"
        ),
        created_by=seller_user,
    )
    SaleItem.objects.create(
        order=order,
        nomenclature=stock_batch.drug.nomenclature,
        vet_stock_batch=stock_batch,
        quantity=qty,
        unit_price_uzs=unit_price_uzs,
    )

    # 5. Confirm — это создаст JE/StockMovement и декрементирует current_quantity
    try:
        confirm_sale(order, user=seller_user)
    except Exception as exc:
        raise VetSellError({"__all__": f"Ошибка проведения продажи: {exc}"})

    order.refresh_from_db()
    stock_batch.refresh_from_db()

    # 6. Если лот опустошён → DEPLETED
    if stock_batch.current_quantity <= 0:
        stock_batch.status = VetStockBatch.Status.DEPLETED
        stock_batch.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=organization,
        module=stock_batch.module,
        actor=seller_user,
        action=AuditLog.Action.POST,
        entity=order,
        action_verb=(
            f"vet retail sale {order.doc_number} · "
            f"{stock_batch.drug.nomenclature.sku} × {qty} · "
            f"by seller {seller_user}"
        ),
    )

    return VetSellResult(
        sale_order=order,
        stock_batch=stock_batch,
        total_uzs=order.amount_uzs,
        remaining_qty=stock_batch.current_quantity,
    )
