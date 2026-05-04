"""
Тесты `compute_aging_report` и `/api/sales/orders/aging/`.

Покрывают:
  - бакетирование по due_date (current/0-30/31-60/61-90/90+)
  - fallback на sale.date если due_date=NULL
  - частичная оплата уменьшает outstanding в бакете
  - PAID-продажи не попадают в отчёт
  - DRAFT/CANCELLED не попадают (только CONFIRMED)
  - агрегация по контрагенту (несколько заказов одного клиента)
  - сортировка по total убыванию (топ должников сверху)
  - per-customer фильтр через ?customer=
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.sales.models import SaleOrder
from apps.sales.services.aging import (
    _bucket_for_days_overdue,
    compute_aging_report,
)
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def warehouse(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter,
        code="СК-AGE", name="Склад aging-теста",
    )


@pytest.fixture
def buyer1(org):
    return Counterparty.objects.create(
        organization=org, code="K-AGE-1", kind="buyer", name="ООО Восток",
    )


@pytest.fixture
def buyer2(org):
    return Counterparty.objects.create(
        organization=org, code="K-AGE-2", kind="buyer", name="ИП Запад",
    )


def _mk_sale(
    org, m, customer, warehouse, *, sale_date, due_date, amount,
    paid=Decimal("0"), doc=None,
):
    """Создаёт CONFIRMED-продажу напрямую (минуя confirm_sale) — для
    aging-теста нам нужны только агрегатные поля, без реальных движений."""
    return SaleOrder.objects.create(
        organization=org, doc_number=doc or f"П-AGE-{customer.code}-{sale_date}",
        date=sale_date, due_date=due_date,
        module=m, customer=customer, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=(
            SaleOrder.PaymentStatus.PARTIAL if 0 < paid < amount
            else SaleOrder.PaymentStatus.UNPAID if paid == 0
            else SaleOrder.PaymentStatus.PAID
        ),
        amount_uzs=amount,
        paid_amount_uzs=paid,
    )


# ─── unit-тесты: бакетирование ────────────────────────────────────────────


def test_bucket_current_when_not_overdue():
    assert _bucket_for_days_overdue(-5) == "current"
    assert _bucket_for_days_overdue(0) == "current"


def test_bucket_0_30():
    assert _bucket_for_days_overdue(1) == "b_0_30"
    assert _bucket_for_days_overdue(15) == "b_0_30"
    assert _bucket_for_days_overdue(30) == "b_0_30"


def test_bucket_31_60():
    assert _bucket_for_days_overdue(31) == "b_31_60"
    assert _bucket_for_days_overdue(60) == "b_31_60"


def test_bucket_61_90():
    assert _bucket_for_days_overdue(61) == "b_61_90"
    assert _bucket_for_days_overdue(90) == "b_61_90"


def test_bucket_90_plus():
    assert _bucket_for_days_overdue(91) == "b_90_plus"
    assert _bucket_for_days_overdue(365) == "b_90_plus"


# ─── service-тесты ───────────────────────────────────────────────────────


def test_aging_uses_due_date_when_set(org, m_slaughter, buyer1, warehouse):
    today = date(2026, 6, 1)
    # due_date = 2026-05-15 → 17 дней просрочки → bucket 0-30
    _mk_sale(
        org, m_slaughter, buyer1, warehouse,
        sale_date=date(2026, 5, 1), due_date=date(2026, 5, 15),
        amount=Decimal("1000000"),
    )
    report = compute_aging_report(org, today=today)
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.code == "K-AGE-1"
    assert row.b_0_30 == Decimal("1000000")
    assert row.current == Decimal("0")
    assert row.total == Decimal("1000000")
    assert row.has_overdue is True
    assert row.oldest_overdue_days == 17


def test_aging_falls_back_to_sale_date_when_no_due(org, m_slaughter, buyer1, warehouse):
    """Без due_date — basis = sale date (immediate payment terms)."""
    today = date(2026, 6, 1)
    _mk_sale(
        org, m_slaughter, buyer1, warehouse,
        sale_date=date(2026, 4, 1),  # 61 день просрочки → 61-90
        due_date=None,
        amount=Decimal("500000"),
    )
    report = compute_aging_report(org, today=today)
    row = report.rows[0]
    assert row.b_61_90 == Decimal("500000")
    assert row.oldest_overdue_days == 61


def test_aging_partial_payment_reduces_outstanding(org, m_slaughter, buyer1, warehouse):
    today = date(2026, 6, 1)
    _mk_sale(
        org, m_slaughter, buyer1, warehouse,
        sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
        amount=Decimal("1000000"), paid=Decimal("300000"),
    )
    report = compute_aging_report(org, today=today)
    # outstanding = 700k, 31 день просрочки → b_31_60
    assert report.rows[0].b_31_60 == Decimal("700000")
    assert report.rows[0].total == Decimal("700000")


def test_aging_excludes_paid_orders(org, m_slaughter, buyer1, warehouse):
    today = date(2026, 6, 1)
    SaleOrder.objects.create(
        organization=org, doc_number="П-AGE-PAID-1",
        date=date(2026, 4, 1), due_date=date(2026, 4, 15),
        module=m_slaughter, customer=buyer1, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.PAID,
        amount_uzs=Decimal("100000"),
        paid_amount_uzs=Decimal("100000"),
    )
    report = compute_aging_report(org, today=today)
    assert report.rows == []
    assert report.summary["total"] == "0"


def test_aging_excludes_draft_and_cancelled(org, m_slaughter, buyer1, warehouse):
    today = date(2026, 6, 1)
    for status in (SaleOrder.Status.DRAFT, SaleOrder.Status.CANCELLED):
        SaleOrder.objects.create(
            organization=org, doc_number=f"П-AGE-{status}",
            date=date(2026, 4, 1), due_date=date(2026, 4, 15),
            module=m_slaughter, customer=buyer1, warehouse=warehouse,
            status=status,
            payment_status=SaleOrder.PaymentStatus.UNPAID,
            amount_uzs=Decimal("100000"),
        )
    report = compute_aging_report(org, today=today)
    assert report.rows == []


def test_aging_aggregates_by_customer(org, m_slaughter, buyer1, warehouse):
    """Несколько заказов одного клиента → одна строка с суммой по бакетам."""
    today = date(2026, 6, 1)
    # Три заказа в разных бакетах
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 5, 25), due_date=date(2026, 5, 25),
             amount=Decimal("100000"), doc="П-AGE-A1")  # 7 дней → 0-30
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 4, 1), due_date=date(2026, 4, 1),
             amount=Decimal("200000"), doc="П-AGE-A2")  # 61 день → 61-90
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 1, 1), due_date=date(2026, 1, 1),
             amount=Decimal("300000"), doc="П-AGE-A3")  # 151 → 90+

    report = compute_aging_report(org, today=today)
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.b_0_30 == Decimal("100000")
    assert row.b_61_90 == Decimal("200000")
    assert row.b_90_plus == Decimal("300000")
    assert row.total == Decimal("600000")
    assert row.orders_count == 3
    assert row.oldest_overdue_days == 151


def test_aging_sorts_by_total_desc(org, m_slaughter, buyer1, buyer2, warehouse):
    today = date(2026, 6, 1)
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
             amount=Decimal("100"), doc="П-AGE-S1")
    _mk_sale(org, m_slaughter, buyer2, warehouse,
             sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
             amount=Decimal("999999"), doc="П-AGE-S2")
    report = compute_aging_report(org, today=today)
    assert [r.code for r in report.rows] == ["K-AGE-2", "K-AGE-1"]


def test_aging_summary_aggregates_buckets(org, m_slaughter, buyer1, buyer2, warehouse):
    today = date(2026, 6, 1)
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 5, 25), due_date=date(2026, 5, 25),
             amount=Decimal("100"), doc="П-AGE-S3")  # 0-30
    _mk_sale(org, m_slaughter, buyer2, warehouse,
             sale_date=date(2026, 1, 1), due_date=date(2026, 1, 1),
             amount=Decimal("500"), doc="П-AGE-S4")  # 90+
    report = compute_aging_report(org, today=today)
    # Сравниваем как Decimal, чтобы не споткнуться о "100" vs "100.00"
    assert Decimal(report.summary["b_0_30"]) == Decimal("100")
    assert Decimal(report.summary["b_90_plus"]) == Decimal("500")
    assert Decimal(report.summary["total"]) == Decimal("600")
    assert report.summary["customers_count"] == 2
    assert report.summary["overdue_customers_count"] == 2


def test_aging_customer_filter(org, m_slaughter, buyer1, buyer2, warehouse):
    today = date(2026, 6, 1)
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
             amount=Decimal("100"), doc="П-AGE-CF1")
    _mk_sale(org, m_slaughter, buyer2, warehouse,
             sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
             amount=Decimal("200"), doc="П-AGE-CF2")
    report = compute_aging_report(org, today=today, customer_id=str(buyer1.id))
    assert len(report.rows) == 1
    assert report.rows[0].code == "K-AGE-1"


# ─── API-тест ────────────────────────────────────────────────────────────


def test_api_aging_endpoint_returns_report(
    org, m_sales, m_slaughter, buyer1, warehouse,
):
    _mk_sale(org, m_slaughter, buyer1, warehouse,
             sale_date=date.today() - timedelta(days=15),
             due_date=date.today() - timedelta(days=15),
             amount=Decimal("777000"), doc="П-AGE-API-1")

    u = User.objects.create(email="aging@y.local", full_name="A")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_sales, level=AccessLevel.READ,
    )

    api = APIClient()
    api.force_authenticate(user=u)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    resp = api.get("/api/sales/orders/aging/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert "rows" in data and "summary" in data and "as_of" in data
    assert len(data["rows"]) == 1
    assert data["rows"][0]["code"] == "K-AGE-1"
    assert Decimal(data["rows"][0]["b_0_30"]) == Decimal("777000")
