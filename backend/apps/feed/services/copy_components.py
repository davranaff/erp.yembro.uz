"""
Сервис `copy_components_from_version` — автоматически создаёт
ProductionTaskComponent для каждого RecipeComponent выбранной версии.

Вызывается при создании ProductionTask через UI/API. Логика:
  1. Для каждого RecipeComponent версии:
     - planned_quantity = task.planned_quantity_kg × share_percent / 100
     - source_batch = первая AVAILABLE партия сырья этой номенклатуры
       с достаточным остатком (FIFO по received_date).
     - planned_price_per_unit_uzs = price_per_unit_uzs выбранной партии.
  2. Если для какой-то номенклатуры нет подходящей партии — создаём
     компонент **без** source_batch (technолог потом назначит вручную).
     Это допустимо: задание создаётся, но провести замес можно будет только
     после назначения партий.

Идемпотентен: если у задания уже есть компоненты — возвращает []
(повторно не копирует).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from ..models import (
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    RecipeComponent,
)


def _quantize(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _find_fifo_source_batch(
    *, organization, nomenclature, required_qty: Decimal
) -> RawMaterialBatch | None:
    """
    FIFO выбор партии сырья: первая по received_date с достаточным остатком.
    Если хватит только частично — берём ту, у которой больше остаток.
    Возвращает None если подходящих партий нет.

    Все запросы с select_for_update(of=("self",)). Без этого два
    параллельных copy_components_from_version (двойной submit «Создать
    задание») могли выбрать одну и ту же партию для одинаковых
    ингредиентов. На execute_task мы поймали бы это row-lock'ом, но
    компоненты обоих заданий уже указывали бы на одну партию, что
    мешает планированию и отчётам.
    """
    qs = RawMaterialBatch.objects.select_for_update(of=("self",)).filter(
        organization=organization,
        nomenclature=nomenclature,
        status=RawMaterialBatch.Status.AVAILABLE,
        current_quantity__gt=0,
    )
    # 1. Сначала пытаемся найти партию с достаточным остатком (FIFO)
    enough = qs.filter(current_quantity__gte=required_qty).order_by(
        "received_date", "created_at"
    ).first()
    if enough:
        return enough
    # 2. Иначе — самую старшую с любым остатком (хоть частично спишется)
    return qs.order_by("received_date", "created_at").first()


@transaction.atomic
def copy_components_from_version(task: ProductionTask) -> list[ProductionTaskComponent]:
    """
    Создать ProductionTaskComponent'ы из RecipeComponent'ов выбранной версии.

    Возвращает список созданных компонентов. Если уже были — возвращает [].
    """
    if task.components.exists():
        return []

    if not task.recipe_version_id:
        return []

    planned_total = Decimal(task.planned_quantity_kg)
    org = task.organization

    components_to_create: list[ProductionTaskComponent] = []
    for idx, rc in enumerate(
        RecipeComponent.objects.filter(recipe_version=task.recipe_version)
        .select_related("nomenclature")
        .order_by("sort_order", "id")
    ):
        share = Decimal(rc.share_percent)
        required_qty = _quantize(planned_total * share / Decimal("100"))

        source_batch = _find_fifo_source_batch(
            organization=org,
            nomenclature=rc.nomenclature,
            required_qty=required_qty,
        )
        price = source_batch.price_per_unit_uzs if source_batch else Decimal("0")

        components_to_create.append(
            ProductionTaskComponent(
                task=task,
                nomenclature=rc.nomenclature,
                source_batch=source_batch,
                planned_quantity=required_qty,
                planned_price_per_unit_uzs=price,
                sort_order=idx,
            )
        )

    if components_to_create:
        ProductionTaskComponent.objects.bulk_create(components_to_create)
    return components_to_create


@transaction.atomic
def refresh_unassigned_task_components(
    task: ProductionTask,
) -> list[ProductionTaskComponent]:
    """
    Перешолвить партии сырья для компонентов задания, у которых ещё нет
    привязки (source_batch IS NULL) — на случай если новая партия пришла
    уже после создания задания.

    Работает только для PLANNED-заданий (на executed/finished не трогаем
    данные о фактически использованных партиях).

    Возвращает список обновлённых компонентов.
    """
    if task.status != ProductionTask.Status.PLANNED:
        return []

    org = task.organization
    updated: list[ProductionTaskComponent] = []
    for c in (
        ProductionTaskComponent.objects
        .filter(task=task, source_batch__isnull=True)
        .select_related("nomenclature")
    ):
        batch = _find_fifo_source_batch(
            organization=org,
            nomenclature=c.nomenclature,
            required_qty=Decimal(c.planned_quantity),
        )
        if batch is None:
            continue
        c.source_batch = batch
        c.planned_price_per_unit_uzs = batch.price_per_unit_uzs
        c.save(update_fields=[
            "source_batch", "planned_price_per_unit_uzs", "updated_at",
        ])
        updated.append(c)
    return updated
