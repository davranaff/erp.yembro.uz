"""
Утилиты для расчёта складского остатка.

Источник истины — `StockMovement`: остаток SKU на складе =
    Σ(INCOMING + TRANSFER_IN на этот склад)
  − Σ(OUTGOING + WRITE_OFF + TRANSFER_OUT с этого склада)

Используется в:
  • VetAccessoryViewSet.perform_create — для гварда «нельзя создать
    карточку если на складе нет прихода по SKU»
  • аналогично можно гвардить любые другие vet-операции
"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum

from ..models import StockMovement


def compute_warehouse_balance_for_sku(warehouse, nomenclature) -> Decimal:
    """
    Возвращает текущий остаток SKU на складе (Decimal).

    Если движений нет — 0. Не учитывает черновики (StockMovement по
    дизайну только posted-записи; promote/cancel создают сторно-записи).
    """
    qs = StockMovement.objects.filter(
        organization=warehouse.organization,
        nomenclature=nomenclature,
    ).filter(Q(warehouse_from=warehouse) | Q(warehouse_to=warehouse))

    agg = qs.aggregate(
        in_qty=Sum("quantity", filter=Q(
            warehouse_to=warehouse,
            kind__in=[StockMovement.Kind.INCOMING, StockMovement.Kind.TRANSFER],
        )),
        out_qty=Sum("quantity", filter=Q(
            warehouse_from=warehouse,
            kind__in=[
                StockMovement.Kind.OUTGOING,
                StockMovement.Kind.WRITE_OFF,
                StockMovement.Kind.TRANSFER,
                # SHRINKAGE физически списывает товар (cron усушки).
                # Без него балансы хранения корма врали на величину
                # испарения — на проде это сотни кг за месяц.
                StockMovement.Kind.SHRINKAGE,
            ],
        )),
    )
    in_qty = Decimal(agg.get("in_qty") or 0)
    out_qty = Decimal(agg.get("out_qty") or 0)
    return in_qty - out_qty
