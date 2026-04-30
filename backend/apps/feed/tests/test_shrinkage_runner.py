"""
Тесты периодической усушки (apps.feed.services.shrinkage_runner).

Покрывают:
  - чистую функцию _compute_loss: компаундный расчёт, max-лимит
  - apply_to_lot: happy, grace, frozen, no_profile, depleted,
    идемпотентность, max_total_percent, stop_after_days
  - apply_for_organization: батч-прогон по нескольким партиям
  - reset_lot_shrinkage: откат state + StockMovement
  - резолвер профиля: warehouse-specific приоритетен
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedLotShrinkageState,
    FeedShrinkageProfile,
    RawMaterialBatch,
)
from apps.feed.services.shrinkage_runner import (
    _compute_loss,
    apply_for_organization,
    apply_for_specific_lot,
    apply_to_lot,
    reset_lot_shrinkage,
    _build_lot_info,
    _find_profile,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.warehouses.models import StockMovement, Warehouse


# ─── fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_grain(org):
    return Category.objects.get_or_create(
        organization=org, name="Зерно (runner test)",
    )[0]


@pytest.fixture
def wheat(org, cat_grain, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TR-WHT", name="Пшеница тест runner",
        category=cat_grain, unit=unit_kg,
    )


@pytest.fixture
def corn(org, cat_grain, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="TR-CRN", name="Кукуруза тест runner",
        category=cat_grain, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.get_or_create(
        organization=org, code="K-RUNNER", kind="supplier",
        defaults={"name": "Поставщик runner"},
    )[0]


@pytest.fixture
def wh1(org, m_feed):
    return Warehouse.objects.get_or_create(
        organization=org, code="СК-Р1",
        defaults={"module": m_feed, "name": "Склад runner 1"},
    )[0]


@pytest.fixture
def wh2(org, m_feed):
    return Warehouse.objects.get_or_create(
        organization=org, code="СК-Р2",
        defaults={"module": m_feed, "name": "Склад runner 2"},
    )[0]


def _make_raw_batch(*, org, module, nomenclature, supplier, warehouse, unit,
                    received_on, qty=Decimal("1000"), price=Decimal("100"),
                    doc_suffix="A"):
    """Хелпер: создаёт RawMaterialBatch со статусом AVAILABLE."""
    return RawMaterialBatch.objects.create(
        organization=org,
        module=module,
        doc_number=f"СЫР-RUN-{doc_suffix}-{received_on:%Y%m%d}",
        nomenclature=nomenclature,
        supplier=supplier,
        warehouse=warehouse,
        received_date=received_on,
        quantity=qty,
        current_quantity=qty,
        unit=unit,
        price_per_unit_uzs=price,
        status=RawMaterialBatch.Status.AVAILABLE,
    )


# ─── чистая функция _compute_loss ─────────────────────────────────────────


def test_compute_loss_zero_when_no_periods():
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("0.8"),
        max_total_pct=None,
        periods=0,
    )
    assert loss == Decimal("0")
    assert not hit_max


def test_compute_loss_one_period_simple():
    """1000 кг × 0.8% = 8.0 кг."""
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("0.8"),
        max_total_pct=None,
        periods=1,
    )
    assert loss == Decimal("8.000")
    assert not hit_max


def test_compute_loss_compound_two_periods():
    """1000 → 992 → 984.06 (компаунд)."""
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("0.8"),
        max_total_pct=None,
        periods=2,
    )
    # 8 + 7.936 = 15.936 → 15.936
    assert loss == Decimal("15.936")
    assert not hit_max


def test_compute_loss_hits_max_total_percent():
    """С max_total=5% и pct=2%/период за 4 периода ожидаем заморозку."""
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("2.0"),
        max_total_pct=Decimal("5.0"),
        periods=10,
    )
    # лимит 50 кг от initial
    assert loss == Decimal("50.000")
    assert hit_max


def test_compute_loss_respects_existing_accumulated():
    """Если уже накопили 3% — новый цикл может дать только 2% до лимита 5%."""
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("970"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("30"),
        pct_per_period=Decimal("5.0"),
        max_total_pct=Decimal("5.0"),
        periods=2,
    )
    assert loss == Decimal("20.000")
    assert hit_max


# ─── apply_to_lot: интеграция ─────────────────────────────────────────────


@pytest.mark.django_db
def test_apply_no_profile_skips(org, m_feed, wheat, supplier, wh1, unit_kg):
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert result.skipped
    assert result.skipped_reason == "no_profile"
    assert not FeedLotShrinkageState.objects.filter(lot_id=batch.id).exists()


@pytest.mark.django_db
def test_apply_grace_period_skips(org, m_feed, wheat, supplier, wh1, unit_kg):
    today = date(2026, 5, 1)
    received = today - timedelta(days=2)  # 2 дня <  grace 3
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg, received_on=received,
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        starts_after_days=3,
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert result.skipped
    assert result.skipped_reason == "grace_period"


@pytest.mark.django_db
def test_apply_first_period_creates_state_and_movement(
    org, m_feed, wheat, supplier, wh1, unit_kg
):
    today = date(2026, 5, 1)
    received = today - timedelta(days=10)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=received, qty=Decimal("1000"), price=Decimal("100"),
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        starts_after_days=3,
    )

    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)

    assert not result.skipped
    # 10 дней с поступления, period=7 → 1 полный период
    assert result.periods_applied == 1
    assert result.loss_kg == Decimal("8.000")
    assert not result.frozen

    # state создан
    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    assert state.accumulated_loss == Decimal("8.000")
    assert state.last_applied_on == today
    assert state.initial_quantity == Decimal("1000")

    # current_quantity партии уменьшен
    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("992.000")

    # StockMovement создан
    mov = StockMovement.objects.get(id=result.movement_id)
    assert mov.kind == StockMovement.Kind.SHRINKAGE
    assert mov.quantity == Decimal("8.000")
    assert mov.warehouse_from_id == wh1.id
    assert mov.amount_uzs == Decimal("800.00")  # 8 × 100


@pytest.mark.django_db
def test_apply_idempotent_on_same_day(org, m_feed, wheat, supplier, wh1, unit_kg):
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))

    r1 = apply_to_lot(lot, today)
    assert not r1.skipped

    # повторный запуск той же датой → ничего не делать
    lot2 = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    r2 = apply_to_lot(lot2, today)
    assert r2.skipped
    assert r2.skipped_reason == "already_applied_today"

    # одно движение всего
    movements = StockMovement.objects.filter(
        kind=StockMovement.Kind.SHRINKAGE,
        source_object_id=FeedLotShrinkageState.objects.get(lot_id=batch.id).id,
    )
    assert movements.count() == 1


@pytest.mark.django_db
def test_apply_freezes_at_max_total_percent(
    org, m_feed, wheat, supplier, wh1, unit_kg
):
    """С max_total=5% за достаточно большое число периодов state замораживается."""
    today = date(2026, 8, 1)
    received = today - timedelta(days=70)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=received, qty=Decimal("1000"),
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        max_total_percent=Decimal("5.0"),
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert not result.skipped
    assert result.frozen

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    assert state.is_frozen
    # лимит ровно 50 кг от initial=1000
    assert state.accumulated_loss == Decimal("50.000")


@pytest.mark.django_db
def test_apply_freezes_at_stop_after_days(
    org, m_feed, wheat, supplier, wh1, unit_kg
):
    today = date(2026, 8, 1)
    received = today - timedelta(days=120)  # > stop_after_days=90
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg, received_on=received,
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        stop_after_days=90,
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    # один последний цикл случился, но state заморожен
    assert result.frozen


@pytest.mark.django_db
def test_apply_skipped_when_frozen(org, m_feed, wheat, supplier, wh1, unit_kg):
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    profile = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )
    FeedLotShrinkageState.objects.create(
        organization=org,
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=batch.id,
        profile=profile,
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("50"),
        is_frozen=True,
    )
    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert result.skipped
    assert result.skipped_reason == "frozen"


# ─── профиль резолвер ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_warehouse_specific_profile_wins_over_generic(
    org, m_feed, wheat, supplier, wh1, wh2, unit_kg
):
    """Когда есть и общий, и склад-специфичный профили — побеждает склад-специфичный."""
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    # Общий профиль на 0.5%
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.5"),
    )
    # Склад-специфичный на 1.5% — должен победить
    specific = FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        warehouse=wh1,
        period_days=7,
        percent_per_period=Decimal("1.5"),
    )

    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    found = _find_profile(lot)
    assert found.id == specific.id


# ─── apply_for_organization батч-прогон ───────────────────────────────────


@pytest.mark.django_db
def test_apply_for_organization_iterates_all_lots(
    org, m_feed, wheat, corn, supplier, wh1, unit_kg
):
    today = date(2026, 5, 1)
    received = today - timedelta(days=10)
    b1 = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg, received_on=received,
        doc_suffix="W",
    )
    b2 = _make_raw_batch(
        org=org, module=m_feed, nomenclature=corn,
        supplier=supplier, warehouse=wh1, unit=unit_kg, received_on=received,
        doc_suffix="C",
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7, percent_per_period=Decimal("0.8"),
    )
    # для corn профиля нет → должна быть пропущена

    results = apply_for_organization(org, today=today)
    by_lot = {r.lot_id: r for r in results}

    assert by_lot[str(b1.id)].skipped is False
    assert by_lot[str(b2.id)].skipped is True
    assert by_lot[str(b2.id)].skipped_reason == "no_profile"


# ─── reset ────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_reset_lot_shrinkage_undoes_movement_and_state(
    org, m_feed, wheat, supplier, wh1, unit_kg
):
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
        qty=Decimal("1000"),
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7, percent_per_period=Decimal("0.8"),
    )

    apply_for_specific_lot(
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=str(batch.id),
        today=today,
    )

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    assert state.accumulated_loss == Decimal("8.000")

    info = reset_lot_shrinkage(state)
    assert info["reverted_movements"] == 1
    assert info["restored_kg"] == Decimal("8.000")

    state.refresh_from_db()
    assert state.accumulated_loss == Decimal("0")
    assert state.last_applied_on is None
    assert not state.is_frozen

    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("1000.000")

    assert StockMovement.objects.filter(
        kind=StockMovement.Kind.SHRINKAGE,
        source_object_id=state.id,
    ).count() == 0


# ─── Spec §A: воспроизведение примера из спецификации ────────────────────


def test_compute_loss_matches_spec_appendix_a():
    """
    Spec §Приложение A: партия 1000 кг, профиль 0.8% / 7д, max 5%, grace 3д.

    Через 52 дня (т.е. 7 полных периодов после grace) накопленные потери
    должны быть ровно 5% (50 кг) — алгоритм урезает последнюю дельту до лимита.
    Проверяем совпадение с расчётной таблицей в спецификации.
    """
    # 7 периодов: должно зафиксироваться на 50 кг и hit_max
    loss, hit_max = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("0.8"),
        max_total_pct=Decimal("5.0"),
        periods=7,
    )
    assert loss == Decimal("50.000")
    assert hit_max is True

    # 6 периодов: НЕ упёрлись в лимит, накапливаем компаундно
    # Δ1=8.000, остаток=992; Δ2=7.936, ост=984.064; ...
    loss6, hit_max6 = _compute_loss(
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        pct_per_period=Decimal("0.8"),
        max_total_pct=Decimal("5.0"),
        periods=6,
    )
    # Сумма дельт за 6 периодов ≈ 47.05 кг (всё ещё < 50 = max)
    assert loss6 < Decimal("50")
    assert loss6 > Decimal("46")
    assert hit_max6 is False


# ─── FeedBatch (готовый корм) ─────────────────────────────────────────────


@pytest.fixture
def recipe(org):
    """Рецепт для готового корма."""
    from apps.feed.models import Recipe
    return Recipe.objects.create(
        organization=org, code="STARTER", name="Стартёр", direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    """Активная версия рецепта."""
    from apps.feed.models import RecipeVersion
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status=RecipeVersion.Status.ACTIVE,
        effective_from=date(2026, 1, 1),
    )


def _make_feed_batch(*, org, m_feed, recipe_version, warehouse, doc, qty="500"):
    """Хелпер: создаёт FeedBatch со статусом APPROVED + production_block."""
    from apps.feed.models import FeedBatch, ProductionTask
    from apps.warehouses.models import ProductionBlock

    storage_bin = ProductionBlock.objects.create(
        organization=org, module=m_feed,
        code=f"BIN-{doc}", name="Бункер test",
        kind=ProductionBlock.Kind.STORAGE_BIN,
    )
    line = ProductionBlock.objects.create(
        organization=org, module=m_feed,
        code=f"LINE-{doc}", name="Линия test",
        kind=ProductionBlock.Kind.MIXER_LINE,
    )
    # Минимальный technologist — берём первого пользователя или создаём
    from apps.users.models import User
    tech = User.objects.create(email=f"tech-{doc}@y.local", full_name="T")
    task = ProductionTask.objects.create(
        organization=org, module=m_feed,
        doc_number=f"ЗМ-{doc}",
        recipe_version=recipe_version,
        production_line=line,
        scheduled_at=datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc),
        planned_quantity_kg=Decimal(qty),
        status=ProductionTask.Status.DONE,
        technologist=tech,
    )
    return FeedBatch.objects.create(
        organization=org, module=m_feed,
        doc_number=f"ГК-{doc}",
        produced_by_task=task,
        recipe_version=recipe_version,
        produced_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
        quantity_kg=Decimal(qty),
        current_quantity_kg=Decimal(qty),
        unit_cost_uzs=Decimal("250.000000"),
        total_cost_uzs=Decimal(qty) * Decimal("250"),
        storage_bin=storage_bin,
        storage_warehouse=warehouse,
        status=FeedBatch.Status.APPROVED,
    )


@pytest.mark.django_db
def test_apply_to_feed_batch_creates_state_and_decrements(
    org, m_feed, recipe, recipe_version, wh1,
):
    """Готовый корм усыхает по профилю target_type=feed_type."""
    today = date(2026, 5, 1)  # +11 дней с produced_at
    batch = _make_feed_batch(
        org=org, m_feed=m_feed, recipe_version=recipe_version,
        warehouse=wh1, doc="FEED-A", qty="500",
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.FEED_TYPE,
        recipe=recipe,
        period_days=7,
        percent_per_period=Decimal("0.4"),
    )

    lot = _build_lot_info(
        FeedLotShrinkageState.LotType.PRODUCTION_BATCH,
        str(batch.id),
    )
    result = apply_to_lot(lot, today)

    assert not result.skipped
    assert result.periods_applied == 1
    assert result.loss_kg == Decimal("2.000")  # 500 × 0.4%

    batch.refresh_from_db()
    assert batch.current_quantity_kg == Decimal("498.000")

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    assert state.lot_type == FeedLotShrinkageState.LotType.PRODUCTION_BATCH


@pytest.mark.django_db
def test_feed_batch_profile_for_different_recipe_does_not_match(
    org, m_feed, recipe, recipe_version, wh1,
):
    """Профиль на recipe A не применяется к партии recipe B."""
    today = date(2026, 5, 1)
    batch = _make_feed_batch(
        org=org, m_feed=m_feed, recipe_version=recipe_version,
        warehouse=wh1, doc="FEED-B", qty="500",
    )

    # Профиль на ДРУГОЙ recipe
    from apps.feed.models import Recipe
    other_recipe = Recipe.objects.create(
        organization=org, code="FINISHER", name="Финишер", direction="broiler",
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.FEED_TYPE,
        recipe=other_recipe,
        period_days=7,
        percent_per_period=Decimal("0.4"),
    )

    lot = _build_lot_info(
        FeedLotShrinkageState.LotType.PRODUCTION_BATCH,
        str(batch.id),
    )
    result = apply_to_lot(lot, today)
    assert result.skipped
    assert result.skipped_reason == "no_profile"


# ─── Multi-org isolation ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_profile_from_different_org_does_not_apply():
    """Профиль из orgA не должен подхватываться партией orgB."""
    from apps.organizations.models import Organization

    org_a = Organization.objects.get(code="DEFAULT")
    # Вторая организация
    org_b = Organization.objects.create(code="OTHER", name="Другая орг")
    m_feed = Module.objects.get(code="feed")

    cat = Category.objects.create(organization=org_b, name="Зерно other-org")
    unit = Unit.objects.create(organization=org_b, code="кг", name="кг")
    nom_b = NomenclatureItem.objects.create(
        organization=org_b, sku="OTHER-WHT", name="Пшеница other",
        category=cat, unit=unit,
    )
    cp_b = Counterparty.objects.create(
        organization=org_b, code="K-OTHER", kind="supplier", name="Постав other",
    )
    wh_b = Warehouse.objects.create(
        organization=org_b, module=m_feed, code="СК-O1", name="Склад other",
    )
    batch_b = RawMaterialBatch.objects.create(
        organization=org_b, module=m_feed,
        doc_number="СЫР-OTHER-1",
        nomenclature=nom_b, supplier=cp_b, warehouse=wh_b,
        received_date=date(2026, 4, 20),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit, price_per_unit_uzs=Decimal("100"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )

    # Профиль создан только в org_a (первая партия органа auto-create)
    # Удалим автосозданные профили чтобы не мешали
    FeedShrinkageProfile.objects.all().delete()

    # Создаём профиль ТОЛЬКО в org_a с такой же номенклатурой по sku
    nom_a_cat = Category.objects.create(organization=org_a, name="Зерно org-a")
    unit_a = Unit.objects.get_or_create(
        organization=org_a, code="кг", defaults={"name": "кг"},
    )[0]
    nom_a = NomenclatureItem.objects.create(
        organization=org_a, sku="OTHER-WHT", name="Пшеница org_a",
        category=nom_a_cat, unit=unit_a,
    )
    FeedShrinkageProfile.objects.create(
        organization=org_a,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=nom_a,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    # Прогон для org_a — не должен трогать org_b
    results_a = apply_for_organization(org_a, today=date(2026, 5, 1))
    org_b_in_results = [r for r in results_a if r.lot_id == str(batch_b.id)]
    assert org_b_in_results == []

    # И наоборот: прогон для org_b не должен видеть профиль org_a
    results_b = apply_for_organization(org_b, today=date(2026, 5, 1))
    batch_b_results = [r for r in results_b if r.lot_id == str(batch_b.id)]
    assert len(batch_b_results) == 1
    assert batch_b_results[0].skipped
    assert batch_b_results[0].skipped_reason == "no_profile"


# ─── Partial consumption (расход между циклами) ──────────────────────────


@pytest.mark.django_db
def test_apply_uses_current_quantity_after_partial_consumption(
    org, m_feed, wheat, supplier, wh1, unit_kg,
):
    """
    Если партия частично израсходована между циклами (current_quantity
    меньше initial_quantity-accumulated_loss), усушка считается от ТЕКУЩЕГО
    остатка, а не от теоретического. Это гарантирует, что суммарная масса
    списания не превышает реальный остаток.
    """
    today = date(2026, 5, 1)
    received = today - timedelta(days=10)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=received, qty=Decimal("1000"),
    )
    # Имитируем частичный расход: партия отдала 600 кг на замес
    batch.current_quantity = Decimal("400")
    batch.save(update_fields=["current_quantity"])

    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("1.0"),
    )

    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)

    # 1% от 400 кг (текущий остаток), не от 1000 (initial)
    assert result.loss_kg == Decimal("4.000")

    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("396.000")


# ─── Профиль склад=NULL применяется когда нет специфичного ───────────────


@pytest.mark.django_db
def test_generic_profile_applies_when_no_warehouse_specific(
    org, m_feed, wheat, supplier, wh1, unit_kg,
):
    """Если для склада нет конкретного профиля, применяется общий (warehouse=NULL)."""
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    # Только общий профиль, без конкретного склада
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        warehouse=None,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert not result.skipped


# ─── Inactive profile is ignored ──────────────────────────────────────────


@pytest.mark.django_db
def test_inactive_profile_is_skipped(org, m_feed, wheat, supplier, wh1, unit_kg):
    today = date(2026, 5, 1)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=today - timedelta(days=10),
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
        is_active=False,  # выкл
    )

    lot = _build_lot_info(FeedLotShrinkageState.LotType.RAW_ARRIVAL, str(batch.id))
    result = apply_to_lot(lot, today)
    assert result.skipped
    assert result.skipped_reason == "no_profile"


# ─── Sequential cycles: idempotent + cumulative ──────────────────────────


@pytest.mark.django_db
def test_two_consecutive_cycles_accumulate_correctly(
    org, m_feed, wheat, supplier, wh1, unit_kg,
):
    """
    Цикл 1 на день +10 → 1 период; цикл 2 на день +17 → ещё 1 период.
    Накопленная потеря должна быть суммой обеих дельт (компаундно).
    """
    received = date(2026, 4, 20)
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=received,
    )
    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("1.0"),  # 1% для красивых чисел
    )

    # Цикл 1: +10 дней → 1 период
    apply_for_specific_lot(
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=str(batch.id),
        today=date(2026, 4, 30),
    )
    # Цикл 2: +17 дней → +1 период
    apply_for_specific_lot(
        lot_type=FeedLotShrinkageState.LotType.RAW_ARRIVAL,
        lot_id=str(batch.id),
        today=date(2026, 5, 7),
    )

    state = FeedLotShrinkageState.objects.get(lot_id=batch.id)
    # Δ1 = 1000 × 1% = 10 кг → остаток 990
    # Δ2 = 990 × 1% = 9.9 кг → накоплено 19.9
    assert state.accumulated_loss == Decimal("19.900")
    assert state.last_applied_on == date(2026, 5, 7)

    # Два движения
    assert StockMovement.objects.filter(
        kind=StockMovement.Kind.SHRINKAGE,
        source_object_id=state.id,
    ).count() == 2

    # Партия похудела на 19.9
    batch.refresh_from_db()
    assert batch.current_quantity == Decimal("980.100")


# ─── Status filtering: только AVAILABLE ───────────────────────────────────


@pytest.mark.django_db
def test_quarantine_batch_not_picked_up(
    org, m_feed, wheat, supplier, wh1, unit_kg,
):
    """Партии в карантине воркер не подхватывает в orgwide-прогоне."""
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=date(2026, 4, 20),
    )
    batch.status = RawMaterialBatch.Status.QUARANTINE
    batch.save(update_fields=["status"])

    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    results = apply_for_organization(org, today=date(2026, 5, 1))
    in_carantine = [r for r in results if r.lot_id == str(batch.id)]
    # Партия в карантине не попадает в _collect_raw_lots
    assert in_carantine == []


@pytest.mark.django_db
def test_depleted_batch_not_picked_up(
    org, m_feed, wheat, supplier, wh1, unit_kg,
):
    """Партии current_quantity=0 не попадают в orgwide-прогон."""
    batch = _make_raw_batch(
        org=org, module=m_feed, nomenclature=wheat,
        supplier=supplier, warehouse=wh1, unit=unit_kg,
        received_on=date(2026, 4, 20),
    )
    batch.current_quantity = Decimal("0")
    batch.save(update_fields=["current_quantity"])

    FeedShrinkageProfile.objects.create(
        organization=org,
        target_type=FeedShrinkageProfile.TargetType.INGREDIENT,
        nomenclature=wheat,
        period_days=7,
        percent_per_period=Decimal("0.8"),
    )

    results = apply_for_organization(org, today=date(2026, 5, 1))
    depleted = [r for r in results if r.lot_id == str(batch.id)]
    assert depleted == []
