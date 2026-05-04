"""
Тесты post_feed_consumption — скармливание корма партии откорма.

Покрывают:
  - happy path: списание со склада + JE Дт 20.02 / Кт 10.05 + cost накапливается на batch
  - rejected feed_batch
  - недостаточно корма
  - неактивная партия откорма (shipped)
  - расчёт period_fcr при наличии взвешиваний
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.accounting.models import GLAccount, GLSubaccount, JournalEntry
from apps.batches.models import Batch
from apps.feed.models import FeedBatch, ProductionTask, Recipe, RecipeVersion
from apps.feedlot.models import (
    DailyWeighing,
    FeedlotBatch,
    FeedlotFeedConsumption,
)
from apps.feedlot.services.feed_consumption import (
    FeedConsumptionError,
    post_feed_consumption,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="fcons@y.local", full_name="FC")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "Голов"}
    )[0]


@pytest.fixture
def cat_chick(org):
    return Category.objects.get_or_create(
        organization=org, name="Птица живая (тест)"
    )[0]


@pytest.fixture
def chick_nom(org, cat_chick, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ТЦ-БР-01", name="Бройлер тест",
        category=cat_chick, unit=unit_pcs,
    )


@pytest.fixture
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-Т-1",
        name="Птичник-Т1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def chick_batch(org, m_feedlot, house, chick_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-Т-ЦБ-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date(2026, 4, 1),
    )


@pytest.fixture
def feedlot_batch(org, m_feedlot, house, chick_batch, user):
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=house, batch=chick_batch,
        doc_number="ФЛ-Т-001", placed_date=date(2026, 4, 1),
        target_weight_kg=Decimal("2.500"),
        initial_heads=10000, current_heads=10000,
        status=FeedlotBatch.Status.GROWING,
        technologist=user,
    )


@pytest.fixture
def cat_feed(org):
    return Category.objects.get_or_create(
        organization=org, name="Корма (тест)"
    )[0]


@pytest.fixture
def feed_nom(org, cat_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ГК-СТ-01", name="Старт бройлер тест",
        category=cat_feed, unit=unit_kg,
    )


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="R-T-START",
        name="Старт тест", direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def production_task(org, m_feed, recipe_version, user):
    return ProductionTask.objects.create(
        organization=org, module=m_feed,
        doc_number="ЗМ-Т-1", recipe_version=recipe_version,
        production_line=ProductionBlock.objects.create(
            organization=org, module=m_feed, code="ЛТ-1",
            name="Линия тест", kind=ProductionBlock.Kind.MIXER_LINE,
        ),
        shift="day", scheduled_at=date(2026, 4, 1),
        planned_quantity_kg=Decimal("1000"),
        actual_quantity_kg=Decimal("1000"),
        status="done",
        technologist=user,
    )


@pytest.fixture
def storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БНТ-1",
        name="Бункер тест", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def feed_warehouse(org, m_feed, storage_bin):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-ГК-Т", name="Склад ГК тест",
        production_block=storage_bin,
    )


@pytest.fixture
def feed_batch(org, m_feed, recipe_version, production_task, storage_bin, feed_warehouse):
    return FeedBatch.objects.create(
        organization=org, module=m_feed,
        doc_number="ГК-Т-001",
        produced_by_task=production_task,
        recipe_version=recipe_version,
        produced_at=date(2026, 4, 1),
        quantity_kg=Decimal("1000"),
        current_quantity_kg=Decimal("1000"),
        unit_cost_uzs=Decimal("3000"),
        total_cost_uzs=Decimal("3000000"),
        storage_bin=storage_bin,
        storage_warehouse=feed_warehouse,
        status=FeedBatch.Status.APPROVED,
        quality_passport_status=FeedBatch.PassportStatus.PASSED,
    )


@pytest.fixture
def chart_of_accounts(org):
    """Создаём минимальный план счетов: 20.02 (НЗП Откорм), 10.05 (ГК Корма)."""
    acc_20, _ = GLAccount.objects.get_or_create(
        organization=org, code="20",
        defaults={"name": "Производство", "type": "asset"},
    )
    acc_10, _ = GLAccount.objects.get_or_create(
        organization=org, code="10",
        defaults={"name": "Материалы", "type": "asset"},
    )
    GLSubaccount.objects.get_or_create(
        account=acc_20, code="20.02",
        defaults={"name": "Откорм НЗП"},
    )
    GLSubaccount.objects.get_or_create(
        account=acc_10, code="10.05",
        defaults={"name": "Готовая продукция корма"},
    )


# ─── Тесты ───────────────────────────────────────────────────────────────


def test_post_feed_consumption_happy_path(
    feedlot_batch, feed_batch, chart_of_accounts, user,
):
    """
    Скармливаем 100 кг корма стоимостью 3000/кг = 300 000 сум.
    Проверяем: списание со склада, JE, накопление cost на batch, per_head_g.
    """
    feed_batch_initial = feed_batch.current_quantity_kg
    batch_cost_initial = feedlot_batch.batch.accumulated_cost_uzs

    result = post_feed_consumption(
        feedlot_batch,
        feed_batch=feed_batch,
        total_kg=Decimal("100"),
        period_from_day=1,
        period_to_day=7,
        feed_type="start",
        notes="первая неделя",
        user=user,
    )

    # FeedBatch уменьшился на 100
    feed_batch.refresh_from_db()
    assert feed_batch.current_quantity_kg == feed_batch_initial - Decimal("100")

    # FeedlotFeedConsumption создан
    assert FeedlotFeedConsumption.objects.filter(
        feedlot_batch=feedlot_batch
    ).count() == 1
    assert result.consumption.total_kg == Decimal("100")
    assert result.consumption.feed_type == "start"
    # per_head_g = 100 кг × 1000 / 10000 голов = 10 г/гол
    assert result.consumption.per_head_g == Decimal("10.000")
    # period_fcr = None т.к. нет взвешиваний
    assert result.consumption.period_fcr is None

    # Cost накопился на batch (накопил 100 × 3000 = 300 000)
    feedlot_batch.batch.refresh_from_db()
    assert feedlot_batch.batch.accumulated_cost_uzs == (
        batch_cost_initial + Decimal("300000")
    )

    # JE Дт 20.02 / Кт 10.05 на 300 000
    assert result.amount_uzs == Decimal("300000.00")
    assert result.journal_entry.debit_subaccount.code == "20.02"
    assert result.journal_entry.credit_subaccount.code == "10.05"
    assert result.journal_entry.amount_uzs == Decimal("300000.00")


def test_post_feed_consumption_with_weighings_computes_fcr(
    feedlot_batch, feed_batch, chart_of_accounts, user,
):
    """
    Если есть взвешивания на границах периода — period_fcr считается.

    День 1: avg=0.05 кг (50 г)
    День 7: avg=0.20 кг (200 г)
    Прирост на голову = 0.15 кг × 10000 голов = 1500 кг
    Скормили 100 кг → period_fcr = 100 / 1500 = 0.067
    """
    DailyWeighing.objects.create(
        feedlot_batch=feedlot_batch, date=date(2026, 4, 1),
        day_of_age=1, sample_size=50, avg_weight_kg=Decimal("0.050"),
    )
    DailyWeighing.objects.create(
        feedlot_batch=feedlot_batch, date=date(2026, 4, 7),
        day_of_age=7, sample_size=50, avg_weight_kg=Decimal("0.200"),
    )

    result = post_feed_consumption(
        feedlot_batch,
        feed_batch=feed_batch,
        total_kg=Decimal("100"),
        period_from_day=1,
        period_to_day=7,
        feed_type="start",
        user=user,
    )

    assert result.consumption.period_fcr is not None
    # 100 / 1500 ≈ 0.067
    assert result.consumption.period_fcr < Decimal("0.1")


def test_post_feed_consumption_insufficient_stock_raises(
    feedlot_batch, feed_batch, chart_of_accounts, user,
):
    """Если корма меньше чем требуется — ValidationError."""
    with pytest.raises(FeedConsumptionError) as exc:
        post_feed_consumption(
            feedlot_batch,
            feed_batch=feed_batch,
            total_kg=Decimal("99999"),  # > 1000
            period_from_day=1, period_to_day=7,
            feed_type="start",
            user=user,
        )
    assert "Недостаточно остатка" in str(exc.value.message_dict)


def test_post_feed_consumption_rejected_batch_raises(
    feedlot_batch, feed_batch, chart_of_accounts, user,
):
    """Если feed_batch не APPROVED — ValidationError."""
    feed_batch.status = FeedBatch.Status.REJECTED
    feed_batch.save(update_fields=["status"])

    with pytest.raises(FeedConsumptionError) as exc:
        post_feed_consumption(
            feedlot_batch,
            feed_batch=feed_batch,
            total_kg=Decimal("100"),
            period_from_day=1, period_to_day=7,
            feed_type="start",
            user=user,
        )
    assert "Отклонена" in str(exc.value.message_dict) or "одобренную" in str(
        exc.value.message_dict
    )


def test_post_feed_consumption_shipped_feedlot_raises(
    feedlot_batch, feed_batch, chart_of_accounts, user,
):
    """Если feedlot_batch отгружена — ValidationError."""
    feedlot_batch.status = FeedlotBatch.Status.SHIPPED
    feedlot_batch.save(update_fields=["status"])

    with pytest.raises(FeedConsumptionError) as exc:
        post_feed_consumption(
            feedlot_batch,
            feed_batch=feed_batch,
            total_kg=Decimal("100"),
            period_from_day=1, period_to_day=7,
            feed_type="start",
            user=user,
        )
    assert "активную" in str(exc.value.message_dict)
