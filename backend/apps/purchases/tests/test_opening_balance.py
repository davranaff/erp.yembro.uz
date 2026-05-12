"""
Тесты для синтетических PurchaseOrder со стартовым долгом поставщику
(`kind=OPENING_BALANCE`).

Симметрия с apps/sales/tests/test_opening_balance.py — там покупатели,
здесь поставщики.
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.purchases.models import PurchaseOrder
from apps.purchases.services.opening_balance import (
    create_opening_balance_purchase,
    sync_opening_balance_for_supplier,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="OB-SUPP-1", kind="supplier",
        name="ООО Поставщик",
    )


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="OB-BUYR-X", kind="buyer", name="Клиент",
    )


# ── create_opening_balance_purchase ──────────────────────────────────────


def test_create_opening_balance_purchase_positive(org, supplier):
    po = create_opening_balance_purchase(
        organization=org,
        counterparty=supplier,
        amount_uzs=Decimal("400000"),
        date_=date(2026, 1, 10),
    )
    assert po.kind == PurchaseOrder.Kind.OPENING_BALANCE
    assert po.status == PurchaseOrder.Status.CONFIRMED
    assert po.payment_status == PurchaseOrder.PaymentStatus.UNPAID
    assert po.amount_uzs == Decimal("400000")
    assert po.module_id is None
    assert po.warehouse_id is None
    assert po.doc_number.startswith("OPN-AP-2026-")
    assert po.date == date(2026, 1, 10)


def test_create_opening_balance_purchase_rejects_zero(org, supplier):
    with pytest.raises(ValueError, match="должен быть > 0"):
        create_opening_balance_purchase(
            organization=org, counterparty=supplier,
            amount_uzs=Decimal("0"), date_=date.today(),
        )


def test_create_opening_balance_purchase_rejects_buyer(org, buyer):
    with pytest.raises(ValueError, match="kind=supplier"):
        create_opening_balance_purchase(
            organization=org, counterparty=buyer,
            amount_uzs=Decimal("100"), date_=date.today(),
        )


# ── sync_opening_balance_for_supplier ────────────────────────────────────


def test_sync_creates_po_when_first_setting_debt(org, supplier):
    supplier.opening_debt_uzs = Decimal("250000")
    supplier.opening_balance_date = date(2026, 2, 5)
    supplier.save()

    po = sync_opening_balance_for_supplier(supplier)
    assert po is not None
    assert po.amount_uzs == Decimal("250000")
    assert po.date == date(2026, 2, 5)


def test_sync_supplier_idempotent(org, supplier):
    supplier.opening_debt_uzs = Decimal("100000")
    supplier.save()

    po1 = sync_opening_balance_for_supplier(supplier)
    po2 = sync_opening_balance_for_supplier(supplier)
    assert po1.id == po2.id


def test_sync_updates_unpaid_supplier_amount(org, supplier):
    supplier.opening_debt_uzs = Decimal("100000")
    supplier.save()
    po = sync_opening_balance_for_supplier(supplier)

    supplier.opening_debt_uzs = Decimal("180000")
    supplier.save()
    sync_opening_balance_for_supplier(supplier)
    po.refresh_from_db()
    assert po.amount_uzs == Decimal("180000")


def test_sync_does_not_touch_paid_supplier_po(org, supplier):
    supplier.opening_debt_uzs = Decimal("100000")
    supplier.save()
    po = sync_opening_balance_for_supplier(supplier)
    po.paid_amount_uzs = Decimal("40000")
    po.payment_status = PurchaseOrder.PaymentStatus.PARTIAL
    po.save()

    supplier.opening_debt_uzs = Decimal("999999")
    supplier.save()
    sync_opening_balance_for_supplier(supplier)
    po.refresh_from_db()
    assert po.amount_uzs == Decimal("100000")


def test_sync_keeps_po_when_debt_zeroed_after_migration(org, supplier):
    """После материализации opening_debt → PurchaseOrder обнуление поля
    не отменяет реальный счёт автоматически. Отмена — явно через UI."""
    supplier.opening_debt_uzs = Decimal("100000")
    supplier.save()
    po = sync_opening_balance_for_supplier(supplier)

    supplier.opening_debt_uzs = Decimal("0")
    supplier.save()
    sync_opening_balance_for_supplier(supplier)
    po.refresh_from_db()
    assert po.status == PurchaseOrder.Status.CONFIRMED
    assert po.amount_uzs == Decimal("100000")


def test_sync_skips_buyer(org, buyer):
    buyer.opening_debt_uzs = Decimal("100000")
    buyer.save()
    po = sync_opening_balance_for_supplier(buyer)
    assert po is None


# ── ViewSet auto-creates PO for supplier ─────────────────────────────────


@pytest.fixture
def admin_user(org):
    user = User.objects.create_user(
        email="opbal-supp-admin@test.local", password="x", full_name="Admin",
    )
    membership = OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
    )
    core = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core, level=AccessLevel.READ_WRITE,
    )
    return user, membership


def test_counterparty_create_supplier_with_opening_debt_creates_po(org, admin_user):
    user, _ = admin_user
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)

    resp = client.post(
        "/api/counterparties/",
        {
            "code": "AUTO-SUPP-1", "name": "Авто-поставщик", "kind": "supplier",
            "opening_debt_uzs": "550000",
            "opening_balance_date": "2026-03-15",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    cp = Counterparty.objects.get(code="AUTO-SUPP-1")
    po = PurchaseOrder.objects.get(
        counterparty=cp, kind=PurchaseOrder.Kind.OPENING_BALANCE,
    )
    assert po.amount_uzs == Decimal("550000")
    assert po.date == date(2026, 3, 15)


def test_counterparty_balances_includes_supplier_opening_po(org, admin_user, supplier):
    """AP-баланс /api/counterparties/balances/ показывает синтетический PO."""
    user, _ = admin_user
    supplier.opening_debt_uzs = Decimal("777000")
    supplier.save()
    sync_opening_balance_for_supplier(supplier)

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    resp = client.get("/api/counterparties/balances/")
    assert resp.status_code == 200, resp.content
    data = resp.json()

    rows = [r for r in data["rows"] if r["counterparty_id"] == str(supplier.id)]
    assert len(rows) == 1
    assert Decimal(rows[0]["ap_uzs"]) == Decimal("777000")
