"""
Тесты field-level RBAC: FinancialFieldsMixin привязывает деньги к
конкретному модулю и скрывает их от пользователей без доступа.

Принцип: «деньги принадлежат модулю-владельцу». Видимость денег =
  - доступ ≥ 'r' к модулю-владельцу (свои деньги), ИЛИ
  - доступ ≥ 'r' к 'ledger' (бухгалтер видит всё)
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.counterparties.models import Counterparty
from apps.feed.models import RawMaterialBatch
from apps.feed.serializers import RawMaterialBatchSerializer
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


# ─── Хелперы ──────────────────────────────────────────────────────────────


def _make_user(email, *, org, modules):
    u = User.objects.create(email=email, full_name=email)
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for module, level in modules.items():
        UserModuleAccessOverride.objects.create(
            membership=membership, module=module, level=level,
        )
    return u


def _serialize(instance, *, user, org, serializer_class):
    """Серилизует instance с правильно настроенным request-context."""
    factory = APIRequestFactory()
    req = factory.get("/")
    force_authenticate(req, user=user)
    req.user = user
    req.organization = org
    ser = serializer_class(instance, context={"request": req})
    return ser.data


# ─── Фикстуры ─────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def m_vet():
    return Module.objects.get(code="vet")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_ledger():
    return Module.objects.get(code="ledger")


@pytest.fixture
def raw_batch(org, m_feed):
    cat = Category.objects.get_or_create(organization=org, name="Зерно тест MM")[0]
    unit = Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"},
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="MM-WHT", name="Пшеница MM",
        category=cat, unit=unit,
    )
    supplier = Counterparty.objects.get_or_create(
        organization=org, code="K-MM", kind="supplier",
        defaults={"name": "Поставщик MM"},
    )[0]
    wh = Warehouse.objects.get_or_create(
        organization=org, code="СК-MM",
        defaults={"module": m_feed, "name": "Склад MM"},
    )[0]
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed,
        doc_number="СЫР-MM-001",
        nomenclature=nom, supplier=supplier, warehouse=wh,
        received_date=date(2026, 4, 20),
        quantity=Decimal("1000"),
        current_quantity=Decimal("1000"),
        unit=unit,
        price_per_unit_uzs=Decimal("2500.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


# ─── feed.r видит свои деньги (feed-модуль) ──────────────────────────────


def test_feed_user_sees_feed_prices(org, m_feed, raw_batch):
    u = _make_user("feed-r@y.local", org=org, modules={m_feed: AccessLevel.READ})
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    assert Decimal(data["price_per_unit_uzs"]) == Decimal("2500.00")
    assert data["_finances_visible"] is True


# ─── vet.r НЕ видит чужие (feed) ─────────────────────────────────────────


def test_vet_only_user_does_not_see_feed_prices(org, m_vet, raw_batch):
    """Vet-менеджер без feed/ledger — цены сырья (feed) скрыты."""
    u = _make_user("vet-only@y.local", org=org, modules={m_vet: AccessLevel.READ_WRITE})
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    assert data["price_per_unit_uzs"] is None
    assert data["_finances_visible"] is False


# ─── feedlot.r НЕ видит чужие (feed) ─────────────────────────────────────


def test_feedlot_only_user_does_not_see_feed_prices(org, m_feedlot, raw_batch):
    u = _make_user("feedlot-only@y.local", org=org, modules={m_feedlot: AccessLevel.READ_WRITE})
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    assert data["price_per_unit_uzs"] is None
    assert data["_finances_visible"] is False


# ─── ledger.r видит всё (универсальный бухгалтер) ───────────────────────


def test_ledger_user_sees_all_finances(org, m_ledger, raw_batch):
    u = _make_user("buh@y.local", org=org, modules={m_ledger: AccessLevel.READ})
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    # Через ledger-bypass — видит цены feed-модуля
    assert Decimal(data["price_per_unit_uzs"]) == Decimal("2500.00")
    assert data["_finances_visible"] is True


# ─── Без модулей — ничего ────────────────────────────────────────────────


def test_user_without_any_module_access_sees_nothing(org, raw_batch):
    """Пользователь только в OrganizationMembership без overrides → не видит."""
    u = User.objects.create(email="empty@y.local", full_name="Empty")
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    assert data["price_per_unit_uzs"] is None
    assert data["_finances_visible"] is False


# ─── Admin видит всё ─────────────────────────────────────────────────────


def test_admin_on_feed_sees_finances(org, m_feed, raw_batch):
    u = _make_user("feed-admin@y.local", org=org, modules={m_feed: AccessLevel.ADMIN})
    data = _serialize(raw_batch, user=u, org=org, serializer_class=RawMaterialBatchSerializer)
    assert Decimal(data["price_per_unit_uzs"]) == Decimal("2500.00")


# ─── Smoke через API: feed.r видит ───────────────────────────────────────


def test_api_feed_user_can_load_and_sees_price(org, m_feed, raw_batch):
    """API-уровень: feed.r → 200 + видит цену."""
    from rest_framework.test import APIClient

    u = _make_user("feed-api@y.local", org=org, modules={m_feed: AccessLevel.READ})
    api = APIClient()
    api.force_authenticate(user=u)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")

    resp = api.get(f"/api/feed/raw-batches/{raw_batch.id}/")
    assert resp.status_code == 200
    data = resp.json()
    assert Decimal(data["price_per_unit_uzs"]) == Decimal("2500.00")


# ─── Кросс-модульная защита через FK (важно): VetStockBatch ──────────────


def test_feed_user_does_not_see_vet_prices(org, m_feed, m_vet):
    """Симметричный тест: feed-менеджер НЕ должен видеть цены лекарств."""
    from apps.vet.models import DrugType, Route, VetDrug, VetStockBatch
    from apps.vet.serializers import VetStockBatchSerializer

    cat = Category.objects.get_or_create(organization=org, name="Лекарства тест")[0]
    unit = Unit.objects.get_or_create(
        organization=org, code="мл", defaults={"name": "Миллилитр"},
    )[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="VET-T1", name="Антибиотик тест",
        category=cat, unit=unit,
    )
    drug = VetDrug.objects.create(
        organization=org, module=m_vet,
        nomenclature=nom,
        drug_type=DrugType.ANTIBIOTIC,
        administration_route=Route.INJECTION,
    )
    supplier = Counterparty.objects.get_or_create(
        organization=org, code="K-VET-MM", kind="supplier",
        defaults={"name": "Поставщик вет MM"},
    )[0]
    wh = Warehouse.objects.get_or_create(
        organization=org, code="СК-VET",
        defaults={"module": m_vet, "name": "Склад вет"},
    )[0]
    vet_batch = VetStockBatch.objects.create(
        organization=org, module=m_vet,
        doc_number="ВЕТ-T1-001",
        drug=drug,
        lot_number="L1",
        warehouse=wh,
        supplier=supplier,
        received_date=date(2026, 4, 20),
        expiration_date=date(2027, 4, 20),
        quantity=Decimal("100"),
        current_quantity=Decimal("100"),
        unit=unit,
        price_per_unit_uzs=Decimal("5000.00"),
    )

    # feed-менеджер
    u = _make_user("feed-r-vet@y.local", org=org, modules={m_feed: AccessLevel.READ_WRITE})
    data = _serialize(vet_batch, user=u, org=org, serializer_class=VetStockBatchSerializer)

    assert data["price_per_unit_uzs"] is None
    assert data["_finances_visible"] is False
