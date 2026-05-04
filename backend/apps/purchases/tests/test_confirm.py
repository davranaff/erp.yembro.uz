"""
Тесты сервиса confirm_purchase.

Ключевой инвариант (задача #1 пользователя): exchange_rate фиксируется на
момент конфирма и НЕ меняется, даже если источник (CBU ExchangeRate)
позже обновится или удалится.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.currency.models import Currency, ExchangeRate
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.purchases.models import PurchaseItem, PurchaseOrder
from apps.purchases.services.confirm import (
    PurchaseConfirmError,
    confirm_purchase,
)
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


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
def module_stock():
    return Module.objects.get(code="stock")


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
    return Unit.objects.get_or_create(organization=org, code="кг", defaults={"name": "Килограмм"})[0]


@pytest.fixture
def category_feed(org):
    # Привязываем категорию к субсчёту 10.05 (Корма) — чтобы
    # _resolve_debit_subaccount нашёл его.
    sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    return Category.objects.get_or_create(
        organization=org,
        name="Корма сырьё",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def corn(org, category_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org,
        sku="С-КУК-01",
        name="Кукуруза",
        category=category_feed,
        unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org,
        code="К-SUPP-01",
        kind="supplier",
        name="Агроимпорт",
    )


@pytest.fixture
def warehouse(org, module_feed):
    return Warehouse.objects.create(
        organization=org,
        module=module_feed,
        code="СК-СР",
        name="Склад сырья",
    )


@pytest.fixture
def uzs_order(org, module_purchases, supplier, warehouse, corn):
    order = PurchaseOrder.objects.create(
        organization=org,
        module=module_purchases,
        doc_number="",
        date=date(2026, 4, 24),
        counterparty=supplier,
        warehouse=warehouse,
        status=PurchaseOrder.Status.DRAFT,
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn, quantity=Decimal("1000"), unit_price=Decimal("18000")
    )
    PurchaseItem.objects.create(
        order=order,
        nomenclature=corn,
        quantity=Decimal("500"),
        unit_price=Decimal("17500"),
    )
    return order


@pytest.fixture
def fx_order(org, module_purchases, supplier, warehouse, corn, usd):
    order = PurchaseOrder.objects.create(
        organization=org,
        module=module_purchases,
        doc_number="",
        date=date(2026, 4, 24),
        counterparty=supplier,
        warehouse=warehouse,
        status=PurchaseOrder.Status.DRAFT,
        currency=usd,
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn, quantity=Decimal("50000"), unit_price=Decimal("0.02")
    )
    return order


@pytest.fixture
def usd_rate(usd):
    return ExchangeRate.objects.create(
        currency=usd,
        date=date(2026, 4, 24),
        rate=Decimal("12015.96"),
        nominal=1,
        source="cbu.uz",
        fetched_at=datetime.now(timezone.utc),
    )


# ─── UZS (без FX) ────────────────────────────────────────────────────────


def test_confirm_uzs_sets_amount_and_status(uzs_order):
    result = confirm_purchase(uzs_order)

    assert result.order.status == PurchaseOrder.Status.CONFIRMED
    # 1000*18000 + 500*17500 = 18_000_000 + 8_750_000 = 26_750_000
    assert result.order.amount_uzs == Decimal("26750000.00")
    assert result.order.amount_foreign is None
    assert result.order.exchange_rate is None
    assert result.order.exchange_rate_source is None
    assert result.rate_snapshot is None


def test_confirm_uzs_generates_doc_number(uzs_order):
    assert uzs_order.doc_number == ""
    result = confirm_purchase(uzs_order)
    assert result.order.doc_number.startswith("ЗК-2026-")


def test_confirm_uzs_creates_stock_movement_per_item(uzs_order, warehouse, corn):
    confirm_purchase(uzs_order)
    movements = StockMovement.objects.filter(
        source_object_id=uzs_order.id, kind=StockMovement.Kind.INCOMING
    )
    assert movements.count() == 2
    for sm in movements:
        assert sm.warehouse_to_id == warehouse.id
        assert sm.nomenclature_id == corn.id
        assert sm.counterparty_id == uzs_order.counterparty_id


def test_confirm_uzs_creates_journal_entry(uzs_order):
    confirm_purchase(uzs_order)
    je = JournalEntry.objects.get(source_object_id=uzs_order.id)
    assert je.amount_uzs == Decimal("26750000.00")
    assert je.currency_id is None
    assert je.exchange_rate is None
    assert je.debit_subaccount.code == "10.05"
    assert je.credit_subaccount.code == "60.01"  # UZS suppliers


# ─── FX (закуп в USD) ────────────────────────────────────────────────────


def test_confirm_fx_sets_snapshot_fields(fx_order, usd_rate):
    result = confirm_purchase(fx_order)

    assert result.order.status == PurchaseOrder.Status.CONFIRMED
    assert result.order.exchange_rate == Decimal("12015.960000")
    assert result.order.exchange_rate_source_id == usd_rate.id
    # 50000 * 0.02 = 1000 USD
    assert result.order.amount_foreign == Decimal("1000.00")
    # 1000 * 12015.96 = 12_015_960.00
    assert result.order.amount_uzs == Decimal("12015960.00")
    assert result.rate_snapshot == Decimal("12015.960000")


def test_confirm_fx_journal_entry_has_fx_snapshot(fx_order, usd_rate, usd):
    confirm_purchase(fx_order)
    je = JournalEntry.objects.get(source_object_id=fx_order.id)
    assert je.currency_id == usd.id
    assert je.amount_foreign == Decimal("1000.00")
    assert je.exchange_rate == Decimal("12015.960000")
    assert je.amount_uzs == Decimal("12015960.00")
    assert je.credit_subaccount.code == "60.02"  # FX suppliers


def test_confirm_fx_missing_rate_raises(fx_order):
    # usd_rate fixture НЕ используется — курса нет
    with pytest.raises(ValidationError):
        confirm_purchase(fx_order)


def test_confirm_fx_uses_fallback_rate_within_7_days(fx_order, usd):
    # Курс на 18.04, закуп на 24.04 — должно сработать (fallback 7 дней)
    ExchangeRate.objects.create(
        currency=usd,
        date=date(2026, 4, 18),
        rate=Decimal("11800.00"),
        nominal=1,
        source="cbu.uz",
        fetched_at=datetime.now(timezone.utc),
    )
    result = confirm_purchase(fx_order)
    assert result.rate_snapshot == Decimal("11800.000000")


# ─── КЛЮЧЕВОЙ ТЕСТ: FX snapshot immutability ─────────────────────────────


def test_fx_snapshot_immutable_when_cbu_rate_changes_afterwards(fx_order, usd_rate, usd):
    """
    ЭТО главный инвариант задачи #1 пользователя:
    если после конфирма CBU «перепишет» курс — у нас всё осталось.
    """
    result = confirm_purchase(fx_order)
    frozen_rate = result.order.exchange_rate
    frozen_uzs = result.order.amount_uzs

    # Через месяц CBU поправил курс на ту же дату
    usd_rate.rate = Decimal("99999.99")
    usd_rate.save()

    # Перезагрузим заказ — snapshot должен остаться
    fx_order.refresh_from_db()
    assert fx_order.exchange_rate == frozen_rate
    assert fx_order.amount_uzs == frozen_uzs

    # JournalEntry тоже сохранил snapshot
    je = JournalEntry.objects.get(source_object_id=fx_order.id)
    assert je.exchange_rate == frozen_rate


def test_fx_snapshot_survives_rate_deletion(fx_order, usd_rate):
    """
    Если ExchangeRate-запись вообще удалят — в PurchaseOrder остаётся
    число (поле `exchange_rate`), а FK `exchange_rate_source` становится
    NULL (on_delete=SET_NULL).
    """
    result = confirm_purchase(fx_order)
    frozen_rate = result.order.exchange_rate

    usd_rate.delete()

    fx_order.refresh_from_db()
    assert fx_order.exchange_rate == frozen_rate  # число сохранилось
    assert fx_order.exchange_rate_source_id is None


# ─── Идемпотентность и guard-ы ──────────────────────────────────────────


def test_confirm_twice_raises(uzs_order):
    confirm_purchase(uzs_order)
    with pytest.raises(ValidationError):
        confirm_purchase(uzs_order)


def test_confirm_empty_order_raises(org, module_purchases, supplier, warehouse):
    empty = PurchaseOrder.objects.create(
        organization=org,
        module=module_purchases,
        doc_number="",
        date=date(2026, 4, 24),
        counterparty=supplier,
        warehouse=warehouse,
    )
    with pytest.raises(ValidationError):
        confirm_purchase(empty)


def test_confirm_is_atomic_rolls_back_on_error(
    fx_order, usd_rate, monkeypatch
):
    """
    Если что-то упадёт после создания StockMovement но до сохранения
    PurchaseOrder — транзакция откатится и в БД не останется осиротевших
    движений.
    """
    # Ломаем создание JournalEntry
    from apps.purchases.services import confirm as confirm_module

    original_save = JournalEntry.save

    def broken_save(self, *args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken_save)

    with pytest.raises(RuntimeError):
        confirm_purchase(fx_order)

    # Откат: никаких StockMovement / JournalEntry не должно остаться
    assert StockMovement.objects.filter(source_object_id=fx_order.id).count() == 0
    assert JournalEntry.objects.filter(source_object_id=fx_order.id).count() == 0

    # order остался в DRAFT
    fx_order.refresh_from_db()
    assert fx_order.status == PurchaseOrder.Status.DRAFT
    assert fx_order.exchange_rate is None
