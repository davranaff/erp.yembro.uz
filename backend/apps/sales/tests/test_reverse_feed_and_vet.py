"""
Тесты reverse_sale для feed_bag_lot и vet_accessory — критический путь:
если оператор отменяет продажу, товар должен вернуться на склад. Раньше
_restore_source умел batch / feed_batch / vet_stock_batch и молча игнорил
feed_bag_lot и vet_accessory → мешки/аксессуары физически уходили
безвозвратно при reverse.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.feed.models import FeedBagLot, FeedBatch
from apps.feed.services.execute_task import execute_production_task
from apps.feed.services.package_feed_batch import package_feed_batch
from apps.modules.models import Module
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale
from apps.sales.services.reverse import reverse_sale
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


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
        organization=org, code="К-RVR", kind="buyer", name="Reverse buyer",
    )


@pytest.fixture
def bag_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-МШ-RVR", name="Bag WH (reverse)",
    )


def _confirmed_bag_sale(org, m_sales, buyer, bag_warehouse, bag_lot, nom, qty):
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="",
        date=date(2026, 5, 5), customer=buyer, warehouse=bag_warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=nom,
        feed_bag_lot=bag_lot,
        quantity=Decimal(str(qty)), unit_price_uzs=Decimal("1200000"),
    )
    confirm_sale(order)
    return order


def test_reverse_restores_bags_to_lot(
    org, m_sales, buyer, bag_warehouse, task, ready_warehouse, storage_bin,
    broiler_feed_nom,
):
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED; fb.save(update_fields=["status"])
    bag_lot = package_feed_batch(
        fb, bag_count=20, bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    ).bag_lot

    # Продали 5 мешков → осталось 15
    order = _confirmed_bag_sale(org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom, 5)
    bag_lot.refresh_from_db()
    assert bag_lot.bags_remaining == 15

    # Reverse → мешки вернулись
    reverse_sale(order, reason="клиент отказался")
    bag_lot.refresh_from_db()
    assert bag_lot.bags_remaining == 20
    assert bag_lot.status == FeedBagLot.Status.ACTIVE


def test_reverse_restores_depleted_bag_lot_to_active(
    org, m_sales, buyer, bag_warehouse, task, ready_warehouse, storage_bin,
    broiler_feed_nom,
):
    """Если продали все мешки → bag_lot стал DEPLETED. Reverse должен
    вернуть его в ACTIVE."""
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED; fb.save(update_fields=["status"])
    bag_lot = package_feed_batch(
        fb, bag_count=20, bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    ).bag_lot

    order = _confirmed_bag_sale(org, m_sales, buyer, bag_warehouse, bag_lot, broiler_feed_nom, 20)
    bag_lot.refresh_from_db()
    assert bag_lot.status == FeedBagLot.Status.DEPLETED

    reverse_sale(order)
    bag_lot.refresh_from_db()
    assert bag_lot.bags_remaining == 20
    assert bag_lot.status == FeedBagLot.Status.ACTIVE


def test_reverse_restores_depleted_feed_batch_to_approved(
    org, m_sales, buyer, ready_warehouse, task, storage_bin, broiler_feed_nom,
):
    """Аналогично — насыпь, проданная под ноль, должна вернуться в APPROVED."""
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED; fb.save(update_fields=["status"])
    qty = fb.current_quantity_kg  # 1000 кг

    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="",
        date=date(2026, 5, 5), customer=buyer, warehouse=ready_warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=broiler_feed_nom,
        feed_batch=fb,
        quantity=qty, unit_price_uzs=Decimal("25000"),
    )
    confirm_sale(order)
    fb.refresh_from_db()
    assert fb.status == FeedBatch.Status.DEPLETED

    reverse_sale(order)
    fb.refresh_from_db()
    assert fb.current_quantity_kg == qty
    assert fb.status == FeedBatch.Status.APPROVED


def test_reverse_restores_vet_accessory(org, m_sales, buyer, m_feed):
    """vet_accessory.current_quantity должен инкрементироваться при reverse."""
    from apps.counterparties.models import Counterparty  # noqa
    from apps.nomenclature.models import Category, NomenclatureItem, Unit
    from apps.vet.models import VetAccessory

    m_vet = Module.objects.get(code="vet")
    sales_wh = Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-RVR-S", name="Sales WH",
    )
    vet_wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-V-RVR", name="Vet WH",
    )
    unit = Unit.objects.create(organization=org, code="шт", name="штука")
    cat = Category.objects.create(organization=org, name="Аксессуары rvr")
    nom = NomenclatureItem.objects.create(
        organization=org, sku="ACC-1", name="Поилка", category=cat, unit=unit,
    )
    acc = VetAccessory.objects.create(
        organization=org, module=m_vet, nomenclature=nom, warehouse=vet_wh,
        current_quantity=Decimal("100"),
        cost_per_unit_uzs=Decimal("5000"),
        sale_price_uzs=Decimal("8000"),
        is_active=True,
    )

    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="",
        date=date(2026, 5, 5), customer=buyer, warehouse=sales_wh,
    )
    SaleItem.objects.create(
        order=order, nomenclature=nom, vet_accessory=acc,
        quantity=Decimal("10"), unit_price_uzs=Decimal("8500"),
    )
    confirm_sale(order)
    acc.refresh_from_db()
    assert acc.current_quantity == Decimal("90.000")

    reverse_sale(order)
    acc.refresh_from_db()
    assert acc.current_quantity == Decimal("100.000")
