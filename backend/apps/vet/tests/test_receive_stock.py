"""
Тесты receive_vet_stock_batch и release_vet_stock_from_quarantine.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.purchases.models import PurchaseOrder
from apps.vet.models import VetDrug, VetStockBatch
from apps.vet.services.receive_stock import (
    receive_vet_stock_batch,
    release_vet_stock_from_quarantine,
)
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def unit_ml(org):
    return Unit.objects.get_or_create(
        organization=org, code="мл", defaults={"name": "миллилитр"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(
        organization=org, name="Ветпрепараты"
    )[0]


@pytest.fixture
def nom(org, cat, unit_ml):
    return NomenclatureItem.objects.create(
        organization=org, sku="ВП-НБ-01", name="Ньюкасл вакцина",
        category=cat, unit=unit_ml,
    )


@pytest.fixture
def drug(org, m_vet, nom):
    return VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nom,
        drug_type="vaccine", administration_route="drinking_water",
        default_withdrawal_days=5,
    )


@pytest.fixture
def warehouse(org, m_vet):
    return Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВП", name="Склад ветаптеки",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-ФЕРМ-01", kind="supplier", name="Фармико",
    )


@pytest.fixture
def purchase(org, m_vet, supplier, warehouse):
    return PurchaseOrder.objects.create(
        organization=org, module=m_vet, doc_number="ЗК-ВТ-01",
        date=date(2026, 4, 20),
        counterparty=supplier, warehouse=warehouse,
    )


def test_receive_creates_quarantined_batch(org, drug, warehouse, supplier, unit_ml, purchase):
    result = receive_vet_stock_batch(
        organization=org, drug=drug, lot_number="L-2403",
        warehouse=warehouse, supplier=supplier, purchase=purchase,
        received_date=date(2026, 4, 20),
        expiration_date=date(2027, 4, 20),
        quantity=Decimal("1000"), unit=unit_ml,
        price_per_unit_uzs=Decimal("500"),
    )
    sb = result.stock_batch
    assert sb.status == VetStockBatch.Status.QUARANTINE
    assert sb.current_quantity == Decimal("1000")
    assert sb.quantity == Decimal("1000")
    assert sb.doc_number.startswith("ВП-")
    # Авто-генерация штрих-кода
    assert sb.barcode and sb.barcode.startswith("VET-")


def test_receive_without_purchase_raises(org, drug, warehouse, supplier, unit_ml):
    """purchase теперь обязателен."""
    with pytest.raises(ValidationError):
        receive_vet_stock_batch(
            organization=org, drug=drug, lot_number="L-2403",
            warehouse=warehouse, supplier=supplier,
            received_date=date(2026, 4, 20),
            expiration_date=date(2027, 4, 20),
            quantity=Decimal("100"), unit=unit_ml,
            price_per_unit_uzs=Decimal("500"),
        )


def test_receive_zero_quantity_raises(org, drug, warehouse, supplier, unit_ml, purchase):
    with pytest.raises(ValidationError):
        receive_vet_stock_batch(
            organization=org, drug=drug, lot_number="L-2403",
            warehouse=warehouse, supplier=supplier, purchase=purchase,
            received_date=date(2026, 4, 20),
            expiration_date=date(2027, 4, 20),
            quantity=Decimal("0"), unit=unit_ml,
            price_per_unit_uzs=Decimal("500"),
        )


def test_receive_expiration_before_received_raises(
    org, drug, warehouse, supplier, unit_ml, purchase,
):
    with pytest.raises(ValidationError):
        receive_vet_stock_batch(
            organization=org, drug=drug, lot_number="L-2403",
            warehouse=warehouse, supplier=supplier, purchase=purchase,
            received_date=date(2026, 4, 20),
            expiration_date=date(2026, 1, 1),
            quantity=Decimal("10"), unit=unit_ml,
            price_per_unit_uzs=Decimal("500"),
        )


def test_release_quarantine_sets_available(org, drug, warehouse, supplier, unit_ml, purchase):
    result = receive_vet_stock_batch(
        organization=org, drug=drug, lot_number="L-2403",
        warehouse=warehouse, supplier=supplier, purchase=purchase,
        received_date=date(2026, 4, 20),
        expiration_date=date(2027, 4, 20),
        quantity=Decimal("1000"), unit=unit_ml,
        price_per_unit_uzs=Decimal("500"),
    )
    released = release_vet_stock_from_quarantine(result.stock_batch)
    assert released.status == VetStockBatch.Status.AVAILABLE


def test_release_from_non_quarantine_raises(org, drug, warehouse, supplier, unit_ml, purchase):
    result = receive_vet_stock_batch(
        organization=org, drug=drug, lot_number="L-2403",
        warehouse=warehouse, supplier=supplier, purchase=purchase,
        received_date=date(2026, 4, 20),
        expiration_date=date(2027, 4, 20),
        quantity=Decimal("1000"), unit=unit_ml,
        price_per_unit_uzs=Decimal("500"),
        start_status=VetStockBatch.Status.AVAILABLE,
    )
    with pytest.raises(ValidationError):
        release_vet_stock_from_quarantine(result.stock_batch)
