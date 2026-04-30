"""
API-тесты для shrinkage endpoints (через DRF APIClient + RBAC).

Покрывают:
  - POST /api/feed/shrinkage-profiles/ — XOR-валидация target ↔ nomenclature/recipe
  - POST /api/feed/shrinkage-state/apply/ — точечный прогон создаёт state+movement
  - GET  /api/feed/shrinkage-state/{id}/history/ — возвращает накопительные точки
  - GET  /api/feed/shrinkage-report/ — JSON и CSV
  - POST /api/feed/shrinkage-state/{id}/reset/ — откатывает движения и сбрасывает state

Все запросы — от admin-пользователя с UserModuleAccessOverride на модуль feed.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedLotShrinkageState,
    FeedShrinkageProfile,
    RawMaterialBatch,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def admin_user(org, m_feed):
    u = User.objects.create(email="shrink-api@y.local", full_name="Admin")
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_feed, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"},
    )[0]


@pytest.fixture
def cat_grain(org):
    return Category.objects.get_or_create(
        organization=org, name="Зерно (api test)",
    )[0]


@pytest.fixture
def wheat(org, cat_grain, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="API-WHT", name="Пшеница API",
        category=cat_grain, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.get_or_create(
        organization=org, code="K-API-SHR", kind="supplier",
        defaults={"name": "Поставщик API"},
    )[0]


@pytest.fixture
def warehouse(org, m_feed):
    return Warehouse.objects.get_or_create(
        organization=org, code="СК-API",
        defaults={"module": m_feed, "name": "Склад API"},
    )[0]


@pytest.fixture
def batch(org, m_feed, wheat, supplier, warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org,
        module=m_feed,
        doc_number="СЫР-API-20260420",
        nomenclature=wheat,
        supplier=supplier,
        warehouse=warehouse,
        received_date=date(2026, 4, 20),
        quantity=Decimal("1000"),
        current_quantity=Decimal("1000"),
        unit=unit_kg,
        price_per_unit_uzs=Decimal("100"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


# ─── /shrinkage-profiles/ ──────────────────────────────────────────────────


def test_create_profile_ingredient_ok(client, wheat):
    """POST с target_type=ingredient + nomenclature → 201."""
    resp = client.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "period_days": 7,
        "percent_per_period": "0.8",
        "max_total_percent": "5.0",
        "starts_after_days": 3,
    }, format="json")
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data["target_type"] == "ingredient"
    assert data["nomenclature"] == str(wheat.id)
    assert data["recipe"] is None
    assert data["is_active"] is True


def test_create_profile_ingredient_without_nomenclature_400(client):
    resp = client.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    assert resp.status_code == 400
    assert "nomenclature" in resp.json()


def test_create_profile_with_both_targets_400(client, wheat):
    """target=ingredient + recipe одновременно → ошибка."""
    from apps.feed.models import Recipe
    recipe = Recipe.objects.create(
        organization=Organization.objects.get(code="DEFAULT"),
        code="API-R1", name="API Recipe", direction="broiler",
    )
    resp = client.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "recipe": str(recipe.id),  # лишнее
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    assert resp.status_code == 400


def test_soft_delete_profile_marks_inactive(client, wheat):
    resp = client.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    pid = resp.json()["id"]

    delete = client.delete(f"/api/feed/shrinkage-profiles/{pid}/")
    # Soft delete — но DRF возвращает 204 как для обычного destroy
    assert delete.status_code in (204, 200)

    # Проверим что профиль есть в БД, но is_active=False
    profile = FeedShrinkageProfile.objects.get(id=pid)
    assert profile.is_active is False


# ─── /shrinkage-state/apply/ ──────────────────────────────────────────────


def test_apply_to_specific_lot_creates_state(client, batch, wheat):
    """POST /apply/ с lot_type+lot_id → создаётся state и StockMovement."""
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival",
        "lot_id": str(batch.id),
        "on_date": "2026-04-30",  # +10 дней с поступления → 1 период
    }, format="json")
    assert resp.status_code == 200, resp.content

    data = resp.json()
    assert data["skipped"] is False
    assert data["periods_applied"] == 1
    assert data["state_id"] is not None
    assert data["movement_id"] is not None

    # State реально создан
    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    assert state.accumulated_loss == Decimal("8.000")

    # Партия списана на 8 кг
    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("992.000")


def test_apply_orgwide_returns_summary(client, batch, wheat):
    """POST /apply/ без аргументов → summary по всей организации."""
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "on_date": "2026-04-30",
    }, format="json")
    assert resp.status_code == 200
    data = resp.json()

    assert data["lots_total"] >= 1
    assert data["lots_applied"] >= 1
    assert "results" in data
    assert any(r["lot_id"] == str(batch.id) and not r["skipped"] for r in data["results"])


def test_apply_invalid_date_400(client):
    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "on_date": "garbage",
    }, format="json")
    assert resp.status_code == 400


def test_apply_lot_type_without_lot_id_400(client):
    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival",
        # lot_id пропущен
    }, format="json")
    assert resp.status_code == 400


# ─── /shrinkage-state/{id}/history/ ───────────────────────────────────────


def test_history_returns_movements_chronologically(client, batch, wheat):
    """После двух циклов история должна содержать обе точки в порядке возрастания дат."""
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    # Цикл 1: +10 дней
    client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival", "lot_id": str(batch.id),
        "on_date": "2026-04-30",
    }, format="json")
    # Цикл 2: ещё +7 дней = +17 от поступления
    client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival", "lot_id": str(batch.id),
        "on_date": "2026-05-07",
    }, format="json")

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    resp = client.get(f"/api/feed/shrinkage-state/{state.id}/history/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) == 2

    p1, p2 = data["points"]
    assert p1["date"] <= p2["date"]
    # cumulative_loss растёт
    assert Decimal(p2["cumulative_loss_kg"]) > Decimal(p1["cumulative_loss_kg"])
    # remaining падает
    assert Decimal(p2["remaining_kg"]) < Decimal(p1["remaining_kg"])


# ─── /shrinkage-report/ ───────────────────────────────────────────────────


def test_report_json_aggregates_by_ingredient(client, batch, wheat):
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival", "lot_id": str(batch.id),
        "on_date": "2026-04-30",
    }, format="json")

    resp = client.get("/api/feed/shrinkage-report/?group_by=ingredient")
    assert resp.status_code == 200
    data = resp.json()
    assert data["group_by"] == "ingredient"
    assert len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["key"] == str(wheat.id)
    assert "Пшеница" in row["label"]
    assert Decimal(row["total_loss_kg"]) == Decimal("8.000")
    assert Decimal(data["summary"]["total_loss_kg"]) == Decimal("8.000")


def test_report_csv_export(client, batch, wheat):
    """?format=csv → text/csv с BOM и итоговой строкой."""
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival", "lot_id": str(batch.id),
        "on_date": "2026-04-30",
    }, format="json")

    resp = client.get("/api/feed/shrinkage-report/?format=csv&group_by=ingredient")
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "attachment" in resp["Content-Disposition"]

    content = b"".join(resp.streaming_content).decode("utf-8")
    # BOM в начале
    assert content.startswith("﻿")
    # Заголовок
    assert "Ингредиент" in content
    assert "Списано (кг)" in content
    # Итог
    assert "Итого" in content


# ─── /shrinkage-state/{id}/reset/ ─────────────────────────────────────────


def test_reset_undoes_movements(client, batch, wheat):
    FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival", "lot_id": str(batch.id),
        "on_date": "2026-04-30",
    }, format="json")

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    resp = client.post(f"/api/feed/shrinkage-state/{state.id}/reset/", {}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["reverted_movements"] == 1

    # Партия восстановлена
    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("1000.000")

    # State сброшен
    state.refresh_from_db()
    assert state.accumulated_loss == Decimal("0")
    assert state.last_applied_on is None
    assert state.is_frozen is False

    # Движения удалены
    assert StockMovement.objects.filter(
        kind=StockMovement.Kind.SHRINKAGE,
        source_object_id=state.id,
    ).count() == 0


# ─── RBAC ─────────────────────────────────────────────────────────────────


def test_endpoint_requires_feed_module_access(org):
    """Юзер без feed-permission получит 403."""
    u = User.objects.create(email="noperm@y.local", full_name="No Perm")
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    api = APIClient()
    api.force_authenticate(user=u)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")

    resp = api.get("/api/feed/shrinkage-profiles/")
    assert resp.status_code == 403


def test_endpoint_requires_org_header(admin_user):
    """Без X-Organization-Code → 400 от OrganizationContextMixin."""
    api = APIClient()
    api.force_authenticate(user=admin_user)
    resp = api.get("/api/feed/shrinkage-profiles/")
    assert resp.status_code == 400


# ─── RBAC: уровни доступа r/rw/admin ──────────────────────────────────────


@pytest.fixture
def reader_user(org, m_feed):
    """Пользователь с уровнем READ — только GET-запросы."""
    u = User.objects.create(email="reader@y.local", full_name="Reader")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_feed, level=AccessLevel.READ,
    )
    return u


@pytest.fixture
def writer_user(org, m_feed):
    """Пользователь с уровнем READ_WRITE — может создавать/обновлять профили."""
    u = User.objects.create(email="writer@y.local", full_name="Writer")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_feed, level=AccessLevel.READ_WRITE,
    )
    return u


def _make_client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_reader_can_list_profiles(reader_user, wheat):
    """Юзер с feed.r видит список профилей."""
    FeedShrinkageProfile.objects.create(
        organization=Organization.objects.get(code="DEFAULT"),
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    api = _make_client(reader_user)
    resp = api.get("/api/feed/shrinkage-profiles/")
    assert resp.status_code == 200


def test_reader_cannot_create_profile(reader_user, wheat):
    """Юзер с feed.r не может POST'ить — 403."""
    api = _make_client(reader_user)
    resp = api.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    assert resp.status_code == 403


def test_writer_can_create_profile(writer_user, wheat):
    """feed.rw может создать профиль."""
    api = _make_client(writer_user)
    resp = api.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    assert resp.status_code == 201


# ─── History edge cases ──────────────────────────────────────────────────


def test_history_empty_for_state_without_movements(client, batch, wheat):
    """
    State может существовать без движений (например в случае freeze
    при первом срабатывании когда max_total_pct уже нулевой).
    """
    # Создадим state вручную, без вызова apply_to_lot
    profile = FeedShrinkageProfile.objects.create(
        organization=batch.organization,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    state = FeedLotShrinkageState.objects.create(
        organization=batch.organization,
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=batch.id,
        profile=profile,
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
    )

    resp = client.get(f"/api/feed/shrinkage-state/{state.id}/history/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == []
    assert Decimal(data["initial_quantity"]) == Decimal("1000")
    assert data["is_frozen"] is False


# ─── Report edge cases ───────────────────────────────────────────────────


def test_report_with_no_movements_returns_empty(client):
    """Отчёт за период без списаний → пустые rows и нулевой итог."""
    resp = client.get(
        "/api/feed/shrinkage-report/?date_from=2026-01-01&date_to=2026-01-31"
        "&group_by=ingredient",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows"] == []
    assert Decimal(data["summary"]["total_loss_kg"]) == Decimal("0")
    assert Decimal(data["summary"]["total_loss_uzs"]) == Decimal("0")


def test_report_invalid_group_by_400(client):
    """group_by должен быть ingredient или warehouse."""
    resp = client.get("/api/feed/shrinkage-report/?group_by=garbage")
    assert resp.status_code == 400


def test_report_invalid_date_400(client):
    resp = client.get("/api/feed/shrinkage-report/?date_from=not-a-date")
    assert resp.status_code == 400


# ─── Soft-delete не повторяется ──────────────────────────────────────────


def test_soft_delete_profile_idempotent(client, wheat):
    """Повторный DELETE на уже неактивном профиле не должен создавать дубль/упасть."""
    resp = client.post("/api/feed/shrinkage-profiles/", {
        "target_type": "ingredient",
        "nomenclature": str(wheat.id),
        "period_days": 7,
        "percent_per_period": "0.8",
    }, format="json")
    pid = resp.json()["id"]

    client.delete(f"/api/feed/shrinkage-profiles/{pid}/")
    # Второй DELETE — профиль уже is_active=False, ничего не должно ломаться
    resp2 = client.delete(f"/api/feed/shrinkage-profiles/{pid}/")
    assert resp2.status_code in (204, 200)
    profile = FeedShrinkageProfile.objects.get(id=pid)
    assert profile.is_active is False


# ─── Apply на несуществующую партию ──────────────────────────────────────


def test_apply_specific_lot_with_invalid_id_returns_error(client):
    """Несуществующий lot_id → 404 или 500. Главное — не silent success."""
    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "raw_arrival",
        "lot_id": "00000000-0000-0000-0000-000000000000",
    }, format="json")
    # Не должно быть 200 со skipped=False
    assert resp.status_code != 200 or resp.json().get("skipped") is True


def test_apply_invalid_lot_type_400(client):
    resp = client.post("/api/feed/shrinkage-state/apply/", {
        "lot_type": "garbage",
        "lot_id": "00000000-0000-0000-0000-000000000000",
    }, format="json")
    assert resp.status_code == 400
