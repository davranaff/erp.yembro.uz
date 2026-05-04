"""
Тесты `check_customer_credit` + интеграция с `confirm_sale`.

Покрывают:
  - оба лимита NULL → ok
  - только credit_limit задан, current+new <= лимита → ok
  - credit_limit превышен → not ok с reason
  - max_overdue_days превышен → not ok с reason
  - оба лимита превышены → 2 reason
  - confirm_sale блокируется при ok=False
  - force_credit_override обходит блок
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.batches.models import Batch
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import SaleConfirmError, confirm_sale
from apps.sales.services.credit_check import check_customer_credit
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="K-CR-1", kind="buyer", name="Тест-клиент",
    )


@pytest.fixture
def warehouse(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter, code="СК-CR", name="Скл CR",
    )


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_meat(org):
    from apps.accounting.models import GLSubaccount
    sub = GLSubaccount.objects.get(account__organization=org, code="43.01")
    return Category.objects.get_or_create(
        organization=org, name="Мясо CR",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def chicken(org, cat_meat, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ТШК-CR", name="Тушка CR",
        category=cat_meat, unit=unit_kg,
    )


@pytest.fixture
def stocked_batch(org, m_slaughter, chicken, unit_kg):
    return Batch.objects.create(
        organization=org, doc_number="П-CR-001",
        nomenclature=chicken, unit=unit_kg,
        origin_module=m_slaughter, current_module=m_slaughter,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("100000"),
        started_at=date.today(),
    )


def _existing_unpaid_sale(org, m_slaughter, buyer, warehouse, *, amount, days_overdue):
    """Создаёт CONFIRMED-продажу с заданной суммой и просрочкой."""
    sale_date = date.today() - timedelta(days=days_overdue)
    return SaleOrder.objects.create(
        organization=org, doc_number=f"П-CR-EXT-{days_overdue}-{amount}",
        date=sale_date, due_date=sale_date,
        module=m_slaughter, customer=buyer, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.UNPAID,
        amount_uzs=Decimal(amount),
    )


def _draft_sale(org, m_sales, buyer, warehouse, chicken, batch, *, qty, price):
    """Создаёт DRAFT с одной item для теста confirm_sale."""
    order = SaleOrder.objects.create(
        organization=org, doc_number="",
        date=date.today(),
        module=m_sales, customer=buyer, warehouse=warehouse,
        status=SaleOrder.Status.DRAFT,
    )
    SaleItem.objects.create(
        order=order, nomenclature=chicken, batch=batch,
        quantity=Decimal(qty), unit_price_uzs=Decimal(price),
    )
    return order


# ─── unit-тесты сервиса ──────────────────────────────────────────────────


def test_credit_check_no_limits_returns_ok(org, buyer):
    assert buyer.credit_limit_uzs is None
    assert buyer.max_overdue_days is None
    result = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("999999999"),
    )
    assert result.ok is True
    assert result.reasons == []


def test_credit_limit_pass_when_within_limit(
    org, m_slaughter, buyer, warehouse,
):
    buyer.credit_limit_uzs = Decimal("1000000")
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="300000", days_overdue=10)
    result = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("500000"),
    )
    assert result.ok is True
    assert result.current_debt_uzs == Decimal("300000")


def test_credit_limit_blocks_when_exceeded(
    org, m_slaughter, buyer, warehouse,
):
    buyer.credit_limit_uzs = Decimal("1000000")
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="800000", days_overdue=5)
    result = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("500000"),
    )
    assert result.ok is False
    assert any("кредитный лимит" in r.lower() for r in result.reasons)


def test_max_overdue_blocks_when_exceeded(
    org, m_slaughter, buyer, warehouse,
):
    buyer.max_overdue_days = 30
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="100", days_overdue=45)
    result = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("100"),
    )
    assert result.ok is False
    assert any("просрочки" in r.lower() for r in result.reasons)


def test_both_limits_violated_yields_two_reasons(
    org, m_slaughter, buyer, warehouse,
):
    buyer.credit_limit_uzs = Decimal("100")
    buyer.max_overdue_days = 30
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="500", days_overdue=60)
    result = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("100"),
    )
    assert result.ok is False
    assert len(result.reasons) == 2


# ─── интеграция с confirm_sale ────────────────────────────────────────────


def test_confirm_sale_blocked_by_credit_limit(
    org, m_slaughter, m_sales, buyer, warehouse, chicken, stocked_batch,
):
    buyer.credit_limit_uzs = Decimal("100000")
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="80000", days_overdue=5)
    draft = _draft_sale(org, m_sales, buyer, warehouse, chicken, stocked_batch,
                        qty="10", price="5000")  # 50k → 80k+50k > 100k
    with pytest.raises(SaleConfirmError) as exc_info:
        confirm_sale(draft)
    assert "credit" in str(exc_info.value.message_dict).lower() or "кредит" in str(exc_info.value.message_dict).lower()


def test_confirm_sale_with_force_override_succeeds(
    org, m_slaughter, m_sales, buyer, warehouse, chicken, stocked_batch,
):
    buyer.credit_limit_uzs = Decimal("100000")
    buyer.save()
    _existing_unpaid_sale(org, m_slaughter, buyer, warehouse,
                          amount="80000", days_overdue=5)
    draft = _draft_sale(org, m_sales, buyer, warehouse, chicken, stocked_batch,
                        qty="10", price="5000")
    # С override — проводится
    result = confirm_sale(draft, force_credit_override=True)
    draft.refresh_from_db()
    assert draft.status == SaleOrder.Status.CONFIRMED
    assert result.revenue_journal is not None


def test_confirm_sale_passes_when_within_limits(
    org, m_slaughter, m_sales, buyer, warehouse, chicken, stocked_batch,
):
    buyer.credit_limit_uzs = Decimal("1000000")
    buyer.max_overdue_days = 30
    buyer.save()
    draft = _draft_sale(org, m_sales, buyer, warehouse, chicken, stocked_batch,
                        qty="10", price="5000")
    confirm_sale(draft)
    draft.refresh_from_db()
    assert draft.status == SaleOrder.Status.CONFIRMED
