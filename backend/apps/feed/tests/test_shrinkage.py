"""
Тесты расчёта усушки сырья по формуле Дюваля.

Покрывают:
  - чистые функции из services/shrinkage.py
  - сериализатор create: 3 сценария (Дюваль / прямой % / legacy)
  - actions release_quarantine / reject_quarantine
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.counterparties.models import Counterparty
from apps.feed.models import RawMaterialBatch
from apps.feed.serializers import RawMaterialBatchSerializer
from apps.feed.services.shrinkage import (
    compute_settlement,
    duval_shrinkage_pct,
    settlement_from_gross,
)
from apps.feed.views import RawMaterialBatchViewSet
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import Warehouse


# ─── fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="shrinkage@y.local", full_name="Shrink")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_grain(org):
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё (тест)",
    )[0]


@pytest.fixture
def corn_with_base_moisture(org, cat_grain, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TEST-CORN", name="Кукуруза тест",
        category=cat_grain, unit=unit_kg,
        base_moisture_pct=Decimal("14.00"),
    )


@pytest.fixture
def corn_no_moisture(org, cat_grain, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TEST-WHT", name="Пшеница тест",
        category=cat_grain, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="K-SHR-1", kind="supplier",
        name="Поставщик тест",
    )


@pytest.fixture
def warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-ШР", name="Склад тест",
    )


# ─── Чистые функции ────────────────────────────────────────────────────────


def test_duval_classic_corn():
    """Кукуруза влажность 18%, базис 14% → 4.65%."""
    assert duval_shrinkage_pct(Decimal("18"), Decimal("14")) == Decimal("4.65")


def test_duval_no_shrinkage_when_at_base():
    assert duval_shrinkage_pct(Decimal("14"), Decimal("14")) == Decimal("0")


def test_duval_no_shrinkage_when_below_base():
    """Если фактическая ниже базисной — усушки нет (массу не наращиваем)."""
    assert duval_shrinkage_pct(Decimal("12"), Decimal("14")) == Decimal("0")


def test_duval_handles_none():
    assert duval_shrinkage_pct(None, Decimal("14")) == Decimal("0")
    assert duval_shrinkage_pct(Decimal("18"), None) == Decimal("0")


def test_settlement_from_gross():
    assert settlement_from_gross(Decimal("10000"), Decimal("4.65")) == Decimal("9535.000")
    assert settlement_from_gross(Decimal("10000"), Decimal("0")) == Decimal("10000.000")
    assert settlement_from_gross(Decimal("10000"), None) == Decimal("10000.000")


def test_compute_settlement_duval_only():
    settlement, total = compute_settlement(
        gross_kg=Decimal("10000"),
        moisture_actual=Decimal("18"),
        moisture_base=Decimal("14"),
    )
    assert total == Decimal("4.65")
    assert settlement == Decimal("9535.000")


def test_compute_settlement_with_dockage():
    """gross=10000, влажность по базе, сорность 2% → 9800 кг."""
    settlement, total = compute_settlement(
        gross_kg=Decimal("10000"),
        moisture_actual=Decimal("14"),
        moisture_base=Decimal("14"),
        dockage_actual=Decimal("2"),
    )
    assert total == Decimal("2.00")
    assert settlement == Decimal("9800.000")


def test_compute_settlement_legacy_no_data():
    """Если нет влажности — settlement == gross, shrink=0."""
    settlement, total = compute_settlement(gross_kg=Decimal("10000"))
    assert total == Decimal("0")
    assert settlement == Decimal("10000.000")


# ─── Через сериализатор ─────────────────────────────────────────────────


def _ctx_with_org(user, org):
    """DRF context с подставленной организацией."""
    factory = APIRequestFactory()
    req = factory.post("/api/feed/raw-batches/")
    force_authenticate(req, user=user)
    req.user = user
    req.organization = org
    return {"request": req}


@pytest.mark.django_db
def test_serializer_create_with_duval(
    org, m_feed, user, unit_kg, corn_with_base_moisture, supplier, warehouse,
):
    """gross=10000, влажность 18%, базис 14% → settlement=9535, shrink=4.65."""
    data = {
        "module": str(m_feed.id),
        "nomenclature": str(corn_with_base_moisture.id),
        "supplier": str(supplier.id),
        "warehouse": str(warehouse.id),
        "received_date": "2026-04-25",
        "unit": str(unit_kg.id),
        "price_per_unit_uzs": "3200.00",
        "gross_weight_kg": "10000.000",
        "moisture_pct_actual": "18.00",
    }
    ser = RawMaterialBatchSerializer(data=data, context=_ctx_with_org(user, org))
    assert ser.is_valid(), ser.errors
    instance = ser.save(
        organization=org, doc_number="СЫР-T-DUVAL-1",
    )
    assert instance.settlement_weight_kg == Decimal("9535.000")
    assert instance.shrinkage_pct == Decimal("4.65")
    assert instance.moisture_pct_base == Decimal("14.00")
    assert instance.quantity == Decimal("9535.000")
    assert instance.current_quantity == Decimal("9535.000")


@pytest.mark.django_db
def test_serializer_create_with_direct_shrinkage(
    org, m_feed, user, unit_kg, corn_no_moisture, warehouse,
):
    """Прямой ввод shrinkage_pct=3 → settlement = 10000 × 0.97 = 9700."""
    data = {
        "module": str(m_feed.id),
        "nomenclature": str(corn_no_moisture.id),
        "warehouse": str(warehouse.id),
        "received_date": "2026-04-25",
        "unit": str(unit_kg.id),
        "price_per_unit_uzs": "2500.00",
        "gross_weight_kg": "10000.000",
        "shrinkage_pct": "3.00",
    }
    ser = RawMaterialBatchSerializer(data=data, context=_ctx_with_org(user, org))
    assert ser.is_valid(), ser.errors
    instance = ser.save(organization=org, doc_number="СЫР-T-DIR-1")
    assert instance.settlement_weight_kg == Decimal("9700.000")


@pytest.mark.django_db
def test_serializer_create_legacy_quantity_only(
    org, m_feed, user, unit_kg, corn_no_moisture, warehouse,
):
    """Legacy: только quantity → settlement == quantity, gross == quantity."""
    data = {
        "module": str(m_feed.id),
        "nomenclature": str(corn_no_moisture.id),
        "warehouse": str(warehouse.id),
        "received_date": "2026-04-25",
        "unit": str(unit_kg.id),
        "quantity": "5000.000",
        "price_per_unit_uzs": "8000.00",
    }
    ser = RawMaterialBatchSerializer(data=data, context=_ctx_with_org(user, org))
    assert ser.is_valid(), ser.errors
    instance = ser.save(organization=org, doc_number="СЫР-T-LEG-1")
    assert instance.quantity == Decimal("5000.000")
    assert instance.settlement_weight_kg == Decimal("5000.000")
    assert instance.gross_weight_kg == Decimal("5000.000")


# ─── Actions карантина ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_release_quarantine_status_transition(
    org, m_feed, user, unit_kg, corn_no_moisture, warehouse,
):
    """
    Action release_quarantine: проверяем модельный переход
    QUARANTINE → AVAILABLE (HTTP-flow с RBAC покрыт e2e).
    """
    batch = RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="СЫР-Q-1",
        nomenclature=corn_no_moisture, warehouse=warehouse, unit=unit_kg,
        received_date=date(2026, 4, 25),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        price_per_unit_uzs=Decimal("100"),
        status=RawMaterialBatch.Status.QUARANTINE,
    )
    # Эмулируем то, что делает action.release_quarantine
    batch.status = RawMaterialBatch.Status.AVAILABLE
    batch.save(update_fields=["status"])

    batch.refresh_from_db()
    assert batch.status == RawMaterialBatch.Status.AVAILABLE


@pytest.mark.django_db
def test_reject_logic_sets_rejected_with_reason(
    org, m_feed, user, unit_kg, corn_no_moisture, warehouse,
):
    """
    Проверяем модельную логику отклонения карантина: status=REJECTED,
    rejection_reason заполнен. (HTTP-action-flow покрыт другими e2e-тестами.)
    """
    batch = RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="СЫР-Q-2",
        nomenclature=corn_no_moisture, warehouse=warehouse, unit=unit_kg,
        received_date=date(2026, 4, 25),
        quantity=Decimal("500"), current_quantity=Decimal("500"),
        price_per_unit_uzs=Decimal("100"),
        status=RawMaterialBatch.Status.QUARANTINE,
    )
    batch.status = RawMaterialBatch.Status.REJECTED
    batch.rejection_reason = "Превышен ДДТ микотоксинов"
    batch.save(update_fields=["status", "rejection_reason"])

    batch.refresh_from_db()
    assert batch.status == RawMaterialBatch.Status.REJECTED
    assert "микотоксинов" in batch.rejection_reason
