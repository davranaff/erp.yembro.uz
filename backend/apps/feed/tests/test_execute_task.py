"""
Тесты execute_production_task.

Ключевые инварианты:
    1. Сырьё списывается с RawMaterialBatch.current_quantity.
    2. FeedBatch создан с корректной себестоимостью (взвешенная).
    3. is_medicated → withdrawal_period_ends рассчитан.
    4. JournalEntry: Dr 10.05 / Cr 10.01 на полную себестоимость.
    5. Повторный execute на DONE → ValidationError.
    6. Нехватка сырья → ValidationError.
    7. Сырьё на карантине → ValidationError.
    8. Атомарность.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedBatch,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeVersion,
)
from apps.feed.services.execute_task import (
    FeedTaskExecuteError,
    execute_production_task,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="tech@y.local", full_name="Tech")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_raw(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.01")
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def corn(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-01", name="Кукуруза",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def soy(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-СШР-01", name="Соевый шрот",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-S-01", kind="supplier", name="Агроимпорт"
    )


@pytest.fixture
def mixer_line(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СМ-1",
        name="Смеситель 1", kind=ProductionBlock.Kind.MIXER_LINE,
    )


@pytest.fixture
def storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БН-3",
        name="Бункер 3", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def raw_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-СР", name="Склад сырья",
    )


@pytest.fixture
def ready_warehouse(org, m_feed, storage_bin):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-ГК", name="Склад готового корма",
        production_block=storage_bin,
    )


@pytest.fixture
def corn_batch(org, m_feed, corn, supplier, raw_warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-417",
        nomenclature=corn, supplier=supplier, warehouse=raw_warehouse,
        received_date=date(2026, 4, 1),
        quantity=Decimal("5000"), current_quantity=Decimal("5000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


@pytest.fixture
def soy_batch(org, m_feed, soy, supplier, raw_warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-С-203",
        nomenclature=soy, supplier=supplier, warehouse=raw_warehouse,
        received_date=date(2026, 4, 1),
        quantity=Decimal("2000"), current_quantity=Decimal("2000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("27000.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="Р-БР-СТ",
        name="Старт бройлера", direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def broiler_feed_nom(org, cat_raw, unit_kg, recipe):
    """Nomenclature для готового корма — sku == recipe.code."""
    return NomenclatureItem.objects.create(
        organization=org, sku="Р-БР-СТ", name="Старт бройлера — корм",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def task(org, m_feed, recipe_version, mixer_line, user, corn_batch, soy_batch, corn, soy):
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-TEST-001",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=user, is_medicated=False, withdrawal_period_days=0,
    )
    # 2 компонента: 700 кг кукурузы + 300 кг сои
    ProductionTaskComponent.objects.create(
        task=t, nomenclature=corn, source_batch=corn_batch,
        planned_quantity=Decimal("700"),
        planned_price_per_unit_uzs=Decimal("18000"),
        sort_order=1,
    )
    ProductionTaskComponent.objects.create(
        task=t, nomenclature=soy, source_batch=soy_batch,
        planned_quantity=Decimal("300"),
        planned_price_per_unit_uzs=Decimal("27000"),
        sort_order=2,
    )
    return t


# ─── Basic flow ──────────────────────────────────────────────────────────


def test_execute_decrements_raw_batches(
    task, corn_batch, soy_batch, ready_warehouse, storage_bin, broiler_feed_nom,
):
    result = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )

    corn_batch.refresh_from_db()
    soy_batch.refresh_from_db()
    # 5000 - 700 = 4300, 2000 - 300 = 1700
    assert corn_batch.current_quantity == Decimal("4300.000")
    assert soy_batch.current_quantity == Decimal("1700.000")


def test_execute_creates_feed_batch_with_correct_cost(
    task, ready_warehouse, storage_bin, broiler_feed_nom,
):
    result = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    # 700*18000 + 300*27000 = 12_600_000 + 8_100_000 = 20_700_000
    fb = result.feed_batch
    assert fb.total_cost_uzs == Decimal("20700000.00")
    # unit_cost = 20_700_000 / 1000 = 20_700.00
    assert fb.unit_cost_uzs == Decimal("20700.000000")
    assert fb.quantity_kg == Decimal("1000")
    assert fb.status == FeedBatch.Status.QUALITY_CHECK
    assert fb.quality_passport_status == FeedBatch.PassportStatus.PENDING


def test_execute_creates_journal_entry_10_05_to_10_01(
    task, ready_warehouse, storage_bin, broiler_feed_nom,
):
    result = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    je = result.journal_entry
    assert je.debit_subaccount.code == "10.05"
    assert je.credit_subaccount.code == "10.01"
    assert je.amount_uzs == Decimal("20700000.00")


def test_execute_marks_task_done(
    task, ready_warehouse, storage_bin, broiler_feed_nom,
):
    result = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    task.refresh_from_db()
    assert task.status == ProductionTask.Status.DONE
    assert task.actual_quantity_kg == Decimal("1000")
    assert task.completed_at is not None


# ─── Medicated flow ──────────────────────────────────────────────────────


def test_execute_medicated_sets_withdrawal_period(
    org, m_feed, recipe_version, mixer_line, user, corn_batch, soy_batch, corn, soy,
    ready_warehouse, storage_bin, broiler_feed_nom,
):
    task = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-MED-001",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=user, is_medicated=True, withdrawal_period_days=5,
    )
    ProductionTaskComponent.objects.create(
        task=task, nomenclature=corn, source_batch=corn_batch,
        planned_quantity=Decimal("700"),
        planned_price_per_unit_uzs=Decimal("18000"),
    )
    ProductionTaskComponent.objects.create(
        task=task, nomenclature=soy, source_batch=soy_batch,
        planned_quantity=Decimal("300"),
        planned_price_per_unit_uzs=Decimal("27000"),
    )

    result = execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    fb = result.feed_batch
    assert fb.is_medicated is True
    assert fb.withdrawal_period_days == 5
    # withdrawal_period_ends = produced_at (local TZ) + 5 days
    from django.utils import timezone as djtz
    expected = djtz.localdate(fb.produced_at) + timedelta(days=5)
    assert fb.withdrawal_period_ends == expected


# ─── Guards ──────────────────────────────────────────────────────────────


def test_execute_twice_raises(
    task, ready_warehouse, storage_bin, broiler_feed_nom,
):
    execute_production_task(
        task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    with pytest.raises(ValidationError):
        execute_production_task(
            task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
        )


def test_execute_insufficient_raw_raises(
    org, m_feed, recipe_version, mixer_line, user, corn, supplier,
    raw_warehouse, unit_kg, ready_warehouse, storage_bin,
):
    # Лот на 100 кг, а нужно 700
    small_batch = RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-SMALL",
        nomenclature=corn, supplier=supplier, warehouse=raw_warehouse,
        received_date=date.today(),
        quantity=Decimal("100"), current_quantity=Decimal("100"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-SMALL",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day", scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("700"),
        status=ProductionTask.Status.PLANNED,
        technologist=user,
    )
    ProductionTaskComponent.objects.create(
        task=t, nomenclature=corn, source_batch=small_batch,
        planned_quantity=Decimal("700"),
        planned_price_per_unit_uzs=Decimal("18000"),
    )
    with pytest.raises(ValidationError):
        execute_production_task(
            t, output_warehouse=ready_warehouse, storage_bin=storage_bin,
        )


def test_execute_raw_in_quarantine_raises(
    org, m_feed, recipe_version, mixer_line, user, corn, supplier,
    raw_warehouse, unit_kg, ready_warehouse, storage_bin,
):
    quarantine_batch = RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-Q",
        nomenclature=corn, supplier=supplier, warehouse=raw_warehouse,
        received_date=date.today(),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000"),
        status=RawMaterialBatch.Status.QUARANTINE,  # ← в карантине
    )
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-Q",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day", scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("500"),
        status=ProductionTask.Status.PLANNED,
        technologist=user,
    )
    ProductionTaskComponent.objects.create(
        task=t, nomenclature=corn, source_batch=quarantine_batch,
        planned_quantity=Decimal("500"),
        planned_price_per_unit_uzs=Decimal("18000"),
    )
    with pytest.raises(ValidationError):
        execute_production_task(
            t, output_warehouse=ready_warehouse, storage_bin=storage_bin,
        )


def test_execute_is_atomic_on_je_failure(
    task, ready_warehouse, storage_bin, broiler_feed_nom,
    corn_batch, monkeypatch,
):
    original_save = JournalEntry.save
    call_count = {"n": 0}

    def broken(self, *a, **kw):
        call_count["n"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(JournalEntry, "save", broken)

    with pytest.raises(RuntimeError):
        execute_production_task(
            task, output_warehouse=ready_warehouse, storage_bin=storage_bin,
        )

    # Откат: task в PLANNED, сырьё не списано
    task.refresh_from_db()
    corn_batch.refresh_from_db()
    assert task.status == ProductionTask.Status.PLANNED
    assert corn_batch.current_quantity == Decimal("5000")
    assert not FeedBatch.objects.filter(produced_by_task=task).exists()
