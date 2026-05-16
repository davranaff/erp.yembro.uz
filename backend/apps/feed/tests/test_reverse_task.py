"""
Тесты reverse_production_task (сторно DONE-замеса).

Покрывают:
  - happy path: 2-компонентный замес → execute → reverse;
    проверяем зеркальные StockMovement, сторно JE, восстановление
    RawMaterialBatch.current_quantity, REJECT готовой партии,
    переход статуса task → CANCELLED.
  - guard: нельзя сторнировать если task не в DONE.
  - guard: нельзя сторнировать если готовый корм уже частично потрачен
    (current_quantity_kg < quantity_kg).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import JournalEntry
from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedBatch,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeVersion,
)
from apps.feed.services.execute_task import execute_production_task
from apps.feed.services.reverse_task import (
    FeedTaskReverseError,
    reverse_production_task,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# Все fixtures — копия test_execute_task.py для самодостаточности файла.
# Сознательно дублируем: тесты должны быть читаемыми без переключения
# между файлами.


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="rev@y.local", full_name="Reverser")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_raw(org):
    from apps.accounting.models import GLSubaccount
    sub = GLSubaccount.objects.get(account__organization=org, code="10.01")
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def corn(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="R-КУК-01", name="Кукуруза",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def soy(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="R-СШР-01", name="Соевый шрот",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-RS-01", kind="supplier", name="Реверс-Импорт",
    )


@pytest.fixture
def mixer_line(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СМ-R1",
        name="Смеситель R1", kind=ProductionBlock.Kind.MIXER_LINE,
    )


@pytest.fixture
def storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БН-R3",
        name="Бункер R3", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def raw_warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-RR", name="Склад сырья R",
    )


@pytest.fixture
def ready_warehouse(org, m_feed, storage_bin):
    return Warehouse.objects.create(
        organization=org, module=m_feed,
        code="СК-RG", name="Склад готового корма R",
        production_block=storage_bin,
    )


@pytest.fixture
def corn_batch(org, m_feed, corn, supplier, raw_warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="RP-К-417",
        nomenclature=corn, supplier=supplier, warehouse=raw_warehouse,
        received_date=date(2026, 4, 1),
        quantity=Decimal("5000"), current_quantity=Decimal("5000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


@pytest.fixture
def soy_batch(org, m_feed, soy, supplier, raw_warehouse, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="RP-С-203",
        nomenclature=soy, supplier=supplier, warehouse=raw_warehouse,
        received_date=date(2026, 4, 1),
        quantity=Decimal("2000"), current_quantity=Decimal("2000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("27000.00"),
        status=RawMaterialBatch.Status.AVAILABLE,
    )


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="R-Р-БР-СТ",
        name="Старт бройлера R", direction="broiler",
    )


@pytest.fixture
def recipe_version(recipe):
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def feed_nom(org, cat_raw, unit_kg, recipe):
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku=recipe.code,
        defaults={
            "name": "Готовый корм R-Р-БР-СТ",
            "category": cat_raw, "unit": unit_kg,
        },
    )
    return item


@pytest.fixture
def task_done(
    org, m_feed, recipe_version, mixer_line, user,
    corn_batch, soy_batch, corn, soy,
    ready_warehouse, storage_bin, feed_nom,
):
    """Создать задачу и сразу провести execute → DONE."""
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-REV-001",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=user, is_medicated=False, withdrawal_period_days=0,
    )
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
    execute_production_task(
        t, output_warehouse=ready_warehouse, storage_bin=storage_bin,
    )
    t.refresh_from_db()
    return t


def test_reverse_restores_raw_quantities(task_done, corn_batch, soy_batch):
    reverse_production_task(task_done, reason="ошибка веса")
    corn_batch.refresh_from_db()
    soy_batch.refresh_from_db()
    # Изначальное количество восстановилось.
    assert corn_batch.current_quantity == Decimal("5000.000")
    assert soy_batch.current_quantity == Decimal("2000.000")


def test_reverse_creates_mirror_stock_movements(task_done):
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q
    result = reverse_production_task(task_done, reason="ошибка веса")
    # Изначально (источник = task): 2 OUTGOING сырья.
    # Изначально (источник = FeedBatch): 1 INCOMING готового корма.
    # После reverse: 2 INCOMING (возврат сырья, source=task) и 1 OUTGOING
    # (отзыв готового корма, source=task — это reverse_movements не
    # дублирует исходный source feed_batch, потому что обратное движение
    # концептуально принадлежит откату задачи).
    task_ct = ContentType.objects.get_for_model(ProductionTask)
    fb_ct = ContentType.objects.get_for_model(FeedBatch)
    fb = result.feed_batch
    all_sm = StockMovement.objects.filter(
        Q(source_content_type=task_ct, source_object_id=task_done.id)
        | Q(source_content_type=fb_ct, source_object_id=fb.id)
    )
    # 2 (OUTGOING сырья → task) + 1 (INCOMING готового → fb) + 3 mirror.
    assert all_sm.count() == 6
    kinds = [sm.kind for sm in result.reverse_movements]
    assert kinds.count(StockMovement.Kind.INCOMING) == 2
    assert kinds.count(StockMovement.Kind.OUTGOING) == 1


def test_reverse_creates_swap_journal_entry(task_done):
    from django.contrib.contenttypes.models import ContentType
    result = reverse_production_task(task_done, reason="ошибка веса")
    task_ct = ContentType.objects.get_for_model(ProductionTask)
    all_je = JournalEntry.objects.filter(
        source_content_type=task_ct, source_object_id=task_done.id,
    )
    # Исходная JE (Dr 10.05 / Cr 10.01) + зеркальная (Dr 10.01 / Cr 10.05) = 2.
    assert all_je.count() == 2
    rev_je = result.reverse_journals[0]
    assert rev_je.debit_subaccount.code == "10.01"  # swapped
    assert rev_je.credit_subaccount.code == "10.05"
    assert rev_je.amount_uzs == Decimal("20700000.00")


def test_reverse_marks_feed_batch_rejected(task_done):
    result = reverse_production_task(task_done, reason="ошибка веса")
    fb = result.feed_batch
    assert fb.status == FeedBatch.Status.REJECTED
    assert fb.current_quantity_kg == Decimal("0")


def test_reverse_marks_task_cancelled(task_done):
    reverse_production_task(task_done, reason="ошибка веса")
    task_done.refresh_from_db()
    assert task_done.status == ProductionTask.Status.CANCELLED


def test_reverse_rejects_non_done_task(
    org, m_feed, recipe_version, mixer_line, user, corn_batch, soy_batch,
    corn, soy,
):
    t = ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-REV-NOTDONE",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("1000"),
        status=ProductionTask.Status.PLANNED,
        technologist=user,
    )
    with pytest.raises(ValidationError):
        reverse_production_task(t, reason="rejected")


def test_reverse_rejects_partially_consumed_feed(task_done):
    # Симулируем что часть корма списали (продажа, упаковка, кормление).
    fb = FeedBatch.objects.get(produced_by_task=task_done)
    fb.current_quantity_kg = fb.quantity_kg - Decimal("100")
    fb.save(update_fields=["current_quantity_kg"])

    with pytest.raises(ValidationError):
        reverse_production_task(task_done, reason="too late")
