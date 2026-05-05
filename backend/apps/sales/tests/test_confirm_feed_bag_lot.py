"""
Тесты sale-confirm для FeedBagLot (продажа фасованного корма в мешках).

Ключевые инварианты:
    1. quantity = кол-во мешков (целое), декремент bags_remaining.
    2. cost_per_unit = bag_unit_cost из FeedBagLot (наследуется при фасовке).
    3. line_cost = qty (мешков) × cost_per_bag.
    4. StockMovement в кг (qty × bag_weight_kg) — единая nomenclature
       консистентна с FeedBatch.
    5. Полная продажа → status=DEPLETED.
    6. Запрет продажи не-ACTIVE партии.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.feed.models import FeedBagLot, FeedBatch
from apps.feed.services.execute_task import execute_production_task
from apps.feed.services.package_feed_batch import package_feed_batch
from apps.modules.models import Module
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import SaleConfirmError, confirm_sale
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# Фикстуры из feed-тестов: основной флоу `замес → фасовка → продажа`
from apps.feed.tests.test_execute_task import (  # noqa: F401
    org,
    m_feed,
    user,
    unit_kg,
    cat_raw,
    corn,
    soy,
    supplier,
    mixer_line,
    storage_bin,
    raw_warehouse,
    ready_warehouse,
    corn_batch,
    soy_batch,
    recipe,
    recipe_version,
    broiler_feed_nom,
    task,
)


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def buyer(org):
    from apps.counterparties.models import Counterparty
    return Counterparty.objects.create(
        organization=org, code="К-BUY-FBL", kind="buyer",
        name="Покупатель мешков",
    )


@pytest.fixture
def bag_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-МШ-CONF", name="Склад мешков (confirm test)",
    )


@pytest.fixture
def bag_lot(task, ready_warehouse, storage_bin, broiler_feed_nom, bag_warehouse):
    """20 мешков по 50 кг = 1000 кг (вся партия)."""
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED
    fb.save(update_fields=["status"])
    pkg = package_feed_batch(
        fb, bag_count=20, bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    )
    return pkg.bag_lot


def _make_order(org, m_sales, buyer, bag_warehouse):
    return SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="",
        date=date(2026, 5, 4), customer=buyer, warehouse=bag_warehouse,
    )


def test_confirm_decrements_bags_and_uses_bag_unit_cost(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    # Продаём 5 мешков по 1 200 000 сум/мешок (наценка над cost ~1 035 000)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("5"), unit_price_uzs=Decimal("1200000"),
    )

    result = confirm_sale(order)

    assert result.order.status == SaleOrder.Status.CONFIRMED
    bag_lot.refresh_from_db()
    assert bag_lot.bags_remaining == 15
    assert bag_lot.status == FeedBagLot.Status.ACTIVE  # ещё есть остаток

    item = order.items.first()
    # cost_per_unit_uzs = bag_lot.unit_cost_uzs ≈ 1 035 000.00
    assert item.cost_per_unit_uzs == bag_lot.unit_cost_uzs
    # line_cost = 5 × cost_per_unit
    assert item.line_cost_uzs == (Decimal(bag_lot.unit_cost_uzs) * 5).quantize(
        Decimal("0.01")
    )
    # line_total = 5 × 1 200 000 = 6 000 000
    assert item.line_total_uzs == Decimal("6000000.00")


def test_confirm_full_sale_marks_bag_lot_depleted(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("20"), unit_price_uzs=Decimal("1100000"),
    )
    confirm_sale(order)
    bag_lot.refresh_from_db()
    assert bag_lot.bags_remaining == 0
    assert bag_lot.status == FeedBagLot.Status.DEPLETED


def test_confirm_stock_movement_in_kg_for_bag_lot(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    """Несмотря на то что продали 3 мешка, в StockMovement quantity=150 кг
    (3×50) — единая nomenclature по кг."""
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("3"), unit_price_uzs=Decimal("1200000"),
    )
    res = confirm_sale(order)
    sms = [
        sm for sm in res.stock_movements
        if sm.kind == StockMovement.Kind.OUTGOING
        and sm.nomenclature_id == broiler_feed_nom.id
    ]
    assert len(sms) == 1
    sm = sms[0]
    assert sm.quantity == Decimal("150.000")  # 3 × 50
    # unit_price = bag_unit_cost / bag_weight ≈ cost_per_kg
    assert sm.unit_price_uzs == (
        Decimal(bag_lot.unit_cost_uzs) / Decimal("50")
    ).quantize(Decimal("0.01"))


def test_confirm_rejects_non_active_bag_lot(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    bag_lot.status = FeedBagLot.Status.DEPLETED
    bag_lot.save()
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("1"), unit_price_uzs=Decimal("1100000"),
    )
    with pytest.raises(SaleConfirmError):
        confirm_sale(order)


def test_confirm_rejects_non_integer_bag_quantity(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    """Мешки целые — qty=2.5 запрещено."""
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("2.5"), unit_price_uzs=Decimal("1200000"),
    )
    with pytest.raises(SaleConfirmError):
        confirm_sale(order)


def test_confirm_rejects_more_bags_than_available(
    org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom,
):
    order = _make_order(org, m_sales, buyer, bag_warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal("25"), unit_price_uzs=Decimal("1200000"),
    )
    with pytest.raises(SaleConfirmError):
        confirm_sale(order)
