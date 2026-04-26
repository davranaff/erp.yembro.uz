"""
Тесты сервиса confirm_sale.

Ключевые сценарии:
    1. UZS продажа — создаёт 2 JE (выручка + себестоимость) с правильными
       субсчетами.
    2. Декремент остатка Batch; при нуле — state=COMPLETED.
    3. Частичная продажа оставляет state=ACTIVE.
    4. FX-snapshot фиксируется из get_rate_for().
    5. Себестоимость идёт на category.default_gl_subaccount (Cr).
    6. Продажа больше остатка → ValidationError.
    7. Повторный confirm → ValidationError.
    8. Atomicity: при падении JE.save ничего не остаётся.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.currency.models import Currency, ExchangeRate
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import SaleConfirmError, confirm_sale
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def module_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def module_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def usd():
    return Currency.objects.get_or_create(
        code="USD",
        defaults={"numeric_code": "840", "name_ru": "Доллар США"},
    )[0]


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def category_meat(org):
    """Готовая продукция списывается с 43.01."""
    sub = GLSubaccount.objects.get(account__organization=org, code="43.01")
    return Category.objects.get_or_create(
        organization=org,
        name="Мясо птицы",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def chicken(org, category_meat, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org,
        sku="ТШК-01",
        name="Тушка куриная",
        category=category_meat,
        unit=unit_kg,
    )


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="К-BUY-01", kind="buyer", name="Дастархан",
    )


@pytest.fixture
def warehouse(org, module_slaughter):
    return Warehouse.objects.create(
        organization=org, module=module_slaughter,
        code="СК-ГОТ", name="Склад готовой продукции",
    )


@pytest.fixture
def meat_batch(org, module_slaughter, chicken, unit_kg):
    """Партия: 100 кг, накопленная стоимость 2_000_000 → 20_000 за кг."""
    return Batch.objects.create(
        organization=org,
        doc_number="П-2026-00001",
        nomenclature=chicken,
        unit=unit_kg,
        origin_module=module_slaughter,
        current_quantity=Decimal("100.000"),
        initial_quantity=Decimal("100.000"),
        accumulated_cost_uzs=Decimal("2000000.00"),
        state=Batch.State.ACTIVE,
        started_at=date(2026, 4, 20),
    )


@pytest.fixture
def usd_rate(usd):
    return ExchangeRate.objects.create(
        currency=usd, date=date(2026, 4, 24),
        rate=Decimal("12015.96"), nominal=1,
        source="cbu.uz", fetched_at=datetime.now(timezone.utc),
    )


def _make_order(org, module_sales, buyer, warehouse, **extras):
    return SaleOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), customer=buyer, warehouse=warehouse,
        **extras,
    )


# ─── UZS продажа ─────────────────────────────────────────────────────────


def test_confirm_uzs_sets_status_and_amounts(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("30.000"), unit_price_uzs=Decimal("35000"),
    )

    result = confirm_sale(order)

    assert result.order.status == SaleOrder.Status.CONFIRMED
    # 30 × 35_000 = 1_050_000
    assert result.order.amount_uzs == Decimal("1050000.00")
    # cost: 30 × (2_000_000 / 100) = 30 × 20_000 = 600_000
    assert result.order.cost_uzs == Decimal("600000.00")
    assert result.order.amount_foreign is None
    assert result.order.exchange_rate is None


def test_confirm_uzs_generates_doc_number(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("10.000"), unit_price_uzs=Decimal("30000"),
    )
    assert order.doc_number == ""

    result = confirm_sale(order)
    assert result.order.doc_number.startswith("ПРД-2026-")


def test_confirm_creates_two_journal_entries(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    """Продажа генерирует: 1 JE выручки + 1 JE себестоимости на каждую item."""
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("50.000"), unit_price_uzs=Decimal("40000"),
    )

    result = confirm_sale(order)

    # Проверяем выручку: Dr 62.01 / Cr 90.01, amount = 2_000_000
    rev_je = result.revenue_journal
    assert rev_je.debit_subaccount.code == "62.01"
    assert rev_je.credit_subaccount.code == "90.01"
    assert rev_je.amount_uzs == Decimal("2000000.00")

    # Себестоимость: Dr 90.02 / Cr 43.01 (из category_meat), amount = 1_000_000
    assert len(result.cost_journals) == 1
    cost_je = result.cost_journals[0]
    assert cost_je.debit_subaccount.code == "90.02"
    assert cost_je.credit_subaccount.code == "43.01"
    assert cost_je.amount_uzs == Decimal("1000000.00")


def test_confirm_decrements_batch_quantity(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("40.000"), unit_price_uzs=Decimal("30000"),
    )

    confirm_sale(order)
    meat_batch.refresh_from_db()

    assert meat_batch.current_quantity == Decimal("60.000")
    assert meat_batch.state == Batch.State.ACTIVE


def test_confirm_full_sale_completes_batch(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("100.000"), unit_price_uzs=Decimal("30000"),
    )

    confirm_sale(order)
    meat_batch.refresh_from_db()

    assert meat_batch.current_quantity == Decimal("0.000")
    assert meat_batch.state == Batch.State.COMPLETED
    assert meat_batch.completed_at is not None


def test_confirm_creates_outgoing_stock_movement(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("20.000"), unit_price_uzs=Decimal("35000"),
    )

    result = confirm_sale(order)

    assert len(result.stock_movements) == 1
    sm = result.stock_movements[0]
    assert sm.kind == StockMovement.Kind.OUTGOING
    assert sm.warehouse_from_id == warehouse.id
    assert sm.warehouse_to_id is None
    assert sm.nomenclature_id == chicken.id
    assert sm.quantity == Decimal("20.000")
    # unit_price_uzs в StockMovement — это себестоимость, не цена продажи
    assert sm.unit_price_uzs == Decimal("20000.00")
    assert sm.amount_uzs == Decimal("400000.00")  # 20 × 20000


# ─── FX продажа ──────────────────────────────────────────────────────────


def test_confirm_fx_snapshot_fields(
    org, module_sales, buyer, warehouse, chicken, meat_batch, usd, usd_rate
):
    order = _make_order(org, module_sales, buyer, warehouse, currency=usd)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("10.000"), unit_price_uzs=Decimal("3"),  # $3 за кг
    )

    result = confirm_sale(order)

    assert result.order.exchange_rate == Decimal("12015.960000")
    assert result.order.exchange_rate_source_id == usd_rate.id
    # 10 × 3 = 30 USD
    assert result.order.amount_foreign == Decimal("30.00")
    # 30 × 12015.96 = 360_478.80
    assert result.order.amount_uzs == Decimal("360478.80")


def test_confirm_fx_uses_62_02(
    org, module_sales, buyer, warehouse, chicken, meat_batch, usd, usd_rate
):
    order = _make_order(org, module_sales, buyer, warehouse, currency=usd)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("5.000"), unit_price_uzs=Decimal("2"),
    )

    result = confirm_sale(order)
    assert result.revenue_journal.debit_subaccount.code == "62.02"  # FX AR


def test_confirm_fx_missing_rate_raises(
    org, module_sales, buyer, warehouse, chicken, meat_batch, usd
):
    # usd_rate fixture НЕ подключаем
    order = _make_order(org, module_sales, buyer, warehouse, currency=usd)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("5.000"), unit_price_uzs=Decimal("2"),
    )
    with pytest.raises(ValidationError):
        confirm_sale(order)


# ─── Guards ──────────────────────────────────────────────────────────────


def test_confirm_twice_raises(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("10.000"), unit_price_uzs=Decimal("30000"),
    )
    confirm_sale(order)
    with pytest.raises(ValidationError):
        confirm_sale(order)


def test_confirm_empty_order_raises(
    org, module_sales, buyer, warehouse
):
    order = _make_order(org, module_sales, buyer, warehouse)
    with pytest.raises(ValidationError):
        confirm_sale(order)


def test_confirm_oversell_raises(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    """В партии 100 кг, пытаемся продать 101."""
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("101.000"), unit_price_uzs=Decimal("30000"),
    )
    with pytest.raises(ValidationError):
        confirm_sale(order)

    # Батч не тронут, заказ остался в DRAFT
    meat_batch.refresh_from_db()
    assert meat_batch.current_quantity == Decimal("100.000")
    order.refresh_from_db()
    assert order.status == SaleOrder.Status.DRAFT


def test_confirm_is_atomic(
    org, module_sales, buyer, warehouse, chicken, meat_batch, monkeypatch
):
    order = _make_order(org, module_sales, buyer, warehouse)
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("10.000"), unit_price_uzs=Decimal("30000"),
    )

    original_save = JournalEntry.save

    def broken_save(self, *a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken_save)

    with pytest.raises(RuntimeError):
        confirm_sale(order)

    # Rollback: батч, движения, JE — не должно ничего остаться
    meat_batch.refresh_from_db()
    assert meat_batch.current_quantity == Decimal("100.000")

    assert StockMovement.objects.filter(source_object_id=order.id).count() == 0
    assert JournalEntry.objects.filter(source_object_id=order.id).count() == 0

    order.refresh_from_db()
    assert order.status == SaleOrder.Status.DRAFT
