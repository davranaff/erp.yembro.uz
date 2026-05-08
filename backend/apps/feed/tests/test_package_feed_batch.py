"""
Тесты сервиса ``package_feed_batch`` — фасовка партии комбикорма в мешки.

Ключевые инварианты:
    1. Создаётся FeedBagLot с правильным cost (per-kg → per-bag).
    2. source.current_quantity_kg декрементируется на bag_count × bag_weight.
    3. Если source ушёл в 0 — статус DEPLETED.
    4. StockMovements OUT/IN созданы (если есть склады и nomenclature).
    5. Нельзя фасовать не-APPROVED партию.
    6. Нельзя фасовать больше чем остаток.
    7. Cross-org/module склад → ошибка.
    8. Фасовка с медикаментозного source → bag_lot тоже медикаментозный.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.feed.models import FeedBagLot, FeedBatch, ProductionTask, RecipeVersion
from apps.feed.services.execute_task import execute_production_task
from apps.feed.services.package_feed_batch import (
    FeedPackageError,
    package_feed_batch,
)
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# Используем фикстуры из test_execute_task — те же org / m_feed / corn / etc.
# Импорт фикстур через conftest.py не нужен — pytest подхватывает их из
# того же directory автоматически только когда они в conftest. Здесь же
# мы переопределим минимум — основной флоу: сначала execute_production_task,
# потом package.


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
def bag_warehouse(org, m_feed):
    """Отдельный склад для расфасованных мешков."""
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-МШ", name="Склад мешков",
    )


@pytest.fixture
def approved_feed_batch(task, ready_warehouse, storage_bin, broiler_feed_nom):
    """Провести замес → получить approved FeedBatch с 1000 кг и cost ~21300/кг."""
    res = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = res.feed_batch
    fb.status = FeedBatch.Status.APPROVED
    fb.save(update_fields=["status"])
    return fb


# ─── happy path ──────────────────────────────────────────────────────────


def test_package_creates_bag_lot_with_correct_costs(
    approved_feed_batch, bag_warehouse, user,
):
    """80 мешков × 50 кг = 4000... но у нас всего 1000кг → 20 мешков × 50 кг."""
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=20,
        bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
        user=user,
    )
    bl = res.bag_lot
    assert bl.bags_initial == 20
    assert bl.bags_remaining == 20
    assert bl.bag_weight_kg == Decimal("50.000")
    # source.unit_cost_uzs ≈ (700×18000 + 300×27000) / 1000 = 20700000/1000 = 20700
    # bag_unit_cost = 20700 × 50 = 1 035 000 сум/мешок
    expected_unit = Decimal("20700.000000") * Decimal("50")
    expected_unit_q = expected_unit.quantize(Decimal("0.01"))
    assert bl.unit_cost_uzs == expected_unit_q
    assert bl.total_cost_uzs == (expected_unit_q * 20).quantize(Decimal("0.01"))
    assert bl.status == FeedBagLot.Status.ACTIVE
    assert bl.storage_warehouse_id == bag_warehouse.id
    assert bl.recipe_version_id == approved_feed_batch.recipe_version_id


def test_package_decrements_source_kg(
    approved_feed_batch, bag_warehouse,
):
    initial_kg = Decimal(approved_feed_batch.current_quantity_kg)
    package_feed_batch(
        approved_feed_batch,
        bag_count=10,
        bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    )
    approved_feed_batch.refresh_from_db()
    assert Decimal(approved_feed_batch.current_quantity_kg) == initial_kg - Decimal("500")
    # 1000 - 500 = 500 кг осталось → ещё ACTIVE/APPROVED
    assert approved_feed_batch.status == FeedBatch.Status.APPROVED


def test_package_full_remaining_marks_source_depleted(
    approved_feed_batch, bag_warehouse,
):
    """Расфасовать все 1000 кг → source становится DEPLETED."""
    package_feed_batch(
        approved_feed_batch,
        bag_count=20,
        bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    )
    approved_feed_batch.refresh_from_db()
    assert Decimal(approved_feed_batch.current_quantity_kg) == Decimal("0.000")
    assert approved_feed_batch.status == FeedBatch.Status.DEPLETED


def test_package_creates_stock_movements(
    approved_feed_batch, bag_warehouse, broiler_feed_nom,
):
    """OUT из бункера-замеса + IN в склад мешков."""
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=10,
        bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    )
    assert len(res.stock_movements) == 2
    out_sm = next(sm for sm in res.stock_movements if sm.kind == StockMovement.Kind.OUTGOING)
    in_sm = next(sm for sm in res.stock_movements if sm.kind == StockMovement.Kind.INCOMING)
    # OUT — со склада исходного замеса
    assert out_sm.warehouse_from_id == approved_feed_batch.storage_warehouse_id
    assert out_sm.quantity == Decimal("500.000")
    # IN — на склад мешков
    assert in_sm.warehouse_to_id == bag_warehouse.id
    assert in_sm.quantity == Decimal("500.000")
    # Обе ссылаются на bag_lot
    assert out_sm.source_object_id == res.bag_lot.id
    assert in_sm.source_object_id == res.bag_lot.id


def test_package_inherits_medicated_flag(
    approved_feed_batch, bag_warehouse,
):
    approved_feed_batch.is_medicated = True
    approved_feed_batch.withdrawal_period_days = 7
    approved_feed_batch.withdrawal_period_ends = date.today() + timedelta(days=7)
    approved_feed_batch.save()
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=5,
        bag_weight_kg=Decimal("50"),
        storage_warehouse=bag_warehouse,
    )
    assert res.bag_lot.is_medicated is True
    assert res.bag_lot.withdrawal_period_days == 7
    assert res.bag_lot.withdrawal_period_ends == approved_feed_batch.withdrawal_period_ends


# ─── guards ──────────────────────────────────────────────────────────────


def test_package_non_approved_raises(
    approved_feed_batch, bag_warehouse,
):
    approved_feed_batch.status = FeedBatch.Status.QUALITY_CHECK
    approved_feed_batch.save()
    with pytest.raises(FeedPackageError):
        package_feed_batch(
            approved_feed_batch,
            bag_count=10,
            bag_weight_kg=Decimal("50"),
            storage_warehouse=bag_warehouse,
        )


def test_package_more_than_available_raises(
    approved_feed_batch, bag_warehouse,
):
    """1000 кг доступно, пытаемся расфасовать 25 × 50 = 1250 кг."""
    with pytest.raises(FeedPackageError):
        package_feed_batch(
            approved_feed_batch,
            bag_count=25,
            bag_weight_kg=Decimal("50"),
            storage_warehouse=bag_warehouse,
        )


def test_package_zero_bags_raises(
    approved_feed_batch, bag_warehouse,
):
    with pytest.raises(FeedPackageError):
        package_feed_batch(
            approved_feed_batch,
            bag_count=0,
            bag_weight_kg=Decimal("50"),
            storage_warehouse=bag_warehouse,
        )


def test_package_negative_weight_raises(
    approved_feed_batch, bag_warehouse,
):
    with pytest.raises(FeedPackageError):
        package_feed_batch(
            approved_feed_batch,
            bag_count=10,
            bag_weight_kg=Decimal("-5"),
            storage_warehouse=bag_warehouse,
        )


def test_package_cross_org_warehouse_raises(
    approved_feed_batch, m_feed, org,
):
    from apps.organizations.models import Organization
    other_org = Organization.objects.create(
        code="OTHER", name="Other",
        accounting_currency=org.accounting_currency,
    )
    other_wh = Warehouse.objects.create(
        organization=other_org, module=m_feed,
        code="OTHER-WH", name="Other warehouse",
    )
    with pytest.raises(FeedPackageError):
        package_feed_batch(
            approved_feed_batch,
            bag_count=10,
            bag_weight_kg=Decimal("50"),
            storage_warehouse=other_wh,
        )


def test_package_idempotency_multiple_lots_from_same_source(
    approved_feed_batch, bag_warehouse,
):
    """От одного source можно создать N FeedBagLot (разные смены фасовки)."""
    res1 = package_feed_batch(
        approved_feed_batch, bag_count=5,
        bag_weight_kg=Decimal("50"), storage_warehouse=bag_warehouse,
    )
    res2 = package_feed_batch(
        approved_feed_batch, bag_count=10,
        bag_weight_kg=Decimal("50"), storage_warehouse=bag_warehouse,
    )
    assert res1.bag_lot.id != res2.bag_lot.id
    assert res1.bag_lot.source_feed_batch_id == res2.bag_lot.source_feed_batch_id
    approved_feed_batch.refresh_from_db()
    # 1000 - 250 - 500 = 250 кг
    assert Decimal(approved_feed_batch.current_quantity_kg) == Decimal("250.000")


# ─── packaging (empty bag) auto-deduction ─────────────────────────────────


@pytest.fixture
def cat_packaging(org, m_feed):
    from apps.nomenclature.models import Category
    return Category.objects.create(
        organization=org, name="Упаковка корма (test)", module=m_feed,
    )


@pytest.fixture
def empty_bag_50(org, cat_packaging, unit_kg):
    """SKU пустого мешка 50 кг (используется автoрезолвом по bag_weight)."""
    from apps.nomenclature.models import NomenclatureItem, Unit
    pcs = Unit.objects.create(organization=org, code="pcs", name="Штука")
    return NomenclatureItem.objects.create(
        organization=org, sku="KORM-XALTA-50",
        name="Мешок пустой 50 кг", category=cat_packaging, unit=pcs,
    )


@pytest.fixture
def stocked_bag_warehouse(bag_warehouse, empty_bag_50, org, m_feed, user):
    """Склад мешков с приходом 100 пустых мешков (≈1000 сум/штука)."""
    from datetime import datetime, timezone
    StockMovement.objects.create(
        organization=org, module=m_feed,
        doc_number="ПР-МШ-001",
        kind=StockMovement.Kind.INCOMING,
        date=datetime.now(timezone.utc),
        nomenclature=empty_bag_50,
        quantity=Decimal("100"),
        unit_price_uzs=Decimal("1000"),
        amount_uzs=Decimal("100000"),
        warehouse_to=bag_warehouse,
        created_by=user,
    )
    return bag_warehouse


def test_package_auto_resolves_empty_bag_by_weight(
    approved_feed_batch, stocked_bag_warehouse, empty_bag_50, user,
):
    """bag_weight=50 → автoрезолв KORM-XALTA-50 → списание со склада."""
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=10, bag_weight_kg=Decimal("50"),
        storage_warehouse=stocked_bag_warehouse, user=user,
    )
    # Среди stock_movements должен быть OUTGOING на пустой мешок
    bag_outs = [
        sm for sm in res.stock_movements
        if sm.nomenclature_id == empty_bag_50.id
        and sm.kind == StockMovement.Kind.OUTGOING
    ]
    assert len(bag_outs) == 1
    assert bag_outs[0].quantity == Decimal("10")
    assert bag_outs[0].warehouse_from_id == stocked_bag_warehouse.id


def test_package_explicit_packaging_nomenclature(
    approved_feed_batch, stocked_bag_warehouse, empty_bag_50, user,
):
    """Явный SKU мешка работает даже при нестандартном bag_weight."""
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=5, bag_weight_kg=Decimal("50"),
        storage_warehouse=stocked_bag_warehouse,
        packaging_nomenclature=empty_bag_50,
        user=user,
    )
    bag_outs = [
        sm for sm in res.stock_movements
        if sm.nomenclature_id == empty_bag_50.id
    ]
    assert len(bag_outs) == 1
    assert bag_outs[0].quantity == Decimal("5")


def test_package_fails_when_not_enough_empty_bags(
    approved_feed_batch, bag_warehouse, empty_bag_50, user,
):
    """100 мешков надо, но на складе пусто → ошибка."""
    with pytest.raises(FeedPackageError) as exc:
        package_feed_batch(
            approved_feed_batch,
            bag_count=10, bag_weight_kg=Decimal("50"),
            storage_warehouse=bag_warehouse,
            packaging_nomenclature=empty_bag_50,
            user=user,
        )
    assert "пустых мешков" in str(exc.value).lower()


def test_package_no_auto_when_weight_nonstandard(
    approved_feed_batch, bag_warehouse, empty_bag_50, user,
):
    """bag_weight=33 кг → не находит SKU → не пытается списать."""
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=5, bag_weight_kg=Decimal("33"),
        storage_warehouse=bag_warehouse, user=user,
    )
    # Нет write-off на пустые мешки — только feed-перемещения
    bag_outs = [
        sm for sm in res.stock_movements
        if sm.nomenclature_id == empty_bag_50.id
    ]
    assert len(bag_outs) == 0


def test_package_includes_empty_bag_cost_in_unit_cost(
    approved_feed_batch, stocked_bag_warehouse, empty_bag_50, user,
):
    """
    Регрессия (audit gap #3): стоимость пустого мешка должна попадать в
    FeedBagLot.unit_cost_uzs, не теряться в OUTGOING SM пустых мешков.
    Без этого downstream-продажи получают заниженную себестоимость.

    Stocked: 100 мешков по 1000 сум/штука → pack_unit_cost = 1000.
    feed_per_bag = source.unit_cost (20700) × bag_weight (50) = 1_035_000.
    bag_unit_cost = 1_035_000 + 1000 = 1_036_000.
    """
    res = package_feed_batch(
        approved_feed_batch,
        bag_count=10, bag_weight_kg=Decimal("50"),
        storage_warehouse=stocked_bag_warehouse, user=user,
    )
    feed_per_bag = (Decimal("20700.000000") * Decimal("50")).quantize(Decimal("0.01"))
    pack_unit_cost = Decimal("1000.00")
    expected_unit = (feed_per_bag + pack_unit_cost).quantize(Decimal("0.01"))
    assert res.bag_lot.unit_cost_uzs == expected_unit
    assert res.bag_lot.total_cost_uzs == (expected_unit * 10).quantize(Decimal("0.01"))
