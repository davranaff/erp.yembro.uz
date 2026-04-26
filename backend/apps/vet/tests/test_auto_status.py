"""Тесты auto_update_vet_stock_status — авто-перевод статусов лотов."""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.vet.models import VetDrug, VetStockBatch
from apps.vet.services.auto_status import auto_update_vet_stock_status
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def base(org, m_vet):
    cat = Category.objects.get_or_create(organization=org, name="Ветпрепараты-AS")[0]
    unit = Unit.objects.get_or_create(
        organization=org, code="мл", defaults={"name": "мл"}
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="ВП-AS-01", name="Тест-Препарат-AS",
        category=cat, unit=unit,
    )
    drug = VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nom,
        drug_type="vaccine", administration_route="oral",
    )
    wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-ВП-AS", name="СкВП AS",
    )
    sup = Counterparty.objects.create(
        organization=org, code="К-ВП-AS", kind="supplier", name="Поставщик AS",
    )
    return {"drug": drug, "wh": wh, "sup": sup, "unit": unit}


def _make_lot(org, m_vet, base, *, exp: date, qty=Decimal("100"), status=None) -> VetStockBatch:
    return VetStockBatch.objects.create(
        organization=org, module=m_vet,
        doc_number=f"ВП-AS-{exp.isoformat()}",
        drug=base["drug"], lot_number=f"LOT-{exp.isoformat()}",
        warehouse=base["wh"], supplier=base["sup"],
        received_date=date.today() - timedelta(days=10),
        expiration_date=exp,
        quantity=qty, current_quantity=qty,
        unit=base["unit"], price_per_unit_uzs=Decimal("100"),
        status=status or VetStockBatch.Status.AVAILABLE,
    )


def test_expired_moves_to_expired(org, m_vet, base):
    """Лот с expiration вчера → статус EXPIRED."""
    lot = _make_lot(org, m_vet, base, exp=date.today() - timedelta(days=1))
    result = auto_update_vet_stock_status()
    lot.refresh_from_db()
    assert lot.status == VetStockBatch.Status.EXPIRED
    assert result.expired == 1


def test_soon_moves_to_expiring_soon(org, m_vet, base):
    """Лот с expiration через 15 дней (< 30) → EXPIRING_SOON."""
    lot = _make_lot(org, m_vet, base, exp=date.today() + timedelta(days=15))
    result = auto_update_vet_stock_status()
    lot.refresh_from_db()
    assert lot.status == VetStockBatch.Status.EXPIRING_SOON
    assert result.expiring == 1


def test_far_future_stays_available(org, m_vet, base):
    """Лот со сроком +200 дней — не трогаем."""
    lot = _make_lot(org, m_vet, base, exp=date.today() + timedelta(days=200))
    auto_update_vet_stock_status()
    lot.refresh_from_db()
    assert lot.status == VetStockBatch.Status.AVAILABLE


def test_quarantine_not_touched(org, m_vet, base):
    """QUARANTINE не должен переходить в EXPIRED даже если истёк."""
    lot = _make_lot(
        org, m_vet, base,
        exp=date.today() - timedelta(days=5),
        status=VetStockBatch.Status.QUARANTINE,
    )
    auto_update_vet_stock_status()
    lot.refresh_from_db()
    assert lot.status == VetStockBatch.Status.QUARANTINE


def test_recalled_not_touched(org, m_vet, base):
    """RECALLED не трогаем."""
    lot = _make_lot(
        org, m_vet, base,
        exp=date.today() - timedelta(days=5),
        status=VetStockBatch.Status.RECALLED,
    )
    auto_update_vet_stock_status()
    lot.refresh_from_db()
    assert lot.status == VetStockBatch.Status.RECALLED


def test_computed_properties(org, m_vet, base):
    """Computed properties: days_to_expiry, is_expired, is_expiring_soon."""
    fresh = _make_lot(org, m_vet, base, exp=date.today() + timedelta(days=200))
    soon = _make_lot(org, m_vet, base, exp=date.today() + timedelta(days=10))
    expired = _make_lot(org, m_vet, base, exp=date.today() - timedelta(days=2))

    assert fresh.days_to_expiry == 200
    assert not fresh.is_expired
    assert not fresh.is_expiring_soon

    assert soon.days_to_expiry == 10
    assert not soon.is_expired
    assert soon.is_expiring_soon

    assert expired.days_to_expiry == -2
    assert expired.is_expired
    assert not expired.is_expiring_soon
