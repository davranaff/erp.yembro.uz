"""
Тесты автосоздания профилей усушки через post_save сигналы.

Покрывают:
  - первая партия новой номенклатуры → создаётся дефолтный профиль
  - вторая партия той же номенклатуры → профиль НЕ дублируется
  - партия номенклатуры, для которой профиль был soft-deleted (is_active=False)
    → не пересоздаём (уважаем выбор пользователя)
  - флаг FEED_AUTO_CREATE_SHRINKAGE_PROFILE=False отключает поведение
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.counterparties.models import Counterparty
from apps.feed.models import FeedShrinkageProfile, RawMaterialBatch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"},
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(
        organization=org, name="Зерно (autocreate)",
    )[0]


@pytest.fixture
def wheat(org, cat, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="AUTO-WHT", name="Пшеница auto",
        category=cat, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.get_or_create(
        organization=org, code="K-AUTO", kind="supplier",
        defaults={"name": "Поставщик auto"},
    )[0]


@pytest.fixture
def warehouse(org, m_feed):
    return Warehouse.objects.get_or_create(
        organization=org, code="СК-AUTO",
        defaults={"module": m_feed, "name": "Склад auto"},
    )[0]


def _make_batch(*, org, m_feed, nomenclature, supplier, warehouse, unit, doc, qty="1000"):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number=doc,
        nomenclature=nomenclature, supplier=supplier, warehouse=warehouse,
        received_date=date(2026, 4, 20),
        quantity=Decimal(qty), current_quantity=Decimal(qty),
        unit=unit, price_per_unit_uzs=Decimal("100"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


# ─── Поведение по умолчанию (флаг включён) ────────────────────────────────


def test_first_batch_creates_default_profile(
    org, m_feed, wheat, supplier, warehouse, unit_kg,
):
    assert not FeedShrinkageProfile.objects.filter(nomenclature=wheat).exists()

    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-AUTO-1",
    )

    profiles = FeedShrinkageProfile.objects.filter(
        organization=org, nomenclature=wheat,
    )
    assert profiles.count() == 1
    p = profiles.first()
    assert p.target_type == FeedShrinkageProfile.TargetType.INGREDIENT
    assert p.is_active is True
    assert p.period_days == 7
    assert p.percent_per_period == Decimal("0.500")
    assert p.max_total_percent == Decimal("4.000")
    assert p.starts_after_days == 3
    assert p.warehouse_id is None  # на все склады по умолчанию
    assert "автоматически" in p.note.lower()


def test_second_batch_does_not_duplicate_profile(
    org, m_feed, wheat, supplier, warehouse, unit_kg,
):
    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-AUTO-A",
    )
    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-AUTO-B",
    )

    assert FeedShrinkageProfile.objects.filter(
        organization=org, nomenclature=wheat,
    ).count() == 1


def test_inactive_profile_not_recreated(
    org, m_feed, wheat, supplier, warehouse, unit_kg,
):
    """Если юзер деактивировал профиль — новая партия не должна его пересоздавать."""
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.5"),
        is_active=False,  # деактивирован
    )

    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-AUTO-INACT",
    )

    profiles = FeedShrinkageProfile.objects.filter(
        organization=org, nomenclature=wheat,
    )
    assert profiles.count() == 1
    assert profiles.first().is_active is False


# ─── Флаг отключает автосоздание ──────────────────────────────────────────


@override_settings(FEED_AUTO_CREATE_SHRINKAGE_PROFILE=False)
def test_flag_disables_autocreate(
    org, m_feed, wheat, supplier, warehouse, unit_kg,
):
    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-AUTO-OFF",
    )

    assert not FeedShrinkageProfile.objects.filter(
        organization=org, nomenclature=wheat,
    ).exists()


# ─── FeedBatch автосоздание (для готового корма) ─────────────────────────


@pytest.fixture
def recipe(org):
    from apps.feed.models import Recipe
    return Recipe.objects.create(
        organization=org, code="AUTO-STARTER", name="Стартёр auto",
        direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    from apps.feed.models import RecipeVersion
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status=RecipeVersion.Status.ACTIVE,
        effective_from=date(2026, 1, 1),
    )


def _make_feed_batch_with_setup(*, org, m_feed, recipe_version, warehouse, doc_suffix):
    """Создаёт минимальный FeedBatch для тестов автосоздания."""
    from datetime import datetime, timezone

    from apps.feed.models import FeedBatch, ProductionTask
    from apps.users.models import User
    from apps.warehouses.models import ProductionBlock

    bin_block = ProductionBlock.objects.create(
        organization=org, module=m_feed,
        code=f"BIN-{doc_suffix}", name="Бункер",
        kind=ProductionBlock.Kind.STORAGE_BIN,
    )
    line = ProductionBlock.objects.create(
        organization=org, module=m_feed,
        code=f"LN-{doc_suffix}", name="Линия",
        kind=ProductionBlock.Kind.MIXER_LINE,
    )
    tech = User.objects.create(email=f"t-{doc_suffix}@y.local", full_name="T")
    task = ProductionTask.objects.create(
        organization=org, module=m_feed,
        doc_number=f"TASK-{doc_suffix}",
        recipe_version=recipe_version,
        production_line=line,
        scheduled_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        planned_quantity_kg=Decimal("500"),
        status=ProductionTask.Status.DONE,
        technologist=tech,
    )
    return FeedBatch.objects.create(
        organization=org, module=m_feed,
        doc_number=f"FB-{doc_suffix}",
        produced_by_task=task,
        recipe_version=recipe_version,
        produced_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        quantity_kg=Decimal("500"),
        current_quantity_kg=Decimal("500"),
        unit_cost_uzs=Decimal("250.000000"),
        total_cost_uzs=Decimal("125000"),
        storage_bin=bin_block,
        storage_warehouse=warehouse,
        status=FeedBatch.Status.APPROVED,
    )


def test_first_feed_batch_creates_default_profile_for_recipe(
    org, m_feed, recipe, recipe_version, warehouse,
):
    """Первая партия готового корма создаёт профиль на recipe с feed-type дефолтами."""
    from apps.feed.models import FeedBatch  # noqa: F401 — нужен для signal-receiver

    assert not FeedShrinkageProfile.objects.filter(recipe=recipe).exists()

    _make_feed_batch_with_setup(
        org=org, m_feed=m_feed, recipe_version=recipe_version,
        warehouse=warehouse, doc_suffix="A",
    )

    profiles = FeedShrinkageProfile.objects.filter(
        organization=org, recipe=recipe,
    )
    assert profiles.count() == 1
    p = profiles.first()
    assert p.target_type == FeedShrinkageProfile.TargetType.FEED_TYPE
    assert p.nomenclature_id is None  # для feed-type не должно быть nomenclature
    assert p.period_days == 7
    assert p.percent_per_period == Decimal("0.300")
    assert p.max_total_percent == Decimal("2.000")
    assert p.starts_after_days == 2


def test_second_feed_batch_same_recipe_does_not_duplicate(
    org, m_feed, recipe, recipe_version, warehouse,
):
    _make_feed_batch_with_setup(
        org=org, m_feed=m_feed, recipe_version=recipe_version,
        warehouse=warehouse, doc_suffix="B1",
    )
    _make_feed_batch_with_setup(
        org=org, m_feed=m_feed, recipe_version=recipe_version,
        warehouse=warehouse, doc_suffix="B2",
    )
    assert FeedShrinkageProfile.objects.filter(
        organization=org, recipe=recipe,
    ).count() == 1


# ─── note содержит маркер «автоматически» (для UI-подсказки) ─────────────


def test_autocreated_profile_note_contains_marker(
    org, m_feed, wheat, supplier, warehouse, unit_kg,
):
    """
    Frontend ShrinkageWidget показывает плашку «создан автоматически» когда
    note содержит слово «автоматически». Проверяем что сигнал пишет именно так.
    """
    _make_batch(
        org=org, m_feed=m_feed, nomenclature=wheat, supplier=supplier,
        warehouse=warehouse, unit=unit_kg, doc="СЫР-NOTE",
    )
    profile = FeedShrinkageProfile.objects.get(nomenclature=wheat)
    assert "автоматически" in profile.note.lower()
