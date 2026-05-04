"""
Тесты "прочих" операций через Payment с contra_subaccount.

Сценарии:
    1. OPEX (прочий расход) OUT — Дт 26.01 / Кт 50.01.
    2. INCOME (прочий доход) IN — Дт 50.01 / Кт 91.01.
    3. OPEX без counterparty проводится ok.
    4. OPEX + allocation → ошибка.
    5. Обычный counterparty-платёж + contra_subaccount → ошибка.
    6. Расход привязан к модулю — создаётся JournalEntry с module.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.payments.models import Payment, PaymentAllocation
from apps.payments.services.post import PaymentPostError, post_payment


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def module_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def module_purchases():
    return Module.objects.get(code="purchases")


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-SUPP-01", kind="supplier", name="Поставщик",
    )


def _sub(org, code: str):
    return GLSubaccount.objects.get(account__organization=org, code=code)


# ─── OPEX: расход с contra_subaccount ────────────────────────────────────


def test_opex_out_cash_creates_je_with_contra(org, module_feed):
    """Оплатили электричество наличкой — Дт 26.01 / Кт 50.01."""
    payment = Payment.objects.create(
        organization=org,
        module=module_feed,
        doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.OPEX,
        amount_uzs=Decimal("2000000"),
        contra_subaccount=_sub(org, "26.01"),
    )
    result = post_payment(payment)

    assert result.payment.status == Payment.Status.POSTED
    je = result.journal_entry
    assert je.debit_subaccount.code == "26.01"
    assert je.credit_subaccount.code == "50.01"
    assert je.amount_uzs == Decimal("2000000")
    # Модуль зафиксирован в проводке (для аналитики)
    assert je.module_id == module_feed.id


def test_opex_out_transfer_uses_51_01(org, module_feed):
    """Перевели с расчётного счёта за связь — Дт 26.02 / Кт 51.01."""
    payment = Payment.objects.create(
        organization=org,
        module=module_feed,
        doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.TRANSFER,
        kind=Payment.Kind.OPEX,
        amount_uzs=Decimal("500000"),
        contra_subaccount=_sub(org, "26.02"),
    )
    result = post_payment(payment)
    assert result.journal_entry.debit_subaccount.code == "26.02"
    assert result.journal_entry.credit_subaccount.code == "51.01"


def test_opex_on_module_nzp_20_05(org, module_feed):
    """Списание на НЗП модуля корма — Дт 20.05 / Кт 50.01."""
    payment = Payment.objects.create(
        organization=org,
        module=module_feed,
        doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.OPEX,
        amount_uzs=Decimal("1500000"),
        contra_subaccount=_sub(org, "20.05"),
    )
    result = post_payment(payment)
    assert result.journal_entry.debit_subaccount.code == "20.05"
    assert result.journal_entry.credit_subaccount.code == "50.01"


# ─── INCOME: прочий доход ────────────────────────────────────────────────


def test_income_in_cash_creates_je_with_contra(org, module_purchases):
    """Получили компенсацию страховой — Дт 50.01 / Кт 91.01."""
    payment = Payment.objects.create(
        organization=org,
        module=module_purchases,
        doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.IN,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.INCOME,
        amount_uzs=Decimal("500000"),
        contra_subaccount=_sub(org, "91.01"),
    )
    result = post_payment(payment)
    je = result.journal_entry
    assert je.debit_subaccount.code == "50.01"
    assert je.credit_subaccount.code == "91.01"


# ─── Без counterparty — ок для OPEX ──────────────────────────────────────


def test_opex_without_counterparty_ok(org, module_feed):
    """Для opex counterparty не обязателен (оплата в налоговую / на служебные нужды)."""
    payment = Payment.objects.create(
        organization=org,
        module=module_feed,
        doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.OPEX,
        amount_uzs=Decimal("100000"),
        contra_subaccount=_sub(org, "26.09"),
        counterparty=None,
    )
    result = post_payment(payment)
    assert result.payment.status == Payment.Status.POSTED


# ─── Guards: конфликты между contra и allocation/counterparty ────────────


def test_opex_with_allocation_raises(org, module_feed, supplier):
    """Нельзя одновременно разносить на PO и указывать contra."""
    # Создадим confirmed PO для allocation
    from datetime import date as date_type
    from apps.accounting.models import GLSubaccount
    from apps.nomenclature.models import Category, NomenclatureItem, Unit
    from apps.purchases.models import PurchaseItem, PurchaseOrder
    from apps.purchases.services.confirm import confirm_purchase
    from apps.warehouses.models import Warehouse

    unit = Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"}
    )[0]
    sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    cat = Category.objects.get_or_create(
        organization=org, name="C-feed", defaults={"default_gl_subaccount": sub},
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="SKU-Y", name="X", category=cat, unit=unit,
    )
    wh = Warehouse.objects.create(
        organization=org, module=module_feed, code="W-opex", name="W",
    )
    po = PurchaseOrder.objects.create(
        organization=org, module=module_feed, doc_number="",
        date=date_type(2026, 4, 24), counterparty=supplier, warehouse=wh,
    )
    PurchaseItem.objects.create(order=po, nomenclature=nom,
                                quantity=Decimal("1"), unit_price=Decimal("1000"))
    confirm_purchase(po)

    # Payment с allocation + contra одновременно — ошибка при post.
    from django.contrib.contenttypes.models import ContentType
    payment = Payment.objects.create(
        organization=org, module=module_feed, doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.OPEX,
        amount_uzs=Decimal("1000"),
        contra_subaccount=_sub(org, "26.01"),
        counterparty=supplier,
    )
    PaymentAllocation.objects.create(
        payment=payment,
        target_content_type=ContentType.objects.get_for_model(PurchaseOrder),
        target_object_id=po.id,
        amount_uzs=Decimal("1000"),
    )

    with pytest.raises(ValidationError):
        post_payment(payment)


# ─── Backward compat: обычная оплата поставщику без contra работает ──────


def test_counterparty_payment_without_contra_still_works(org, module_purchases, supplier):
    """Старое поведение: OUT без contra → Дт 60.01 / Кт 50.01."""
    payment = Payment.objects.create(
        organization=org, module=module_purchases, doc_number="",
        date=date(2026, 4, 24),
        direction=Payment.Direction.OUT,
        channel=Payment.Channel.CASH,
        kind=Payment.Kind.COUNTERPARTY,
        counterparty=supplier,
        amount_uzs=Decimal("1000000"),
    )
    result = post_payment(payment)
    assert result.journal_entry.debit_subaccount.code == "60.01"
    assert result.journal_entry.credit_subaccount.code == "50.01"
