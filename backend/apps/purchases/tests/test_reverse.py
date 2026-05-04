"""
Тесты reverse_purchase — сторно проведённого закупа.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.purchases.models import PurchaseItem, PurchaseOrder
from apps.purchases.services.confirm import confirm_purchase
from apps.purchases.services.reverse import (
    PurchaseReverseError,
    reverse_purchase,
)
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def module_purchases():
    return Module.objects.get(code="purchases")


@pytest.fixture
def module_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def category_feed(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    return Category.objects.get_or_create(
        organization=org,
        name="Корма сырьё",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def corn(org, category_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-01", name="Кукуруза",
        category=category_feed, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-SUPP-01", kind="supplier", name="Агроимпорт",
    )


@pytest.fixture
def warehouse(org, module_feed):
    return Warehouse.objects.create(
        organization=org, module=module_feed, code="СК-СР", name="Склад сырья",
    )


@pytest.fixture
def confirmed_order(org, module_purchases, supplier, warehouse, corn):
    order = PurchaseOrder.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), counterparty=supplier, warehouse=warehouse,
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn,
        quantity=Decimal("100"), unit_price=Decimal("10000"),
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn,
        quantity=Decimal("50"), unit_price=Decimal("12000"),
    )
    confirm_purchase(order)
    order.refresh_from_db()
    return order


# ─── Core flow ───────────────────────────────────────────────────────────


def test_reverse_sets_cancelled_status(confirmed_order):
    result = reverse_purchase(confirmed_order, reason="ошибка ввода")
    assert result.order.status == PurchaseOrder.Status.CANCELLED


def test_reverse_creates_writeoff_per_incoming(confirmed_order):
    result = reverse_purchase(confirmed_order)
    assert len(result.reverse_movements) == 2
    for sm in result.reverse_movements:
        assert sm.kind == StockMovement.Kind.WRITE_OFF
        assert sm.warehouse_to_id is None
        # warehouse_from — это исходный warehouse_to закупа
        assert sm.warehouse_from_id == confirmed_order.warehouse_id


def test_reverse_creates_swapped_journal(confirmed_order):
    original_je = JournalEntry.objects.get(source_object_id=confirmed_order.id)
    result = reverse_purchase(confirmed_order)

    rev_je = result.reverse_journal
    assert rev_je.debit_subaccount_id == original_je.credit_subaccount_id
    assert rev_je.credit_subaccount_id == original_je.debit_subaccount_id
    assert rev_je.amount_uzs == original_je.amount_uzs
    assert rev_je.doc_number.startswith("ПР-2026-")


def test_reverse_preserves_original_documents(confirmed_order):
    reverse_purchase(confirmed_order)
    # Оригинальные приходы и JE должны остаться
    incoming = StockMovement.objects.filter(
        source_object_id=confirmed_order.id,
        kind=StockMovement.Kind.INCOMING,
    )
    assert incoming.count() == 2
    # Всего SM — 2 IN + 2 WRITE_OFF = 4
    assert StockMovement.objects.filter(
        source_object_id=confirmed_order.id
    ).count() == 4
    # Два JE (исходный + сторно)
    assert JournalEntry.objects.filter(
        source_object_id=confirmed_order.id
    ).count() == 2


# ─── Guards ──────────────────────────────────────────────────────────────


def test_reverse_draft_raises(org, module_purchases, supplier, warehouse, corn):
    order = PurchaseOrder.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), counterparty=supplier, warehouse=warehouse,
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn,
        quantity=Decimal("10"), unit_price=Decimal("1000"),
    )
    with pytest.raises(ValidationError):
        reverse_purchase(order)


def test_reverse_twice_raises(confirmed_order):
    reverse_purchase(confirmed_order)
    with pytest.raises(ValidationError):
        reverse_purchase(confirmed_order)


def test_reverse_paid_raises(confirmed_order):
    """Если есть оплаты — надо сначала reverse_payment."""
    confirmed_order.paid_amount_uzs = Decimal("100000")
    confirmed_order.save(update_fields=["paid_amount_uzs"])
    with pytest.raises(ValidationError):
        reverse_purchase(confirmed_order)


def test_reverse_is_atomic(confirmed_order, monkeypatch):
    """Если JE.save упадёт — должен быть откат."""
    original_save = JournalEntry.save

    call_count = {"n": 0}

    def broken_save(self, *a, **kw):
        call_count["n"] += 1
        # пустим первое сохранение JE (не по сторно), ломаем второе
        if call_count["n"] >= 1 and getattr(self, "description", "").startswith("Сторно"):
            raise RuntimeError("boom")
        return original_save(self, *a, **kw)

    monkeypatch.setattr(JournalEntry, "save", broken_save)

    with pytest.raises(RuntimeError):
        reverse_purchase(confirmed_order)

    confirmed_order.refresh_from_db()
    assert confirmed_order.status == PurchaseOrder.Status.CONFIRMED
    # Не должно появиться ни одного WRITE_OFF / сторно-JE
    assert StockMovement.objects.filter(
        source_object_id=confirmed_order.id,
        kind=StockMovement.Kind.WRITE_OFF,
    ).count() == 0
