"""
Тесты public-эндпоинтов вет.аптеки + продажа через seller-token.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.vet.models import (
    SellerDeviceToken,
    VetDrug,
    VetStockBatch,
)
from apps.vet.services.sell import sell_vet_stock
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def user():
    return User.objects.create(email="seller@y.local", full_name="Seller")


@pytest.fixture
def base(org, m_vet):
    cat = Category.objects.get_or_create(organization=org, name="ВП-PUB")[0]
    unit = Unit.objects.get_or_create(
        organization=org, code="фл", defaults={"name": "флакон"}
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="ВП-PUB-01", name="Препарат-PUB",
        category=cat, unit=unit,
    )
    drug = VetDrug.objects.create(
        organization=org, module=m_vet, nomenclature=nom,
        drug_type="vitamin", administration_route="oral",
    )
    wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-PUB", name="СкВП PUB",
    )
    sup = Counterparty.objects.create(
        organization=org, code="К-PUB-01", kind="supplier", name="Поставщик-PUB",
    )
    return {"drug": drug, "wh": wh, "sup": sup, "unit": unit, "nom": nom}


@pytest.fixture
def lot(org, m_vet, base):
    return VetStockBatch.objects.create(
        organization=org, module=m_vet,
        doc_number="ВП-PUB-LOT", drug=base["drug"], lot_number="L-PUB-01",
        warehouse=base["wh"], supplier=base["sup"],
        received_date=date.today(),
        expiration_date=date.today() + timedelta(days=180),
        quantity=Decimal("100"), current_quantity=Decimal("100"),
        unit=base["unit"], price_per_unit_uzs=Decimal("25000"),
        status=VetStockBatch.Status.AVAILABLE,
        barcode="VET-PUB-TEST-XYZ1",
    )


@pytest.fixture
def seller_token(org, user):
    return SellerDeviceToken.objects.create(
        user=user,
        organization=org,
        token="test-seller-token-abc123",
        label="Тестовый магазин",
    )


# ─── Public scan (anonymous) ──────────────────────────────────────


def test_public_scan_returns_lot_data(lot):
    client = APIClient()
    resp = client.get(f"/api/vet/public/scan/{lot.barcode}/")
    assert resp.status_code == 200
    data = resp.data
    # Должны быть только разрешённые поля
    assert data["barcode"] == lot.barcode
    assert data["drug_sku"] == "ВП-PUB-01"
    assert data["drug_name"] == "Препарат-PUB"
    assert "current_quantity" in data
    assert "expiration_date" in data
    # НЕ должны быть чувствительные поля
    assert "organization" not in data
    assert "supplier" not in data
    assert "purchase" not in data


def test_public_scan_unknown_barcode_returns_404():
    client = APIClient()
    resp = client.get("/api/vet/public/scan/UNKNOWN-CODE/")
    assert resp.status_code == 404


# ─── Seller token authentication ──────────────────────────────────


def test_seller_sale_with_valid_token_creates_sale_order(lot, seller_token):
    client = APIClient()
    resp = client.post(
        "/api/vet/public/sell/",
        {"barcode": lot.barcode, "quantity": "5"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {seller_token.token}",
    )
    assert resp.status_code == 201, resp.content
    data = resp.data
    assert data["sale_order_doc"]
    assert Decimal(data["remaining_qty"]) == Decimal("95.000")
    assert data["lot_status"] == "available"


def test_seller_sale_without_token_returns_401(lot):
    client = APIClient()
    resp = client.post(
        "/api/vet/public/sell/",
        {"barcode": lot.barcode, "quantity": "5"},
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_seller_sale_with_revoked_token_returns_401(lot, seller_token):
    from django.utils import timezone

    seller_token.revoked_at = timezone.now()
    seller_token.is_active = False
    seller_token.save()

    client = APIClient()
    resp = client.post(
        "/api/vet/public/sell/",
        {"barcode": lot.barcode, "quantity": "5"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {seller_token.token}",
    )
    assert resp.status_code == 401


def test_seller_sale_invalid_token_returns_401(lot):
    client = APIClient()
    resp = client.post(
        "/api/vet/public/sell/",
        {"barcode": lot.barcode, "quantity": "5"},
        format="json",
        HTTP_AUTHORIZATION="Bearer wrong-token-xxx",
    )
    assert resp.status_code == 401


# ─── sell_vet_stock service ────────────────────────────────────────


def test_sell_vet_stock_decrements_lot(org, m_vet, lot, user):
    result = sell_vet_stock(
        stock_batch=lot,
        quantity=Decimal("10"),
        seller_user=user,
        organization=org,
    )
    lot.refresh_from_db()
    assert lot.current_quantity == Decimal("90.000")
    assert result.sale_order.status == "confirmed"
    assert result.total_uzs > 0


def test_sell_full_quantity_marks_depleted(org, m_vet, lot, user):
    result = sell_vet_stock(
        stock_batch=lot,
        quantity=Decimal("100"),
        seller_user=user,
        organization=org,
    )
    lot.refresh_from_db()
    assert lot.current_quantity == Decimal("0.000")
    assert lot.status == VetStockBatch.Status.DEPLETED


def test_sell_more_than_available_raises(org, m_vet, lot, user):
    from apps.vet.services.sell import VetSellError

    with pytest.raises(VetSellError):
        sell_vet_stock(
            stock_batch=lot,
            quantity=Decimal("200"),
            seller_user=user,
            organization=org,
        )


def test_sell_expired_raises(org, m_vet, lot, user, base):
    from apps.vet.services.sell import VetSellError

    lot.expiration_date = date.today() - timedelta(days=1)
    lot.save(update_fields=["expiration_date"])

    with pytest.raises(VetSellError):
        sell_vet_stock(
            stock_batch=lot,
            quantity=Decimal("10"),
            seller_user=user,
            organization=org,
        )


def test_sell_quarantine_raises(org, m_vet, lot, user):
    from apps.vet.services.sell import VetSellError

    lot.status = VetStockBatch.Status.QUARANTINE
    lot.save(update_fields=["status"])

    with pytest.raises(VetSellError):
        sell_vet_stock(
            stock_batch=lot,
            quantity=Decimal("10"),
            seller_user=user,
            organization=org,
        )
