"""
Тесты post_feed_consumption: авто-списание корма при создании BFC.

Сценарии:
    1. Happy path: Дт 20.01 / Кт 10.05 + FeedBatch.current_quantity_kg уменьшается.
    2. Если есть ACTIVE egg-батч стада → создаётся BatchCostEntry(FEED) + accumulated_cost обновляется.
    3. Если нет active egg-батча → только JE и декремент (без BCE).
    4. quantity_kg > current_quantity_kg → ValidationError.
    5. feed_batch=None → только сохранение BFC, без JE.
    6. FeedBatch становится DEPLETED если остаток=0.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch, BatchCostEntry
from apps.feed.models import FeedBatch, ProductionTask, Recipe, RecipeVersion
from apps.matochnik.models import (
    BreedingFeedConsumption,
    BreedingHerd,
    DailyEggProduction,
)
from apps.matochnik.services.post_feed_consumption import (
    FeedConsumptionPostError,
    post_feed_consumption,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


# ─── Фикстуры ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="pfc@y.local", full_name="PFC")


@pytest.fixture
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik, code="КС-PFC",
        name="Корпус", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def feed_block(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СИЛ-01",
        name="Силос", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def herd(org, m_matochnik, block, user):
    return BreedingHerd.objects.create(
        organization=org, module=m_matochnik, block=block,
        doc_number="СТ-PFC-01",
        direction=BreedingHerd.Direction.LAYER_PARENT,
        placed_at=date(2026, 1, 1),
        initial_heads=5000, current_heads=5000,
        age_weeks_at_placement=25,
        status=BreedingHerd.Status.PRODUCING,
        technologist=user,
    )


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def feed_batch(org, m_feed, feed_block):
    """FeedBatch 1000 кг по 1500 сум/кг → 1.5M сум total."""
    from apps.feed.models import Recipe, RecipeVersion, ProductionTask
    recipe = Recipe.objects.create(
        organization=org, code="РЕЦ-PFC", name="Рецепт",
        direction="layer", is_medicated=False,
    )
    rv = RecipeVersion.objects.create(
        recipe=recipe, version_number=1, status=RecipeVersion.Status.ACTIVE,
        effective_from=date(2026, 1, 1),
    )
    line = ProductionBlock.objects.create(
        organization=org, module=m_feed, code="ЛН-PFC",
        name="Линия", kind=ProductionBlock.Kind.MIXER_LINE,
    )
    task = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ПЗ-PFC-01",
        recipe_version=rv, production_line=line,
        scheduled_at=datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.DONE,
        technologist=User.objects.create(email="tech@pfc.local", full_name="T"),
    )
    return FeedBatch.objects.create(
        organization=org, module=m_feed,
        doc_number="ФБ-PFC-01",
        produced_by_task=task,
        recipe_version=rv,
        produced_at=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
        quantity_kg=Decimal("1000"),
        current_quantity_kg=Decimal("1000"),
        unit_cost_uzs=Decimal("1500.000000"),
        total_cost_uzs=Decimal("1500000"),
        storage_bin=feed_block,
        status=FeedBatch.Status.APPROVED,
    )


@pytest.fixture
def egg_nomenclature(org, unit_kg):
    cat = Category.objects.get_or_create(
        organization=org, name="Яйца", defaults={},
    )[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="ЯЙЦ-ИНК-01", name="Инкубационное яйцо",
        category=cat, unit=unit_kg,
    )


@pytest.fixture
def active_egg_batch(org, m_matochnik, herd, egg_nomenclature, unit_kg, block):
    """Активная яичная партия, связанная со стадом через DailyEggProduction."""
    batch = Batch.objects.create(
        organization=org, doc_number="П-ЯЙЦ-PFC-01",
        nomenclature=egg_nomenclature, unit=unit_kg,
        origin_module=m_matochnik, current_module=m_matochnik,
        current_block=block,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("0"),
        state=Batch.State.ACTIVE, started_at=date(2026, 4, 1),
    )
    DailyEggProduction.objects.create(
        herd=herd, date=date(2026, 4, 20),
        eggs_collected=500, unfit_eggs=0,
        outgoing_batch=batch,
    )
    return batch


def _sub(org, code: str):
    return GLSubaccount.objects.get(account__organization=org, code=code)


# ─── Тесты ───────────────────────────────────────────────────────────────


def test_happy_path_creates_je_and_decrements_feed(
    herd, feed_batch, active_egg_batch
):
    """Списали 100 кг → JE на 150k, FeedBatch = 900 кг, BCE на egg-партии."""
    bfc = BreedingFeedConsumption.objects.create(
        herd=herd, date=date(2026, 4, 24),
        feed_batch=feed_batch, quantity_kg=Decimal("100"),
    )
    result = post_feed_consumption(bfc)

    # 1. Стоимость посчитана
    assert result.total_cost_uzs == Decimal("150000.00")

    # 2. FeedBatch уменьшен
    feed_batch.refresh_from_db()
    assert feed_batch.current_quantity_kg == Decimal("900.000")

    # 3. JournalEntry создан Дт 20.01 / Кт 10.05
    je = result.journal_entry
    assert je is not None
    assert je.debit_subaccount.code == "20.01"
    assert je.credit_subaccount.code == "10.05"
    assert je.amount_uzs == Decimal("150000.00")
    assert je.module.code == "matochnik"

    # 4. BatchCostEntry на egg-батче
    bce = result.batch_cost_entry
    assert bce is not None
    assert bce.batch_id == active_egg_batch.id
    assert bce.category == BatchCostEntry.Category.FEED
    assert bce.amount_uzs == Decimal("150000.00")

    # 5. accumulated_cost партии обновлён
    active_egg_batch.refresh_from_db()
    assert active_egg_batch.accumulated_cost_uzs == Decimal("150000.00")


def test_no_active_egg_batch_skips_bce(herd, feed_batch, org):
    """Нет ACTIVE egg-батча → только JE, без BatchCostEntry."""
    bfc = BreedingFeedConsumption.objects.create(
        herd=herd, date=date(2026, 4, 24),
        feed_batch=feed_batch, quantity_kg=Decimal("50"),
    )
    result = post_feed_consumption(bfc)

    assert result.journal_entry is not None
    assert result.batch_cost_entry is None
    assert result.egg_batch is None


def test_no_feed_batch_skips_posting(herd):
    """BFC без feed_batch — ничего не посчитаем, только журналим."""
    bfc = BreedingFeedConsumption.objects.create(
        herd=herd, date=date(2026, 4, 24),
        feed_batch=None, quantity_kg=Decimal("10"),
    )
    result = post_feed_consumption(bfc)

    assert result.journal_entry is None
    assert result.batch_cost_entry is None
    assert result.total_cost_uzs == Decimal("0")


def test_insufficient_feed_batch_raises(herd, feed_batch):
    """Списать больше чем есть → ValidationError."""
    bfc = BreedingFeedConsumption.objects.create(
        herd=herd, date=date(2026, 4, 24),
        feed_batch=feed_batch, quantity_kg=Decimal("2000"),  # > 1000
    )
    with pytest.raises(ValidationError):
        post_feed_consumption(bfc)


def test_feed_batch_depleted_when_emptied(herd, feed_batch):
    """Списываем весь корм → FeedBatch.status=DEPLETED."""
    bfc = BreedingFeedConsumption.objects.create(
        herd=herd, date=date(2026, 4, 24),
        feed_batch=feed_batch, quantity_kg=Decimal("1000"),
    )
    post_feed_consumption(bfc)
    feed_batch.refresh_from_db()
    assert feed_batch.current_quantity_kg == Decimal("0.000")
    assert feed_batch.status == FeedBatch.Status.DEPLETED
