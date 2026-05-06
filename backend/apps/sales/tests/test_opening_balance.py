"""
Тесты для синтетических SaleOrder со стартовым долгом миграции
(`kind=OPENING_BALANCE`).

Покрывают:
  - create_opening_balance_sale: положительный путь + валидации
  - sync_opening_balance_for_counterparty: создать / обновить / отменить
  - aging_report включает OPENING_BALANCE SO как обычный счёт
  - credit_check тянет OPENING_BALANCE из aging (без + opening костыля)
  - record_payment работает на OPENING_BALANCE SO частичной оплатой
  - CounterpartyViewSet авто-создаёт SO при выставлении opening_debt > 0
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.modules.models import Module
from apps.sales.models import SaleOrder
from apps.sales.services.aging import compute_aging_report
from apps.sales.services.credit_check import check_customer_credit
from apps.sales.services.opening_balance import (
    create_opening_balance_sale,
    sync_opening_balance_for_counterparty,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="OB-BUYER", kind="buyer", name="ООО ОткрытыйДолг",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="OB-SUPP", kind="supplier", name="Поставщик",
    )


# ── create_opening_balance_sale ──────────────────────────────────────────


def test_create_opening_balance_sale_positive(org, buyer):
    so = create_opening_balance_sale(
        organization=org,
        customer=buyer,
        amount_uzs=Decimal("500000"),
        date_=date(2026, 1, 15),
    )
    assert so.kind == SaleOrder.Kind.OPENING_BALANCE
    assert so.status == SaleOrder.Status.CONFIRMED
    assert so.payment_status == SaleOrder.PaymentStatus.UNPAID
    assert so.amount_uzs == Decimal("500000")
    assert so.module_id is None
    assert so.warehouse_id is None
    assert so.doc_number.startswith("OPN-2026-")
    assert so.date == date(2026, 1, 15)
    assert so.due_date == date(2026, 1, 15)


def test_create_opening_balance_rejects_zero(org, buyer):
    with pytest.raises(ValueError, match="должен быть > 0"):
        create_opening_balance_sale(
            organization=org, customer=buyer,
            amount_uzs=Decimal("0"), date_=date.today(),
        )


def test_create_opening_balance_rejects_supplier(org, supplier):
    with pytest.raises(ValueError, match="kind=buyer"):
        create_opening_balance_sale(
            organization=org, customer=supplier,
            amount_uzs=Decimal("100"), date_=date.today(),
        )


# ── sync_opening_balance_for_counterparty ────────────────────────────────


def test_sync_creates_so_when_first_setting_debt(org, buyer):
    buyer.opening_debt_uzs = Decimal("300000")
    buyer.opening_balance_date = date(2026, 2, 1)
    buyer.save()

    so = sync_opening_balance_for_counterparty(buyer)
    assert so is not None
    assert so.amount_uzs == Decimal("300000")
    assert so.date == date(2026, 2, 1)


def test_sync_is_idempotent(org, buyer):
    buyer.opening_debt_uzs = Decimal("100000")
    buyer.save()

    so1 = sync_opening_balance_for_counterparty(buyer)
    so2 = sync_opening_balance_for_counterparty(buyer)
    assert so1.id == so2.id
    assert SaleOrder.objects.filter(
        kind=SaleOrder.Kind.OPENING_BALANCE, customer=buyer,
    ).count() == 1


def test_sync_updates_amount_when_unpaid(org, buyer):
    buyer.opening_debt_uzs = Decimal("100000")
    buyer.save()
    so = sync_opening_balance_for_counterparty(buyer)
    assert so.amount_uzs == Decimal("100000")

    # Админ корректирует долг — SO ещё не оплачен, обновляем.
    buyer.opening_debt_uzs = Decimal("250000")
    buyer.save()
    so2 = sync_opening_balance_for_counterparty(buyer)
    assert so2.id == so.id
    assert so2.amount_uzs == Decimal("250000")


def test_sync_does_not_touch_partially_paid_so(org, buyer):
    buyer.opening_debt_uzs = Decimal("100000")
    buyer.save()
    so = sync_opening_balance_for_counterparty(buyer)
    so.paid_amount_uzs = Decimal("30000")
    so.payment_status = SaleOrder.PaymentStatus.PARTIAL
    so.save()

    # После оплаты долг «де-факто» 70k, но opening_debt_uzs не должен
    # переписать amount уже оплачиваемого SO — это сломает аудит.
    buyer.opening_debt_uzs = Decimal("999999")
    buyer.save()
    sync_opening_balance_for_counterparty(buyer)
    so.refresh_from_db()
    assert so.amount_uzs == Decimal("100000")


def test_sync_cancels_unpaid_so_when_debt_zeroed(org, buyer):
    buyer.opening_debt_uzs = Decimal("100000")
    buyer.save()
    so = sync_opening_balance_for_counterparty(buyer)

    buyer.opening_debt_uzs = Decimal("0")
    buyer.save()
    sync_opening_balance_for_counterparty(buyer)
    so.refresh_from_db()
    assert so.status == SaleOrder.Status.CANCELLED


def test_sync_skips_supplier(org, supplier):
    supplier.opening_debt_uzs = Decimal("100000")
    supplier.save()
    so = sync_opening_balance_for_counterparty(supplier)
    assert so is None
    assert SaleOrder.objects.filter(customer=supplier).count() == 0


# ── aging_report includes synthetic SO ───────────────────────────────────


def test_aging_includes_opening_balance_so(org, buyer):
    create_opening_balance_sale(
        organization=org, customer=buyer,
        amount_uzs=Decimal("700000"),
        date_=date.today() - timedelta(days=45),
    )

    report = compute_aging_report(org, customer_id=str(buyer.id))
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.total == Decimal("700000")
    assert row.b_31_60 == Decimal("700000")
    assert row.has_overdue is True
    assert row.oldest_overdue_days == 45


# ── credit_check uses aging-only path (no + opening) ─────────────────────


def test_credit_check_via_synthetic_so(org, buyer):
    buyer.credit_limit_uzs = Decimal("1000000")
    buyer.opening_debt_uzs = Decimal("800000")
    buyer.save()
    sync_opening_balance_for_counterparty(buyer)

    # Текущий долг по aging = 800k. Лимит 1M. Новая продажа на 250k → 1.05M > 1M → блок.
    res = check_customer_credit(
        organization=org, customer=buyer, new_sale_uzs=Decimal("250000"),
    )
    assert res.ok is False
    assert any("кредитный лимит" in r.lower() for r in res.reasons)
    assert res.current_debt_uzs == Decimal("800000")


def test_credit_check_no_double_count(org, buyer):
    """Проверяем что opening_debt не суммируется дважды (старый + opening
    костыль был бы 1.6M вместо 800k)."""
    buyer.credit_limit_uzs = Decimal("1000000")
    buyer.opening_debt_uzs = Decimal("800000")
    buyer.save()
    sync_opening_balance_for_counterparty(buyer)

    res = check_customer_credit(organization=org, customer=buyer)
    assert res.current_debt_uzs == Decimal("800000")  # не 1.6M!


# ── record_payment on synthetic SO ───────────────────────────────────────


@pytest.fixture
def admin_user(org):
    user = User.objects.create_user(
        email="opbal-admin@test.local", password="x", full_name="Admin",
    )
    membership = OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
    )
    sales_module = Module.objects.get(code="sales")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=sales_module, level=AccessLevel.READ_WRITE,
    )
    return user, membership


def test_record_payment_partial_on_opening_balance_so(org, buyer, admin_user):
    user, _ = admin_user
    so = create_opening_balance_sale(
        organization=org, customer=buyer,
        amount_uzs=Decimal("500000"),
        date_=date.today() - timedelta(days=10),
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)

    resp = client.post(
        f"/api/sales/orders/{so.id}/record_payment/",
        {"channel": "cash", "amount_uzs": "200000"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    so.refresh_from_db()
    assert so.paid_amount_uzs == Decimal("200000")
    assert so.payment_status == SaleOrder.PaymentStatus.PARTIAL

    # Доплачиваем остаток — статус → PAID.
    resp2 = client.post(
        f"/api/sales/orders/{so.id}/record_payment/",
        {"channel": "cash", "amount_uzs": "300000"},
        format="json",
    )
    assert resp2.status_code == 200, resp2.content
    so.refresh_from_db()
    assert so.paid_amount_uzs == Decimal("500000")
    assert so.payment_status == SaleOrder.PaymentStatus.PAID


# ── ViewSet auto-creates SO ──────────────────────────────────────────────


def test_counterparty_create_with_opening_debt_creates_so(org, admin_user):
    user, membership = admin_user
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)

    # Нужен RW на core
    core = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core, level=AccessLevel.READ_WRITE,
    )

    resp = client.post(
        "/api/counterparties/",
        {
            "code": "AUTO-OB-1", "name": "Авто-долг", "kind": "buyer",
            "opening_debt_uzs": "750000",
            "opening_balance_date": "2026-03-01",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    cp = Counterparty.objects.get(code="AUTO-OB-1")
    so = SaleOrder.objects.get(customer=cp, kind=SaleOrder.Kind.OPENING_BALANCE)
    assert so.amount_uzs == Decimal("750000")
    assert so.date == date(2026, 3, 1)


def test_counterparty_patch_opening_debt_updates_so(org, admin_user):
    user, membership = admin_user
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    core = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core, level=AccessLevel.READ_WRITE,
    )

    cp = Counterparty.objects.create(
        organization=org, code="AUTO-OB-2", kind="buyer", name="Будем менять",
    )
    resp = client.patch(
        f"/api/counterparties/{cp.id}/",
        {"opening_debt_uzs": "100000"}, format="json",
    )
    assert resp.status_code == 200, resp.content
    so = SaleOrder.objects.get(customer=cp, kind=SaleOrder.Kind.OPENING_BALANCE)
    assert so.amount_uzs == Decimal("100000")

    # Меняем сумму — должен подхватить.
    resp2 = client.patch(
        f"/api/counterparties/{cp.id}/",
        {"opening_debt_uzs": "150000"}, format="json",
    )
    assert resp2.status_code == 200, resp2.content
    so.refresh_from_db()
    assert so.amount_uzs == Decimal("150000")
