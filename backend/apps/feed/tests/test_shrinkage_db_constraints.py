"""
Низкоуровневые тесты CHECK-констрейнтов в БД.

Проверяют что Postgres отклоняет невалидные данные на уровне миграции
0004_shrinkage_profiles_and_states. Это последний рубеж защиты —
сериализаторы тоже валидируют, но прямые `objects.create()` без
.full_clean() обходят их.

Все тесты ловят `IntegrityError` (для CHECK) — после такой ошибки
транзакция сломана, поэтому каждый тест в `transaction.atomic` / отдельной
функции, чтобы не загрязнять остальные.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.feed.models import (
    FeedLotShrinkageState,
    FeedShrinkageProfile,
    Recipe,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def wheat(org):
    cat = Category.objects.get_or_create(organization=org, name="Зерно constraints")[0]
    unit = Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"},
    )[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="DBC-WHT", name="Пшеница constraints",
        category=cat, unit=unit,
    )


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="DBC-R1", name="DBC recipe", direction="broiler",
    )


# ─── target XOR (один из nomenclature/recipe должен быть заполнен) ──────


def test_profile_target_ingredient_without_nomenclature_rejected(org):
    """target_type=ingredient + nomenclature=NULL → CHECK fail."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=None,
                recipe=None,
                period_days=7,
                percent_per_period=Decimal("0.8"),
            )


def test_profile_target_feed_type_without_recipe_rejected(org):
    """target_type=feed_type + recipe=NULL → CHECK fail."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.FEED_TYPE,
                nomenclature=None,
                recipe=None,
                period_days=7,
                percent_per_period=Decimal("0.8"),
            )


def test_profile_with_both_targets_rejected(org, wheat, recipe):
    """nomenclature + recipe одновременно → CHECK fail."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=wheat,
                recipe=recipe,
                period_days=7,
                percent_per_period=Decimal("0.8"),
            )


# ─── period_days > 0 ──────────────────────────────────────────────────────


def test_profile_period_days_zero_rejected(org, wheat):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=wheat,
                period_days=0,
                percent_per_period=Decimal("0.8"),
            )


# ─── percent_per_period в [0, 100] ────────────────────────────────────────


def test_profile_percent_negative_rejected(org, wheat):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=wheat,
                period_days=7,
                percent_per_period=Decimal("-1"),
            )


def test_profile_percent_above_100_rejected(org, wheat):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=wheat,
                period_days=7,
                percent_per_period=Decimal("150"),
            )


# ─── max_total_percent в [0, 100] (если задан) ───────────────────────────


def test_profile_max_total_percent_above_100_rejected(org, wheat):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedShrinkageProfile.objects.create(
                organization=org,
                target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
                nomenclature=wheat,
                period_days=7,
                percent_per_period=Decimal("0.8"),
                max_total_percent=Decimal("150"),
            )


def test_profile_max_total_percent_null_ok(org, wheat):
    """NULL = «без предела» — должно проходить."""
    profile = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        max_total_percent=None,
    )
    assert profile.max_total_percent is None


# ─── FeedLotShrinkageState: accumulated_loss <= initial_quantity ─────────


def test_state_accumulated_loss_exceeds_initial_rejected(org, wheat):
    """accumulated_loss > initial_quantity → CHECK fail."""
    profile = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedLotShrinkageState.objects.create(
                organization=org,
                lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
                lot_id="00000000-0000-0000-0000-000000000001",
                profile=profile,
                initial_quantity=Decimal("100"),
                accumulated_loss=Decimal("150"),  # > initial
            )


def test_state_negative_accumulated_loss_rejected(org, wheat):
    profile = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedLotShrinkageState.objects.create(
                organization=org,
                lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
                lot_id="00000000-0000-0000-0000-000000000002",
                profile=profile,
                initial_quantity=Decimal("100"),
                accumulated_loss=Decimal("-5"),
            )


# ─── unique (lot_type, lot_id) — одна партия = одно состояние ────────────


def test_state_unique_lot_type_id(org, wheat):
    """Дублирующая запись (lot_type, lot_id) → IntegrityError."""
    profile = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    fixed_id = "00000000-0000-0000-0000-0000000000aa"
    FeedLotShrinkageState.objects.create(
        organization=org,
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=fixed_id,
        profile=profile,
        initial_quantity=Decimal("100"),
        accumulated_loss=Decimal("0"),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeedLotShrinkageState.objects.create(
                organization=org,
                lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
                lot_id=fixed_id,  # дубликат
                profile=profile,
                initial_quantity=Decimal("100"),
                accumulated_loss=Decimal("0"),
            )
