"""
Сервис `sell_feed_bag_lot` — розничная продажа фасованного корма с
public-сканера.

Симметричен `apps/vet/services/sell.py`. Используется на public endpoint
`POST /api/vet/public/sell/` когда штрих-код принадлежит FeedBagLot.

Atomic-транзакция:
  1. Guards: лот в ACTIVE, bags_remaining ≥ qty, не RECALLED.
  2. Resolve customer (default: «Розница» Counterparty per org).
  3. Создать SaleOrder + SaleItem(feed_bag_lot=лот) status=DRAFT.
  4. Подтвердить через apps/sales.confirm_sale
     → JE Дт 62.01 / Кт 90.01 + Дт 90.02 / Кт 43.01 + StockMovement OUTGOING
       + декремент bags_remaining лота (через сервис confirm_sale).
  5. Если bags_remaining == 0 → DEPLETED.
  6. AuditLog с seller_user.

Цена обязательная: у FeedBagLot нет дефолтной отпускной цены (только cost),
поэтому seller всегда передаёт unit_price_uzs. Без неё поднимаем
ValidationError с понятным сообщением.
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
from apps.nomenclature.models import NomenclatureItem
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale

from ..models import FeedBagLot


RETAIL_COUNTERPARTY_CODE = "RETAIL"
RETAIL_COUNTERPARTY_NAME = "Розничный покупатель"


class FeedBagSellError(ValidationError):
    pass


@dataclass
class FeedBagSellResult:
    sale_order: SaleOrder
    bag_lot: FeedBagLot
    total_uzs: Decimal
    remaining_bags: int


def _resolve_or_create_retail_customer(organization) -> Counterparty:
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


def _resolve_nomenclature(bag_lot: FeedBagLot) -> NomenclatureItem | None:
    """Резолвим NomenclatureItem по recipe.code (тот же паттерн что в
    FeedBagLotSerializer._resolve_nomenclature). Если рецепт не зарегистрирован
    как номенклатурная позиция — продажа невозможна (нечего класть в SaleItem).
    """
    if not bag_lot.recipe_version_id:
        return None
    return NomenclatureItem.objects.filter(
        organization_id=bag_lot.organization_id,
        sku=bag_lot.recipe_version.recipe.code,
    ).first()


@transaction.atomic
def sell_feed_bag_lot(
    *,
    bag_lot: FeedBagLot,
    quantity: Decimal,
    seller_user,
    organization,
    customer: Counterparty | None = None,
    unit_price_uzs: Decimal | None = None,
) -> FeedBagSellResult:
    bag_lot = FeedBagLot.objects.select_for_update().select_related(
        "recipe_version__recipe", "storage_warehouse", "module",
    ).get(pk=bag_lot.pk)

    if bag_lot.organization_id != organization.id:
        raise FeedBagSellError({"__all__": "Партия из другой организации."})

    if bag_lot.status != FeedBagLot.Status.ACTIVE:
        raise FeedBagSellError(
            {"bag_lot": (
                f"Партия {bag_lot.doc_number} в статусе "
                f"{bag_lot.get_status_display()} — недоступна для продажи."
            )}
        )

    # Quantity — целое число мешков.
    qty = Decimal(str(quantity))
    if qty <= 0:
        raise FeedBagSellError({"quantity": "Количество мешков должно быть > 0."})
    # Учёт в шт — quantity целое, но Decimal допустим (из API приходит строкой).
    if qty % 1 != 0:
        raise FeedBagSellError(
            {"quantity": "Мешки продаются целым числом штук."}
        )
    qty_int = int(qty)
    if qty_int > bag_lot.bags_remaining:
        raise FeedBagSellError(
            {"quantity": (
                f"Доступно только {bag_lot.bags_remaining} шт мешков."
            )}
        )

    # Customer
    if customer is None:
        customer = _resolve_or_create_retail_customer(organization)
    elif customer.organization_id != organization.id:
        raise FeedBagSellError({"customer": "Покупатель из другой организации."})

    # Цена. У FeedBagLot нет sale_price — обязательно от продавца.
    if unit_price_uzs is None:
        raise FeedBagSellError(
            {"unit_price_uzs": "Укажите цену за мешок — у партии нет дефолтной."}
        )
    unit_price_uzs = Decimal(str(unit_price_uzs))
    if unit_price_uzs <= 0:
        raise FeedBagSellError({"unit_price_uzs": "Цена должна быть > 0."})

    # Nomenclature — обязательна для SaleItem.
    nomenclature = _resolve_nomenclature(bag_lot)
    if nomenclature is None:
        raise FeedBagSellError(
            {"bag_lot": (
                "Не найден NomenclatureItem для рецепта. Заведите номенклатурную "
                "позицию с sku = recipe.code."
            )}
        )

    # SaleOrder
    today = date.today()
    doc_number = next_doc_number(
        SaleOrder, organization=organization, prefix="ПР", on_date=today,
    )
    order = SaleOrder.objects.create(
        organization=organization,
        module=bag_lot.module,
        doc_number=doc_number,
        date=today,
        customer=customer,
        warehouse=bag_lot.storage_warehouse,
        status=SaleOrder.Status.DRAFT,
        notes=(
            f"Розничная продажа feed-партии {bag_lot.doc_number} "
            f"(barcode {bag_lot.barcode or '—'}) · продавец {seller_user}"
        ),
        created_by=seller_user,
    )
    SaleItem.objects.create(
        order=order,
        nomenclature=nomenclature,
        feed_bag_lot=bag_lot,
        quantity=qty_int,
        unit_price_uzs=unit_price_uzs,
    )

    # Confirm — создаст JE/StockMovement и декрементирует bags_remaining.
    try:
        confirm_sale(order, user=seller_user)
    except Exception as exc:
        raise FeedBagSellError({"__all__": f"Ошибка проведения продажи: {exc}"})

    order.refresh_from_db()
    bag_lot.refresh_from_db()

    if bag_lot.bags_remaining <= 0:
        bag_lot.status = FeedBagLot.Status.DEPLETED
        bag_lot.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=organization,
        module=bag_lot.module,
        actor=seller_user,
        action=AuditLog.Action.POST,
        entity=order,
        action_verb=(
            f"feed retail sale {order.doc_number} · "
            f"{bag_lot.doc_number} × {qty_int} bag(s) · "
            f"by seller {seller_user}"
        ),
    )

    return FeedBagSellResult(
        sale_order=order,
        bag_lot=bag_lot,
        total_uzs=order.amount_uzs,
        remaining_bags=bag_lot.bags_remaining,
    )
