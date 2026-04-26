"""
Тесты reverse_sale — сторно проведённой продажи.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale
from apps.sales.services.reverse import SaleReverseError, reverse_sale
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures (аналогично test_confirm) ──────────────────────────────────


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
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def category_meat(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="43.01")
    return Category.objects.get_or_create(
        organization=org, name="Мясо птицы",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def chicken(org, category_meat, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ТШК-01", name="Тушка куриная",
        category=category_meat, unit=unit_kg,
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
    return Batch.objects.create(
        organization=org, doc_number="П-2026-00001",
        nomenclature=chicken, unit=unit_kg,
        origin_module=module_slaughter,
        current_quantity=Decimal("100.000"),
        initial_quantity=Decimal("100.000"),
        accumulated_cost_uzs=Decimal("2000000.00"),
        state=Batch.State.ACTIVE,
        started_at=date(2026, 4, 20),
    )


@pytest.fixture
def confirmed_sale(org, module_sales, buyer, warehouse, chicken, meat_batch):
    order = SaleOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), customer=buyer, warehouse=warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("30.000"), unit_price_uzs=Decimal("35000"),
    )
    confirm_sale(order)
    order.refresh_from_db()
    return order


# ─── Core flow ───────────────────────────────────────────────────────────


def test_reverse_sets_cancelled_status(confirmed_sale):
    result = reverse_sale(confirmed_sale, reason="клиент отказался")
    assert result.order.status == SaleOrder.Status.CANCELLED


def test_reverse_restores_batch_quantity(confirmed_sale, meat_batch):
    # После confirm в батче осталось 70
    meat_batch.refresh_from_db()
    assert meat_batch.current_quantity == Decimal("70.000")

    reverse_sale(confirmed_sale)

    meat_batch.refresh_from_db()
    assert meat_batch.current_quantity == Decimal("100.000")


def test_reverse_restores_completed_batch_to_active(
    org, module_sales, module_slaughter, buyer, warehouse, chicken, unit_kg
):
    """Если партия была COMPLETED после полной продажи, reverse возвращает её в ACTIVE."""
    batch = Batch.objects.create(
        organization=org, doc_number="П-2026-00002",
        nomenclature=chicken, unit=unit_kg, origin_module=module_slaughter,
        current_quantity=Decimal("50.000"),
        initial_quantity=Decimal("50.000"),
        accumulated_cost_uzs=Decimal("1000000.00"),
        state=Batch.State.ACTIVE, started_at=date(2026, 4, 20),
    )
    order = SaleOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), customer=buyer, warehouse=warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=batch,
        quantity=Decimal("50.000"), unit_price_uzs=Decimal("30000"),
    )
    confirm_sale(order)
    order.refresh_from_db()

    batch.refresh_from_db()
    assert batch.state == Batch.State.COMPLETED

    reverse_sale(order)

    batch.refresh_from_db()
    assert batch.state == Batch.State.ACTIVE
    assert batch.current_quantity == Decimal("50.000")
    assert batch.completed_at is None


def test_reverse_creates_incoming_movement(confirmed_sale, warehouse):
    result = reverse_sale(confirmed_sale)

    assert len(result.reverse_movements) == 1
    sm = result.reverse_movements[0]
    assert sm.kind == StockMovement.Kind.INCOMING
    assert sm.warehouse_to_id == warehouse.id
    assert sm.warehouse_from_id is None


def test_reverse_creates_swapped_journals(confirmed_sale):
    originals = list(
        JournalEntry.objects.filter(source_object_id=confirmed_sale.id)
    )
    assert len(originals) == 2  # выручка + себестоимость

    result = reverse_sale(confirmed_sale)

    assert len(result.reverse_journals) == 2
    # Все сторно-JE имеют описание «Сторно продажи»
    for je in result.reverse_journals:
        assert je.description.startswith("Сторно продажи")

    # Для каждой исходной JE должна быть обратная: Dr ↔ Cr
    originals_by_pair = {
        (je.debit_subaccount_id, je.credit_subaccount_id): je.amount_uzs
        for je in originals
    }
    for rev in result.reverse_journals:
        swapped_pair = (rev.credit_subaccount_id, rev.debit_subaccount_id)
        assert swapped_pair in originals_by_pair
        assert originals_by_pair[swapped_pair] == rev.amount_uzs


def test_reverse_preserves_original_documents(confirmed_sale):
    reverse_sale(confirmed_sale)

    # Исходные OUTGOING должны остаться
    outgoing = StockMovement.objects.filter(
        source_object_id=confirmed_sale.id,
        kind=StockMovement.Kind.OUTGOING,
    )
    assert outgoing.count() == 1
    # Всего SM: 1 OUTGOING + 1 INCOMING
    assert StockMovement.objects.filter(
        source_object_id=confirmed_sale.id
    ).count() == 2
    # JE: исходные 2 + сторно 2 = 4
    assert JournalEntry.objects.filter(
        source_object_id=confirmed_sale.id
    ).count() == 4


# ─── Guards ──────────────────────────────────────────────────────────────


def test_reverse_draft_raises(
    org, module_sales, buyer, warehouse, chicken, meat_batch
):
    order = SaleOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), customer=buyer, warehouse=warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("10.000"), unit_price_uzs=Decimal("30000"),
    )
    with pytest.raises(ValidationError):
        reverse_sale(order)


def test_reverse_twice_raises(confirmed_sale):
    reverse_sale(confirmed_sale)
    with pytest.raises(ValidationError):
        reverse_sale(confirmed_sale)


def test_reverse_paid_raises(confirmed_sale):
    confirmed_sale.paid_amount_uzs = Decimal("500000")
    confirmed_sale.save(update_fields=["paid_amount_uzs"])
    with pytest.raises(ValidationError):
        reverse_sale(confirmed_sale)
