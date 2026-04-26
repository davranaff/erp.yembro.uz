"""
Тесты взаимодействия Payment (direction=IN) + SaleOrder.

Ключевые сценарии:
    1. IN-платёж с аллокацией на SaleOrder → payment_status=PARTIAL/PAID/OVERPAID.
    2. Два IN-платежа суммируются в paid_amount_uzs.
    3. OUT-платёж нельзя аллоцировать на SaleOrder.
    4. IN-платёж нельзя аллоцировать на PurchaseOrder.
    5. reverse_payment возвращает SaleOrder в UNPAID.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount
from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.post import post_payment
from apps.payments.services.reverse import reverse_payment
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import confirm_sale
from apps.warehouses.models import Warehouse


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
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-SUPP-01", kind="supplier", name="Агроимпорт",
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
        state=Batch.State.ACTIVE, started_at=date(2026, 4, 20),
    )


@pytest.fixture
def confirmed_sale(org, module_sales, buyer, warehouse, chicken, meat_batch):
    """Продажа на 1_000_000 UZS (50 кг × 20_000)."""
    order = SaleOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), customer=buyer, warehouse=warehouse,
    )
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=meat_batch,
        quantity=Decimal("50.000"), unit_price_uzs=Decimal("20000"),
    )
    confirm_sale(order)
    order.refresh_from_db()
    assert order.amount_uzs == Decimal("1000000.00")
    return order


def _allocate(payment, target, amount):
    ct = ContentType.objects.get_for_model(type(target))
    return PaymentAllocation.objects.create(
        payment=payment, target_content_type=ct,
        target_object_id=target.id, amount_uzs=amount,
    )


def _make_in_payment(org, module_sales, buyer, amount):
    return Payment.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), direction="in", channel="cash",
        counterparty=buyer, amount_uzs=amount,
    )


# ─── Happy path ──────────────────────────────────────────────────────────


def test_full_payment_marks_sale_paid(
    org, module_sales, buyer, confirmed_sale
):
    payment = _make_in_payment(org, module_sales, buyer, Decimal("1000000"))
    _allocate(payment, confirmed_sale, Decimal("1000000"))

    result = post_payment(payment)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.paid_amount_uzs == Decimal("1000000.00")
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.PAID
    assert len(result.affected_orders) == 1
    assert result.affected_orders[0].id == confirmed_sale.id


def test_partial_payment_sets_partial_status(
    org, module_sales, buyer, confirmed_sale
):
    payment = _make_in_payment(org, module_sales, buyer, Decimal("400000"))
    _allocate(payment, confirmed_sale, Decimal("400000"))

    post_payment(payment)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.paid_amount_uzs == Decimal("400000.00")
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.PARTIAL


def test_overpayment_sets_overpaid_status(
    org, module_sales, buyer, confirmed_sale
):
    payment = _make_in_payment(org, module_sales, buyer, Decimal("1200000"))
    _allocate(payment, confirmed_sale, Decimal("1200000"))

    post_payment(payment)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.paid_amount_uzs == Decimal("1200000.00")
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.OVERPAID


def test_multiple_payments_sum_correctly(
    org, module_sales, buyer, confirmed_sale
):
    p1 = _make_in_payment(org, module_sales, buyer, Decimal("300000"))
    _allocate(p1, confirmed_sale, Decimal("300000"))
    post_payment(p1)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.PARTIAL

    p2 = _make_in_payment(org, module_sales, buyer, Decimal("700000"))
    _allocate(p2, confirmed_sale, Decimal("700000"))
    post_payment(p2)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.paid_amount_uzs == Decimal("1000000.00")
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.PAID


def test_in_payment_uses_ar_62_01(
    org, module_sales, buyer, confirmed_sale
):
    """IN-платёж в UZS: Dr cash / Cr 62.01."""
    payment = _make_in_payment(org, module_sales, buyer, Decimal("1000000"))
    _allocate(payment, confirmed_sale, Decimal("1000000"))

    result = post_payment(payment)
    assert result.journal_entry.debit_subaccount.code == "50.01"
    assert result.journal_entry.credit_subaccount.code == "62.01"


# ─── Guards: направление ↔ тип документа ────────────────────────────────


def test_out_payment_cannot_allocate_to_sale(
    org, module_sales, supplier, confirmed_sale
):
    """OUT-платёж (поставщику) нельзя разнести на SaleOrder."""
    payment = Payment.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), direction="out", channel="cash",
        counterparty=supplier, amount_uzs=Decimal("100000"),
    )
    _allocate(payment, confirmed_sale, Decimal("100000"))

    with pytest.raises(ValidationError):
        post_payment(payment)


def test_in_payment_cannot_allocate_to_purchase(
    org, module_sales, buyer, supplier, warehouse
):
    """IN-платёж (от покупателя) нельзя разнести на PurchaseOrder."""
    from apps.purchases.models import PurchaseItem
    from apps.purchases.services.confirm import confirm_purchase

    # Готовим минимальный confirmed PurchaseOrder
    unit = Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"}
    )[0]
    feed_sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    cat = Category.objects.get_or_create(
        organization=org, name="Корма сырьё",
        defaults={"default_gl_subaccount": feed_sub},
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="С-01", name="Товар",
        category=cat, unit=unit,
    )
    po = PurchaseOrder.objects.create(
        organization=org, module=module_sales, doc_number="",
        date=date(2026, 4, 24), counterparty=supplier, warehouse=warehouse,
    )
    PurchaseItem.objects.create(
        order=po, nomenclature=nom,
        quantity=Decimal("10"), unit_price=Decimal("1000"),
    )
    confirm_purchase(po)
    po.refresh_from_db()

    payment = _make_in_payment(org, module_sales, buyer, Decimal("10000"))
    _allocate(payment, po, Decimal("10000"))

    with pytest.raises(ValidationError):
        post_payment(payment)


# ─── Reverse ─────────────────────────────────────────────────────────────


def test_reverse_payment_restores_sale_unpaid(
    org, module_sales, buyer, confirmed_sale
):
    payment = _make_in_payment(org, module_sales, buyer, Decimal("1000000"))
    _allocate(payment, confirmed_sale, Decimal("1000000"))
    post_payment(payment)

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.PAID

    reverse_payment(payment, reason="возврат")

    confirmed_sale.refresh_from_db()
    assert confirmed_sale.paid_amount_uzs == Decimal("0.00")
    assert confirmed_sale.payment_status == SaleOrder.PaymentStatus.UNPAID
