"""
Тесты reverse_payment — сторно проведённого платежа.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.post import post_payment
from apps.payments.services.reverse import (
    PaymentReverseError,
    reverse_payment,
)
from apps.purchases.models import PurchaseItem, PurchaseOrder
from apps.purchases.services.confirm import confirm_purchase
from apps.warehouses.models import Warehouse


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
        organization=org, name="Корма сырьё",
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
    confirm_purchase(order)
    order.refresh_from_db()
    return order


@pytest.fixture
def posted_payment(org, module_purchases, supplier, confirmed_order):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("1000000"),
    )
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)
    PaymentAllocation.objects.create(
        payment=payment, target_content_type=po_ct,
        target_object_id=confirmed_order.id,
        amount_uzs=Decimal("1000000"),
    )
    post_payment(payment)
    payment.refresh_from_db()
    return payment


# ─── Core flow ───────────────────────────────────────────────────────────


def test_reverse_sets_cancelled_status(posted_payment):
    result = reverse_payment(posted_payment, reason="откат")
    assert result.payment.status == Payment.Status.CANCELLED


def test_reverse_creates_swapped_journal(posted_payment):
    original_je = posted_payment.journal_entry
    result = reverse_payment(posted_payment)

    rev = result.reverse_journal
    assert rev.debit_subaccount_id == original_je.credit_subaccount_id
    assert rev.credit_subaccount_id == original_je.debit_subaccount_id
    assert rev.amount_uzs == original_je.amount_uzs
    assert rev.doc_number.startswith("ПР-2026-")


def test_reverse_recalculates_po_status(posted_payment, confirmed_order):
    # До reverse — PO PAID
    confirmed_order.refresh_from_db()
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PAID

    reverse_payment(posted_payment)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("0.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.UNPAID


def test_reverse_keeps_allocations(posted_payment):
    """Аллокации не удаляются — они исторический след."""
    assert posted_payment.allocations.count() == 1
    reverse_payment(posted_payment)
    posted_payment.refresh_from_db()
    assert posted_payment.allocations.count() == 1


def test_reverse_preserves_original_je(posted_payment):
    """Исходная JE остаётся — бух иммутабельность."""
    original_je_id = posted_payment.journal_entry_id
    reverse_payment(posted_payment)
    assert JournalEntry.objects.filter(pk=original_je_id).exists()


# ─── Multi-payment scenario ──────────────────────────────────────────────


def test_reverse_one_of_two_leaves_partial(
    org, module_purchases, supplier, confirmed_order
):
    """PO оплачен двумя платежами; reverse одного — остаётся PARTIAL."""
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)

    p1 = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("400000"),
    )
    PaymentAllocation.objects.create(
        payment=p1, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("400000"),
    )
    post_payment(p1)

    p2 = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 25), direction="out", channel="transfer",
        counterparty=supplier, amount_uzs=Decimal("600000"),
    )
    PaymentAllocation.objects.create(
        payment=p2, target_content_type=po_ct,
        target_object_id=confirmed_order.id, amount_uzs=Decimal("600000"),
    )
    post_payment(p2)

    confirmed_order.refresh_from_db()
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PAID

    p1.refresh_from_db()
    reverse_payment(p1)

    confirmed_order.refresh_from_db()
    assert confirmed_order.paid_amount_uzs == Decimal("600000.00")
    assert confirmed_order.payment_status == PurchaseOrder.PaymentStatus.PARTIAL


# ─── Guards ──────────────────────────────────────────────────────────────


def test_reverse_draft_raises(org, module_purchases, supplier):
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("100000"),
    )
    with pytest.raises(ValidationError):
        reverse_payment(payment)


def test_reverse_twice_raises(posted_payment):
    reverse_payment(posted_payment)
    with pytest.raises(ValidationError):
        reverse_payment(posted_payment)
