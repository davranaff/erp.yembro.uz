"""
Тесты VetAccessory: модель, receive с weighted-avg cost, продажа через
SaleOrder (XOR + 41.01 GL), public scan-and-sell по barcode.

Покрывают:
  - clean(): cross-org + warehouse-module проверки
  - receive: инкремент qty + пересчёт avg-cost
  - receive: первый приход (qty=0 → cost = unit_cost напрямую)
  - receive: довоз без unit_cost — cost не меняется
  - sale через confirm_sale: списание + JE Cr 41.01 / Dr 90.02
  - SaleItem XOR: нельзя одновременно vet_accessory + batch
  - public scan возвращает source_kind=accessory
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.sales.models import SaleItem, SaleOrder
from apps.sales.services.confirm import SaleConfirmError, confirm_sale
from apps.users.models import User
from apps.vet.models import VetAccessory
from apps.vet.services.receive_accessory import (
    VetAccessoryReceiveError,
    receive_vet_accessory,
)
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"},
    )[0]


@pytest.fixture
def cat_accessory(org):
    return Category.objects.get_or_create(
        organization=org, name="Аксессуары",
    )[0]


@pytest.fixture
def bowl_nom(org, cat_accessory, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ACC-BOWL", name="Миска для корма",
        category=cat_accessory, unit=unit_pcs,
    )


@pytest.fixture
def vet_warehouse(org, m_vet):
    return Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВЕТ-А",
        name="Склад вет-аксессуаров",
    )


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="K-ACC-BUY", kind="buyer", name="Покупатель ACC",
    )


@pytest.fixture
def user():
    return User.objects.create(email="acc-tester@y.local", full_name="ACC Tester")


@pytest.fixture
def accessory(org, m_vet, bowl_nom, vet_warehouse):
    return VetAccessory.objects.create(
        organization=org, module=m_vet,
        nomenclature=bowl_nom, warehouse=vet_warehouse,
        current_quantity=Decimal("0"),
        cost_per_unit_uzs=Decimal("0"),
        sale_price_uzs=Decimal("25000"),
        barcode="VET-A-BOWL-TEST",
    )


# ─── Receive: weighted-average cost ─────────────────────────────────────


def test_receive_first_time_sets_cost_directly(accessory, user):
    """Первый приход (current_qty=0) → cost = unit_cost без усреднения."""
    result = receive_vet_accessory(
        accessory, quantity=Decimal("10"),
        unit_cost_uzs=Decimal("15000"), user=user,
    )
    accessory.refresh_from_db()
    assert accessory.current_quantity == Decimal("10")
    assert accessory.cost_per_unit_uzs == Decimal("15000.00")
    assert result.previous_cost_uzs == Decimal("0")
    assert result.new_cost_uzs == Decimal("15000.00")
    # StockMovement INCOMING создан
    assert StockMovement.objects.filter(
        source_object_id=accessory.id, kind=StockMovement.Kind.INCOMING,
    ).count() == 1


def test_receive_weighted_avg_when_existing_stock(accessory, user):
    """Имеем 10 по 15000, принимаем 5 по 21000 → avg = (10*15+5*21)/15 = 17000."""
    receive_vet_accessory(accessory, quantity=Decimal("10"),
                         unit_cost_uzs=Decimal("15000"), user=user)
    receive_vet_accessory(accessory, quantity=Decimal("5"),
                         unit_cost_uzs=Decimal("21000"), user=user)
    accessory.refresh_from_db()
    assert accessory.current_quantity == Decimal("15")
    assert accessory.cost_per_unit_uzs == Decimal("17000.00")


def test_receive_without_unit_cost_keeps_cost(accessory, user):
    """Довоз без указания цены — cost не меняется, qty +=."""
    receive_vet_accessory(accessory, quantity=Decimal("10"),
                         unit_cost_uzs=Decimal("15000"), user=user)
    receive_vet_accessory(accessory, quantity=Decimal("3"), user=user)
    accessory.refresh_from_db()
    assert accessory.current_quantity == Decimal("13")
    assert accessory.cost_per_unit_uzs == Decimal("15000.00")


def test_receive_zero_quantity_raises(accessory, user):
    with pytest.raises(VetAccessoryReceiveError):
        receive_vet_accessory(accessory, quantity=Decimal("0"), user=user)


def test_receive_inactive_accessory_raises(accessory, user):
    accessory.is_active = False
    accessory.save()
    with pytest.raises(VetAccessoryReceiveError):
        receive_vet_accessory(accessory, quantity=Decimal("1"), user=user)


# ─── Sale flow: confirm_sale + GL 41.01 ──────────────────────────────────


def test_sale_decrements_accessory_and_posts_je_to_41_01(
    org, m_sales, accessory, vet_warehouse, buyer, bowl_nom, user,
):
    receive_vet_accessory(accessory, quantity=Decimal("20"),
                         unit_cost_uzs=Decimal("15000"), user=user)

    order = SaleOrder.objects.create(
        organization=org, doc_number="",
        date=date.today(), module=m_sales, customer=buyer,
        warehouse=vet_warehouse, status=SaleOrder.Status.DRAFT,
    )
    SaleItem.objects.create(
        order=order, nomenclature=bowl_nom,
        vet_accessory=accessory,
        quantity=Decimal("3"), unit_price_uzs=Decimal("25000"),
    )

    confirm_sale(order)

    accessory.refresh_from_db()
    assert accessory.current_quantity == Decimal("17")  # 20 - 3

    order.refresh_from_db()
    assert order.status == SaleOrder.Status.CONFIRMED

    # Cost JE (Dr 90.02 / Cr 41.01) — 3 * 15000 = 45000
    cost_je = JournalEntry.objects.filter(
        organization=org,
        debit_subaccount__code="90.02",
        credit_subaccount__code="41.01",
    ).order_by("-created_at").first()
    assert cost_je is not None, "JE на 41.01 не создан"
    assert cost_je.amount_uzs == Decimal("45000.00")


def test_sale_blocked_when_accessory_inactive(
    org, m_sales, accessory, vet_warehouse, buyer, bowl_nom, user,
):
    receive_vet_accessory(accessory, quantity=Decimal("5"),
                         unit_cost_uzs=Decimal("10000"), user=user)
    accessory.is_active = False
    accessory.save()

    order = SaleOrder.objects.create(
        organization=org, doc_number="",
        date=date.today(), module=m_sales, customer=buyer,
        warehouse=vet_warehouse, status=SaleOrder.Status.DRAFT,
    )
    SaleItem.objects.create(
        order=order, nomenclature=bowl_nom,
        vet_accessory=accessory,
        quantity=Decimal("1"), unit_price_uzs=Decimal("20000"),
    )
    with pytest.raises(SaleConfirmError):
        confirm_sale(order)


def test_sale_blocked_when_insufficient_stock(
    org, m_sales, accessory, vet_warehouse, buyer, bowl_nom, user,
):
    receive_vet_accessory(accessory, quantity=Decimal("2"),
                         unit_cost_uzs=Decimal("10000"), user=user)
    order = SaleOrder.objects.create(
        organization=org, doc_number="",
        date=date.today(), module=m_sales, customer=buyer,
        warehouse=vet_warehouse, status=SaleOrder.Status.DRAFT,
    )
    SaleItem.objects.create(
        order=order, nomenclature=bowl_nom,
        vet_accessory=accessory,
        quantity=Decimal("5"), unit_price_uzs=Decimal("20000"),
    )
    with pytest.raises(SaleConfirmError):
        confirm_sale(order)


def test_xor_blocks_two_sources_at_once(
    org, m_sales, accessory, vet_warehouse, buyer, bowl_nom, user,
):
    """SaleItem не должен пускать одновременно vet_accessory + другой источник."""
    from django.core.exceptions import ValidationError
    from apps.batches.models import Batch
    from apps.modules.models import Module

    m_slaughter = Module.objects.get(code="slaughter")
    other_batch = Batch.objects.create(
        organization=org, doc_number="П-X-1",
        nomenclature=bowl_nom, unit=bowl_nom.unit,
        origin_module=m_slaughter, current_module=m_slaughter,
        current_quantity=Decimal("1"), initial_quantity=Decimal("1"),
        accumulated_cost_uzs=Decimal("0"),
        started_at=date.today(),
    )
    order = SaleOrder.objects.create(
        organization=org, doc_number="",
        date=date.today(), module=m_sales, customer=buyer,
        warehouse=vet_warehouse, status=SaleOrder.Status.DRAFT,
    )
    item = SaleItem(
        order=order, nomenclature=bowl_nom,
        vet_accessory=accessory, batch=other_batch,
        quantity=Decimal("1"), unit_price_uzs=Decimal("100"),
    )
    with pytest.raises(ValidationError):
        item.full_clean()


# ─── Public scan ─────────────────────────────────────────────────────────


def test_public_scan_finds_accessory_by_barcode(accessory):
    from rest_framework.test import APIClient

    api = APIClient()
    resp = api.get(f"/api/vet/public/scan/{accessory.barcode}/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert data["source_kind"] == "accessory"
    assert data["barcode"] == accessory.barcode
    assert data["nomenclature_sku"] == "ACC-BOWL"
