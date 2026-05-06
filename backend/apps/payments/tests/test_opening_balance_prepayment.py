"""
Тесты синтетического Payment'а стартовой предоплаты
(kind=OPENING_BALANCE_PREPAYMENT) — последняя ветка opening_debt
рефакторинга.
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payments.models import Payment
from apps.payments.services.opening_balance_prepayment import (
    create_opening_balance_prepayment,
    sync_opening_balance_prepayment_for_counterparty,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.sales.models import SaleOrder
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="OBP-BUYER", kind="buyer",
        name="ООО Предоплатник",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="OBP-SUPP", kind="supplier",
        name="ООО ПерекинутыйАванс",
    )


# ── create ────────────────────────────────────────────────────────────────


def test_create_prepayment_for_buyer_creates_in_payment(org, buyer):
    p = create_opening_balance_prepayment(
        organization=org, counterparty=buyer,
        amount_uzs=Decimal("500000"), date_=date(2026, 1, 10),
    )
    assert p.kind == Payment.Kind.OPENING_BALANCE_PREPAYMENT
    assert p.direction == Payment.Direction.IN
    assert p.status == Payment.Status.POSTED
    assert p.amount_uzs == Decimal("500000")
    assert p.journal_entry_id is None
    assert p.cash_subaccount_id is None
    assert p.doc_number.startswith("ОБП-2026-")


def test_create_prepayment_for_supplier_creates_out_payment(org, supplier):
    p = create_opening_balance_prepayment(
        organization=org, counterparty=supplier,
        amount_uzs=Decimal("300000"), date_=date(2026, 1, 10),
    )
    assert p.direction == Payment.Direction.OUT
    assert p.status == Payment.Status.POSTED
    assert p.journal_entry_id is None


def test_create_prepayment_rejects_zero(org, buyer):
    with pytest.raises(ValueError, match="должен быть > 0"):
        create_opening_balance_prepayment(
            organization=org, counterparty=buyer,
            amount_uzs=Decimal("0"), date_=date.today(),
        )


# ── sync (negative opening_debt) ───────────────────────────────────────────


def test_sync_creates_prepayment_when_negative(org, buyer):
    buyer.opening_debt_uzs = Decimal("-500000")
    buyer.opening_balance_date = date(2026, 2, 1)
    buyer.save()

    p = sync_opening_balance_prepayment_for_counterparty(buyer)
    assert p is not None
    assert p.amount_uzs == Decimal("500000")
    assert p.direction == Payment.Direction.IN


def test_sync_idempotent(org, buyer):
    buyer.opening_debt_uzs = Decimal("-100000")
    buyer.save()
    p1 = sync_opening_balance_prepayment_for_counterparty(buyer)
    p2 = sync_opening_balance_prepayment_for_counterparty(buyer)
    assert p1.id == p2.id


def test_sync_skip_when_positive(org, buyer):
    buyer.opening_debt_uzs = Decimal("500000")
    buyer.save()
    p = sync_opening_balance_prepayment_for_counterparty(buyer)
    # Положительный opening_debt → препэймент не создаём.
    assert p is None


def test_sync_updates_unallocated_amount(org, buyer):
    buyer.opening_debt_uzs = Decimal("-100000")
    buyer.save()
    p = sync_opening_balance_prepayment_for_counterparty(buyer)

    buyer.opening_debt_uzs = Decimal("-250000")
    buyer.save()
    sync_opening_balance_prepayment_for_counterparty(buyer)
    p.refresh_from_db()
    assert p.amount_uzs == Decimal("250000")


def test_sync_cancels_when_zeroed(org, buyer):
    buyer.opening_debt_uzs = Decimal("-100000")
    buyer.save()
    p = sync_opening_balance_prepayment_for_counterparty(buyer)

    buyer.opening_debt_uzs = Decimal("0")
    buyer.save()
    sync_opening_balance_prepayment_for_counterparty(buyer)
    p.refresh_from_db()
    assert p.status == Payment.Status.CANCELLED


# ── apply_prepayment endpoint ─────────────────────────────────────────────


@pytest.fixture
def admin_user(org):
    user = User.objects.create_user(
        email="obp-admin@test.local", password="x", full_name="A",
    )
    membership = OrganizationMembership.objects.create(
        user=user, organization=org, is_active=True,
    )
    sales_module = Module.objects.get(code="sales")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=sales_module, level=AccessLevel.READ_WRITE,
    )
    core = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core, level=AccessLevel.READ_WRITE,
    )
    return user, membership


def test_apply_prepayment_to_sale_order(org, buyer, admin_user):
    user, _ = admin_user

    # Стартовая предоплата 500k
    prepay = create_opening_balance_prepayment(
        organization=org, counterparty=buyer,
        amount_uzs=Decimal("500000"), date_=date(2026, 1, 10),
    )

    # Новая продажа 200k (используем minimal SO без позиций — opening_balance kind)
    so = SaleOrder.objects.create(
        organization=org, customer=buyer,
        kind=SaleOrder.Kind.OPENING_BALANCE,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.UNPAID,
        doc_number="TEST-SO-1",
        date=date.today(),
        amount_uzs=Decimal("200000"),
    )

    from django.contrib.contenttypes.models import ContentType
    so_ct = ContentType.objects.get_for_model(SaleOrder)

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    resp = client.post(
        f"/api/payments/{prepay.id}/apply_prepayment/",
        {
            "target_content_type": so_ct.id,
            "target_object_id": str(so.id),
            "amount_uzs": "200000",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    so.refresh_from_db()
    assert so.paid_amount_uzs == Decimal("200000")
    assert so.payment_status == SaleOrder.PaymentStatus.PAID

    # Проверим что после повторной попытки применить ещё 350k получим ошибку
    # (осталось только 300k свободного кредита).
    so2 = SaleOrder.objects.create(
        organization=org, customer=buyer,
        kind=SaleOrder.Kind.OPENING_BALANCE,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.UNPAID,
        doc_number="TEST-SO-2",
        date=date.today(),
        amount_uzs=Decimal("400000"),
    )
    resp2 = client.post(
        f"/api/payments/{prepay.id}/apply_prepayment/",
        {
            "target_content_type": so_ct.id,
            "target_object_id": str(so2.id),
            "amount_uzs": "350000",
        },
        format="json",
    )
    assert resp2.status_code == 400
    assert "свободного кредита" in str(resp2.content, "utf-8")


def test_apply_prepayment_rejects_wrong_direction(org, buyer, admin_user):
    user, _ = admin_user
    prepay = create_opening_balance_prepayment(
        organization=org, counterparty=buyer,
        amount_uzs=Decimal("100000"), date_=date.today(),
    )

    # Попытаемся применить IN-предоплату к PurchaseOrder — это OUT-документ,
    # должно отлететь.
    from django.contrib.contenttypes.models import ContentType
    from apps.purchases.models import PurchaseOrder
    po_ct = ContentType.objects.get_for_model(PurchaseOrder)

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    resp = client.post(
        f"/api/payments/{prepay.id}/apply_prepayment/",
        {
            "target_content_type": po_ct.id,
            "target_object_id": "00000000-0000-0000-0000-000000000000",
            "amount_uzs": "50000",
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "SaleOrder" in str(resp.content, "utf-8")


# ── Counterparty viewset auto-creates prepayment ──────────────────────────


def test_counterparty_create_with_negative_opening_creates_prepayment(
    org, admin_user,
):
    user, _ = admin_user
    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)

    resp = client.post(
        "/api/counterparties/",
        {
            "code": "AUTO-OBP", "name": "Авто-предоплата", "kind": "buyer",
            "opening_debt_uzs": "-300000",
            "opening_balance_date": "2026-04-01",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    cp = Counterparty.objects.get(code="AUTO-OBP")
    p = Payment.objects.get(
        counterparty=cp, kind=Payment.Kind.OPENING_BALANCE_PREPAYMENT,
    )
    assert p.amount_uzs == Decimal("300000")
    assert p.direction == Payment.Direction.IN


def test_debt_summary_exposes_free_credit(org, buyer, admin_user):
    user, _ = admin_user
    create_opening_balance_prepayment(
        organization=org, counterparty=buyer,
        amount_uzs=Decimal("750000"), date_=date(2026, 1, 1),
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.credentials(HTTP_X_ORGANIZATION_CODE=org.code)
    resp = client.get(f"/api/counterparties/{buyer.id}/debt_summary/")
    assert resp.status_code == 200
    data = resp.json()
    assert "prepayments" in data
    assert len(data["prepayments"]) == 1
    assert Decimal(data["prepayments"][0]["free_uzs"]) == Decimal("750000")
    assert Decimal(data["prepayments_total_free_uzs"]) == Decimal("750000")
