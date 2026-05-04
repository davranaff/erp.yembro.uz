"""
Тесты сервиса post_payment.

Ключевые сценарии:
    1. OUT платёж cash → Dr 60.01 / Cr 50.01.
    2. OUT платёж transfer → Cr 51.01.
    3. FX OUT платёж → Dr 60.02 (валютные AP).
    4. IN платёж → Dr 50.01 / Cr 62.01 (без аллокаций).
    5. Аллокация на PO обновляет paid_amount_uzs / payment_status.
    6. Multi-payment по одному PO: суммы правильно складываются.
    7. Overpay.
    8. Идемпотентность: второй post → ValidationError.
    9. Сумма аллокаций != amount_uzs → ValidationError.
    10. Атомарность.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.currency.models import Currency, ExchangeRate
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.post import (
    PaymentPostError,
    create_and_post_payment,
    post_payment,
)
from apps.purchases.models import PurchaseItem, PurchaseOrder
from apps.purchases.services.confirm import confirm_purchase
from apps.warehouses.models import Warehouse


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
        organization=org, code="К-SUPP-01", kind="supplier", name="Агроимпорт"
    )


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="К-BUY-01", kind="buyer", name="Дастархан"
    )


@pytest.fixture
def warehouse(org, module_feed):
    return Warehouse.objects.create(
        organization=org, module=module_feed, code="СК-СР", name="Склад сырья"
    )


@pytest.fixture
def usd_rate(usd):
    return ExchangeRate.objects.create(
        currency=usd, date=date(2026, 4, 24),
        rate=Decimal("12015.96"), nominal=1,
        source="cbu.uz", fetched_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def confirmed_order(org, module_purchases, supplier, warehouse, corn):
    """Создать и провести UZS-закуп на 10M UZS."""
    order = PurchaseOrder.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), counterparty=supplier, warehouse=warehouse,
    )
    PurchaseItem.objects.create(
        order=order, nomenclature=corn,
        quantity=Decimal("1000"), unit_price=Decimal("10000"),
    )
    confirm_purchase(order)
    order.refresh_from_db()
    assert order.amount_uzs == Decimal("10000000.00")
    return order


# ─── OUT платежи ─────────────────────────────────────────────────────────


def test_out_cash_uzs_creates_je_60_01_to_50_01(org, supplier, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("1000000"),
    )
    result = post_payment(payment)

    assert result.payment.status == Payment.Status.POSTED
    assert result.payment.posted_at is not None
    assert result.payment.doc_number.startswith("ПЛ-2026-")

    je = result.journal_entry
    assert je.debit_subaccount.code == "60.01"
    assert je.credit_subaccount.code == "50.01"
    assert je.amount_uzs == Decimal("1000000.00")
    assert je.currency_id is None


def test_out_transfer_uzs_uses_51_01(org, supplier, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="transfer",
        counterparty=supplier, amount_uzs=Decimal("500000"),
    )
    result = post_payment(payment)
    assert result.journal_entry.credit_subaccount.code == "51.01"


def test_out_click_uses_51_01(org, supplier, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="click",
        counterparty=supplier, amount_uzs=Decimal("300000"),
    )
    result = post_payment(payment)
    assert result.journal_entry.credit_subaccount.code == "51.01"


def test_fx_out_uses_60_02(org, supplier, module_purchases, usd, usd_rate):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="transfer",
        counterparty=supplier,
        currency=usd, exchange_rate=Decimal("12015.96"),
        exchange_rate_source=usd_rate,
        amount_foreign=Decimal("100.00"),
        amount_uzs=Decimal("1201596.00"),
    )
    result = post_payment(payment)

    je = result.journal_entry
    assert je.debit_subaccount.code == "60.02"
    assert je.credit_subaccount.code == "51.01"
    assert je.currency_id == usd.id
    assert je.amount_foreign == Decimal("100.00")
    assert je.exchange_rate == Decimal("12015.96")


# ─── IN платежи ──────────────────────────────────────────────────────────


def test_in_cash_creates_je_50_01_to_62_01(org, buyer, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="in", channel="cash",
        counterparty=buyer, amount_uzs=Decimal("2000000"),
    )
    result = post_payment(payment)
    je = result.journal_entry
    assert je.debit_subaccount.code == "50.01"
    assert je.credit_subaccount.code == "62.01"


# ─── Аллокации и payment_status ──────────────────────────────────────────


def test_full_payment_with_allocation_marks_po_paid(
    org, module_purchases, supplier, confirmed_order
):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("10000000"),
    )
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id,
        amount_uzs=Decimal("10000000"),
    )

    result = post_payment(payment)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("10000000.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PAID
    assert len(result.affected_orders) == 1


def test_partial_payment_sets_partial_status(
    org, module_purchases, supplier, confirmed_order
):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("4000000"),
    )
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id,
        amount_uzs=Decimal("4000000"),
    )
    post_payment(payment)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("4000000.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PARTIAL


def test_multiple_payments_sum_correctly(
    org, module_purchases, supplier, confirmed_order
):
    """Два платежа по 4M + 6M == 10M (full)."""
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)

    p1 = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("4000000"),
    )
    PaymentAllocation.objects.create(
        payment=p1, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("4000000"),
    )
    post_payment(p1)

    confirmed_order.refresh_from_db()
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PARTIAL

    p2 = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 25), direction="out", channel="transfer",
        counterparty=supplier, amount_uzs=Decimal("6000000"),
    )
    PaymentAllocation.objects.create(
        payment=p2, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("6000000"),
    )
    post_payment(p2)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("10000000.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PAID


def test_overpay_sets_overpaid_status(
    org, module_purchases, supplier, confirmed_order
):
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("11000000"),
    )
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("11000000"),
    )
    post_payment(payment)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("11000000.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.OVERPAID


def test_allocation_sum_must_match_amount(
    org, module_purchases, supplier, confirmed_order
):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("1000000"),
    )
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id,
        amount_uzs=Decimal("500000"),  # != 1000000
    )
    with pytest.raises(ValidationError):
        post_payment(payment)


# ─── Гарды ───────────────────────────────────────────────────────────────


def test_post_twice_raises(org, supplier, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("100000"),
    )
    post_payment(payment)
    with pytest.raises(ValidationError):
        post_payment(payment)


def test_post_cancelled_raises(org, supplier, module_purchases):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("100000"),
        status=Payment.Status.CANCELLED,
    )
    with pytest.raises(ValidationError):
        post_payment(payment)


def test_atomicity_rollback_on_error(
    org, module_purchases, supplier, confirmed_order, monkeypatch
):
    """Если JournalEntry.save() упадёт — ничего не сохранится."""
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("1000000"),
    )
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("1000000"),
    )

    original_save = JournalEntry.save

    def broken(self, *a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken)

    with pytest.raises(RuntimeError):
        post_payment(payment)

    payment.refresh_from_db()
    confirmed_order.refresh_from_db()
    # payment должен остаться в исходном статусе, PO не тронут
    assert payment.status == Payment.Status.DRAFT
    assert payment.journal_entry_id is None
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.UNPAID
    assert confirmed_order.paid_amount_uzs == Decimal("0.00")


# ─── Helper create_and_post_payment ──────────────────────────────────────


def test_create_and_post_payment_helper(
    org, module_purchases, supplier, confirmed_order
):
    result = create_and_post_payment(
        organization=org,
        module=module_purchases,
        direction="out",
        channel="cash",
        counterparty=supplier,
        amount_uzs=Decimal("10000000"),
        date=date(2026, 4, 24),
        allocations=[{"target": confirmed_order, "amount_uzs": Decimal("10000000")}],
    )
    assert result.payment.status == Payment.Status.POSTED
    assert result.affected_orders[0].payment_status == PurchaseOrder.PaymentStatus.PAID
