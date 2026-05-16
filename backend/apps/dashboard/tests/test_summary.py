"""
Smoke-тесты /api/dashboard/summary/ и /api/dashboard/cashflow/.
"""
import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user(org):
    u = User.objects.create(email="dash@y.local", full_name="D")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    # Финансовый KPI / cashflow требует ledger.r — даём, чтобы smoke-тесты
    # видели «сырое» содержимое endpoint'а. Отдельный кейс ниже проверяет
    # обратный сценарий — без ledger.
    ledger = Module.objects.get(code="ledger")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=ledger, level=AccessLevel.READ,
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_summary_shape(client):
    resp = client.get("/api/dashboard/summary/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "kpis" in body
    assert "production" in body
    assert "cash" in body

    kpis = body["kpis"]
    for k in [
        "period", "purchases_confirmed_uzs", "purchases_paid_uzs",
        "creditor_balance_uzs", "debtor_balance_uzs",
        "payments_in_uzs", "payments_out_uzs",
        "sales_revenue_uzs", "sales_invoiced_uzs", "sales_unpaid_uzs",
        "sales_cost_uzs", "sales_margin_uzs",
        "sales_forecast_uzs", "sales_overdue_loss_uzs",
        "active_batches", "transfers_pending",
        "purchases_drafts", "sales_drafts", "payments_drafts",
    ]:
        assert k in kpis, k

    assert "_total_uzs" in body["cash"]

    prod = body["production"]
    for k in [
        "matochnik_heads", "feedlot_heads",
        "incubation_runs", "incubation_eggs_loaded",
    ]:
        assert k in prod, k


def test_summary_sales_revenue_excludes_unpaid_debt(org):
    """Продажа с частичной оплатой: выручка — только оплаченная часть.
    Маржа cash-basis: paid - cost×(paid/amount).
    Непросроченный остаток — в sales_forecast_uzs.
    """
    from datetime import date, timedelta
    from decimal import Decimal

    from apps.counterparties.models import Counterparty
    from apps.dashboard.services import kpi_summary
    from apps.sales.models import SaleOrder
    from apps.warehouses.models import Warehouse

    fresh = Organization.objects.create(
        code="DASH-DEBT", name="Dashboard debt test",
        accounting_currency=org.accounting_currency,
    )
    m_sales = Module.objects.get(code="sales")
    warehouse = Warehouse.objects.create(
        organization=fresh, module=m_sales, code="WH-DD", name="Склад теста",
    )
    customer = Counterparty.objects.create(
        organization=fresh, code="C-DD", kind="buyer", name="Должник",
    )
    today = date.today()
    SaleOrder.objects.create(
        organization=fresh, doc_number="П-DD-1", date=today,
        module=m_sales, customer=customer, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.PARTIAL,
        amount_uzs=Decimal("1000000"),
        paid_amount_uzs=Decimal("300000"),
        cost_uzs=Decimal("400000"),
        due_date=today + timedelta(days=14),  # ещё не просрочен
    )

    kpis = kpi_summary(fresh, today=today)
    assert Decimal(kpis["sales_revenue_uzs"]) == Decimal("300000")    # оплачено
    assert Decimal(kpis["sales_invoiced_uzs"]) == Decimal("1000000")  # отгружено
    assert Decimal(kpis["sales_unpaid_uzs"]) == Decimal("700000")     # долг — отдельно
    assert Decimal(kpis["sales_cost_uzs"]) == Decimal("400000")
    # cash-basis margin = 300000 - 400000 * (300000/1000000) = 300000 - 120000 = 180000
    assert Decimal(kpis["sales_margin_uzs"]) == Decimal("180000")
    # Не просрочен → в прогнозе, не в убытках
    assert Decimal(kpis["sales_forecast_uzs"]) == Decimal("700000")
    assert Decimal(kpis["sales_overdue_loss_uzs"]) == Decimal("0")


def test_summary_overdue_goes_to_loss(org):
    """Продажа с due_date в прошлом и неполной оплатой: остаток попадает в
    sales_overdue_loss_uzs, а не в sales_forecast_uzs."""
    from datetime import date, timedelta
    from decimal import Decimal

    from apps.counterparties.models import Counterparty
    from apps.dashboard.services import kpi_summary
    from apps.sales.models import SaleOrder
    from apps.warehouses.models import Warehouse

    fresh = Organization.objects.create(
        code="DASH-LOSS", name="Dashboard loss test",
        accounting_currency=org.accounting_currency,
    )
    m_sales = Module.objects.get(code="sales")
    warehouse = Warehouse.objects.create(
        organization=fresh, module=m_sales, code="WH-DL", name="Склад теста",
    )
    customer = Counterparty.objects.create(
        organization=fresh, code="C-DL", kind="buyer", name="Просрочник",
    )
    today = date.today()
    SaleOrder.objects.create(
        organization=fresh, doc_number="П-DL-1", date=today,
        module=m_sales, customer=customer, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.PARTIAL,
        amount_uzs=Decimal("2000000"),
        paid_amount_uzs=Decimal("500000"),
        cost_uzs=Decimal("800000"),
        due_date=today - timedelta(days=1),  # просрочен вчера
    )

    kpis = kpi_summary(fresh, today=today)
    assert Decimal(kpis["sales_overdue_loss_uzs"]) == Decimal("1500000")  # 2M - 0.5M
    assert Decimal(kpis["sales_forecast_uzs"]) == Decimal("0")


def test_summary_purchases_paid_excludes_unpaid_debt(org):
    """Симметрия по закупкам: purchases_confirmed_uzs — полный объём закупок
    периода (начисление), purchases_paid_uzs — реально оплаченная поставщикам
    часть. Непогашенный долг по закупкам в «оплачено» не попадает."""
    from datetime import date
    from decimal import Decimal

    from apps.counterparties.models import Counterparty
    from apps.dashboard.services import kpi_summary
    from apps.purchases.models import PurchaseOrder
    from apps.warehouses.models import Warehouse

    # Свежая организация — чтобы агрегаты были детерминированы (без seed-данных).
    fresh = Organization.objects.create(
        code="DASH-AP", name="Dashboard AP test",
        accounting_currency=org.accounting_currency,
    )
    m_purchases = Module.objects.get(code="purchases")
    warehouse = Warehouse.objects.create(
        organization=fresh, module=m_purchases, code="WH-AP", name="Склад теста",
    )
    supplier = Counterparty.objects.create(
        organization=fresh, code="S-AP", kind="supplier", name="Поставщик",
    )
    PurchaseOrder.objects.create(
        organization=fresh, doc_number="З-AP-1", date=date.today(),
        module=m_purchases, counterparty=supplier, warehouse=warehouse,
        status=PurchaseOrder.Status.CONFIRMED,
        payment_status=PurchaseOrder.PaymentStatus.PARTIAL,
        amount_uzs=Decimal("800000"),
        paid_amount_uzs=Decimal("500000"),
    )

    kpis = kpi_summary(fresh)
    assert Decimal(kpis["purchases_confirmed_uzs"]) == Decimal("800000")  # начислено
    assert Decimal(kpis["purchases_paid_uzs"]) == Decimal("500000")       # оплачено


def test_summary_requires_org_header(user):
    api = APIClient()
    api.force_authenticate(user=user)
    resp = api.get("/api/dashboard/summary/")
    # Без header — ValidationError из OrganizationContextMixin
    assert resp.status_code == 400


def test_cashflow_default_30_days(client):
    resp = client.get("/api/dashboard/cashflow/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["days"] == 30
    assert len(body["points"]) == 30
    assert all("date" in p and "in_uzs" in p and "out_uzs" in p for p in body["points"])


def test_cashflow_custom_days(client):
    resp = client.get("/api/dashboard/cashflow/?days=7")
    assert resp.status_code == 200
    assert resp.json()["days"] == 7
    assert len(resp.json()["points"]) == 7


def test_cashflow_invalid_days_falls_back_to_30(client):
    resp = client.get("/api/dashboard/cashflow/?days=not-a-number")
    assert resp.status_code == 200
    assert resp.json()["days"] == 30


def test_cashflow_clamps_to_max_365(client):
    resp = client.get("/api/dashboard/cashflow/?days=99999")
    assert resp.status_code == 200
    assert resp.json()["days"] == 365


def test_head_slaughter_sees_only_accessible_production():
    """HEAD_SLAUGHTER has feedlot:r, slaughter:admin, sales:rw — no matochnik/incubation.
    production_summary must return None for matochnik and incubation tiles."""
    from apps.dashboard.services import production_summary
    from apps.organizations.models import Organization

    org = Organization.objects.get(code="DEFAULT")
    readable = {"slaughter", "feedlot", "sales", "core", "stock", "reports"}
    # Note: ledger intentionally absent (removed from role by Task 5 migration)

    prod = production_summary(org, readable_modules=readable)

    assert prod["matochnik_heads"] is None      # no matochnik access
    assert prod["incubation_runs"] is None      # no incubation access
    assert prod["incubation_eggs_loaded"] is None
    assert prod["feedlot_heads"] is not None    # feedlot:r → visible (int or 0)


def test_head_slaughter_drafts_scoped():
    """purchases_drafts is None (no purchases access), sales_drafts is int (sales:rw)."""
    from apps.dashboard.services import kpi_summary
    from apps.organizations.models import Organization

    org = Organization.objects.get(code="DEFAULT")
    readable = {"slaughter", "feedlot", "sales", "core", "stock", "reports"}

    kpis = kpi_summary(org, readable_modules=readable)

    assert kpis["purchases_drafts"] is None   # purchases not in readable
    assert kpis["payments_drafts"] is None    # ledger not in readable
    assert isinstance(kpis["sales_drafts"], int)  # sales:rw → visible


def test_unlimited_readable_modules_returns_all_fields():
    """readable_modules=None (superuser/org-admin) → all fields are non-None."""
    from apps.dashboard.services import production_summary, kpi_summary
    from apps.organizations.models import Organization

    org = Organization.objects.get(code="DEFAULT")

    prod = production_summary(org, readable_modules=None)
    kpis = kpi_summary(org, readable_modules=None)

    for key in ("matochnik_heads", "feedlot_heads", "incubation_runs", "incubation_eggs_loaded"):
        assert isinstance(prod[key], int), f"production.{key} should be int (not None) for unlimited scope"
    for key in ("purchases_drafts", "sales_drafts", "payments_drafts"):
        assert isinstance(kpis[key], int), f"kpis.{key} should be int (not None) for unlimited scope"
