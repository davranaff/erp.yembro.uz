"""
Сервис `execute_production_task` — исполнение задания на замес.

Что делает в atomic-транзакции:
    1. Guard: status=PLANNED, actual_quantity_kg не задан, components.
    2. Для каждого ProductionTaskComponent:
         - Проверить что source_batch задан и current_quantity >= planned_quantity.
         - Декремент RawMaterialBatch.current_quantity.
         - Создать StockMovement OUTGOING из склада сырья.
         - Накопить суммарную стоимость (sum of component.source_batch.price * qty).
    3. Создать FeedBatch:
         - quantity_kg = task.planned_quantity_kg (или actual если задан)
         - unit_cost_uzs = total_cost / quantity_kg
         - total_cost_uzs = sum
         - is_medicated = task.is_medicated
         - withdrawal_period_days = task.withdrawal_period_days
         - withdrawal_period_ends = produced_at + withdrawal_period_days (если is_medicated)
         - status = QUALITY_CHECK (awaiting lab)
    4. Создать StockMovement INCOMING в feed-warehouse.
    5. Создать JournalEntry: Dr 10.05 (Корма, готовая партия) / Cr 10.01 (Сырьё, списание)
       amount = total_cost_uzs.
    6. Обновить task:
         - status = DONE
         - actual_quantity_kg = produced kg (если не задано — planned)
         - actual_price_per_unit_uzs заполнить на каждом component
         - completed_at = now()

Если в actual_quantity_kg указан вес, отличный от planned, то сумма по
компонентам пропорционируется. В MVP считаем что actual == planned.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import FeedBatch, ProductionTask, ProductionTaskComponent, RawMaterialBatch


# GL-политика для Feed:
#   Dr 10.05 «Корма» (приход готовой партии)
#   Cr 10.01 «Сырьё»  (списание компонентов)
READY_FEED_SUBACCOUNT = "10.05"
RAW_MATERIAL_SUBACCOUNT = "10.01"


class FeedTaskExecuteError(ValidationError):
    pass


@dataclass
class FeedTaskExecuteResult:
    task: ProductionTask
    feed_batch: FeedBatch
    stock_movements: list[StockMovement]
    journal_entry: JournalEntry


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise FeedTaskExecuteError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def execute_production_task(
    task: ProductionTask,
    *,
    output_warehouse,
    storage_bin,
    actual_quantity_kg: Optional[Decimal] = None,
    user=None,
) -> FeedTaskExecuteResult:
    """
    Провести задание на замес → получить партию готового корма.

    Args:
        task: ProductionTask в статусе PLANNED/RUNNING.
        output_warehouse: Warehouse (kind=warehouse) куда оприходуется готовый корм.
        storage_bin: ProductionBlock (kind=storage_bin) — бункер на складе.
        actual_quantity_kg: фактический выпуск (default = planned).
        user: User для created_by.

    Returns:
        FeedTaskExecuteResult.

    Raises:
        FeedTaskExecuteError: guard-проверки, нехватка сырья, cross-org.
    """
    # 1. Row-lock
    task = ProductionTask.objects.select_for_update().get(pk=task.pk)
    task = ProductionTask.objects.select_related(
        "organization", "module", "recipe_version", "recipe_version__recipe",
        "production_line", "technologist",
    ).get(pk=task.pk)

    # 2. Guards
    if task.status in (ProductionTask.Status.DONE, ProductionTask.Status.CANCELLED):
        raise FeedTaskExecuteError(
            {"status": f"Задание уже в статусе {task.get_status_display()}."}
        )

    components = list(task.components.select_related("nomenclature", "source_batch"))
    if not components:
        # Fallback: пытаемся скопировать компоненты из версии прямо сейчас
        # (бэкфилл-сценарий — для заданий, созданных до того как
        # perform_create начал делать auto-copy).
        from .copy_components import copy_components_from_version
        copy_components_from_version(task)
        components = list(task.components.select_related("nomenclature", "source_batch"))

    if not components:
        # Если и после fallback пусто — у версии действительно нет компонентов.
        raise FeedTaskExecuteError(
            {"components": (
                "В задании нет компонентов — у выбранной версии рецепта тоже нет "
                "компонентов. Откройте версию в drawer'е рецепта, добавьте компоненты "
                "(сырьё с долями) и попробуйте провести замес снова."
            )}
        )

    org = task.organization

    # Нормализация actual
    actual_qty = actual_quantity_kg or task.actual_quantity_kg or task.planned_quantity_kg

    # 3. Проверки источников и сборка данных
    total_cost = Decimal("0")
    for comp in components:
        if not comp.source_batch_id:
            raise FeedTaskExecuteError(
                {
                    "components": (
                        f"Для компонента «{comp.nomenclature.sku} · "
                        f"{comp.nomenclature.name}» не назначена партия сырья. "
                        f"Это значит что на складе нет доступной (вне карантина) "
                        f"партии этой номенклатуры. Оприходуйте сырьё в табе "
                        f"«Сырьё» и снимите карантин, затем создайте задание заново."
                    )
                }
            )
        batch = comp.source_batch
        if batch.status != RawMaterialBatch.Status.AVAILABLE:
            raise FeedTaskExecuteError(
                {
                    "components": (
                        f"Партия сырья {batch.doc_number} в статусе "
                        f"{batch.get_status_display()} — недоступна для списания."
                    )
                }
            )
        required = comp.planned_quantity
        if batch.current_quantity < required:
            raise FeedTaskExecuteError(
                {
                    "components": (
                        f"Партия сырья {batch.doc_number}: остаток "
                        f"{batch.current_quantity} < требуется {required}."
                    )
                }
            )
        component_cost = _quantize_money(required * batch.price_per_unit_uzs)
        total_cost += component_cost

    total_cost = _quantize_money(total_cost)
    if actual_qty == 0:
        raise FeedTaskExecuteError(
            {"actual_quantity_kg": "Фактический выпуск не может быть нулевым."}
        )
    unit_cost = (total_cost / actual_qty).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    # 4. Cross-org / module checks для output_warehouse / storage_bin
    if output_warehouse.organization_id != org.id:
        raise FeedTaskExecuteError(
            {"output_warehouse": "Склад из другой организации."}
        )
    if output_warehouse.module_id != task.module_id:
        raise FeedTaskExecuteError(
            {"output_warehouse": "Склад не принадлежит модулю задания."}
        )
    if storage_bin.organization_id != org.id:
        raise FeedTaskExecuteError(
            {"storage_bin": "Бункер из другой организации."}
        )
    if storage_bin.module_id != task.module_id:
        raise FeedTaskExecuteError(
            {"storage_bin": "Бункер не принадлежит модулю задания."}
        )

    now = timezone.now()
    # Используем local-TZ дату (settings.TIME_ZONE = Asia/Tashkent)
    entry_date = timezone.localdate(now)

    # 5. Декремент сырья + OUTGOING movements
    stock_movements: list[StockMovement] = []
    for comp in components:
        batch = comp.source_batch
        RawMaterialBatch.objects.filter(pk=batch.pk).update(
            current_quantity=F("current_quantity") - comp.planned_quantity
        )
        # Обновим comp.actual_quantity и actual_price (MVP: actual == planned)
        comp.actual_quantity = comp.planned_quantity
        comp.actual_price_per_unit_uzs = batch.price_per_unit_uzs
        comp.save(
            update_fields=[
                "actual_quantity",
                "actual_price_per_unit_uzs",
                "updated_at",
            ]
        )

        sm_number = next_doc_number(
            StockMovement, organization=org, prefix="СД", on_date=entry_date
        )
        amount = _quantize_money(comp.planned_quantity * batch.price_per_unit_uzs)
        sm = StockMovement(
            organization=org,
            module=task.module,
            doc_number=sm_number,
            kind=StockMovement.Kind.OUTGOING,
            date=now,
            nomenclature=comp.nomenclature,
            quantity=comp.planned_quantity,
            unit_price_uzs=batch.price_per_unit_uzs,
            amount_uzs=amount,
            warehouse_from=batch.warehouse,
            warehouse_to=None,
            source_content_type=ContentType.objects.get_for_model(ProductionTask),
            source_object_id=task.id,
            created_by=user,
        )
        sm.full_clean(exclude=None)
        sm.save()
        stock_movements.append(sm)

    # 6. FeedBatch (готовый комбикорм)
    recipe = task.recipe_version.recipe
    fb_number = (
        f"К-{recipe.code}-" + next_doc_number(
            FeedBatch, organization=org, prefix="ФБ", on_date=entry_date, width=5
        ).split("-")[-1]
    )
    withdrawal_period_ends = None
    if task.is_medicated and task.withdrawal_period_days:
        from datetime import timedelta

        withdrawal_period_ends = entry_date + timedelta(days=task.withdrawal_period_days)

    feed_batch = FeedBatch(
        organization=org,
        module=task.module,
        doc_number=fb_number,
        produced_by_task=task,
        recipe_version=task.recipe_version,
        produced_at=now,
        quantity_kg=actual_qty,
        current_quantity_kg=actual_qty,
        unit_cost_uzs=unit_cost,
        total_cost_uzs=total_cost,
        storage_bin=storage_bin,
        storage_warehouse=output_warehouse,
        status=FeedBatch.Status.QUALITY_CHECK,
        is_medicated=task.is_medicated,
        withdrawal_period_days=task.withdrawal_period_days,
        withdrawal_period_ends=withdrawal_period_ends,
        quality_passport_status=FeedBatch.PassportStatus.PENDING,
    )
    feed_batch.full_clean(exclude=None)
    feed_batch.save()

    # 7. StockMovement INCOMING (готовый корм)
    sm_in_number = next_doc_number(
        StockMovement, organization=org, prefix="СД", on_date=entry_date
    )
    # Готовый корм — это nomenclature рецепта.
    # У ProductionTask нет FK на nomenclature-продукт; возьмём из первого
    # имеющегося на бункере или используем specialty: так как в фазе
    # моделей ProductionTask не хранит output_nomenclature, MVP не
    # создаёт incoming movement с корректной номенклатурой готового корма.
    # Решение: добавим incoming movement на номенклатуру "готового корма"
    # если она есть в nomenclature (Recipe.code). В текущей схеме
    # nomenclature готового корма создаётся при CRUD. Для MVP вернёмся
    # к использованию nomenclature первой позиции компонентов? — нет,
    # это неверно. Оставим без incoming SM если nomenclature не найдена.
    from apps.nomenclature.models import NomenclatureItem
    feed_nom = NomenclatureItem.objects.filter(
        organization=org, sku=recipe.code
    ).first()
    sm_in = None
    if feed_nom:
        sm_in = StockMovement(
            organization=org,
            module=task.module,
            doc_number=sm_in_number,
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=feed_nom,
            quantity=actual_qty,
            unit_price_uzs=unit_cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            amount_uzs=total_cost,
            warehouse_to=output_warehouse,
            warehouse_from=None,
            source_content_type=ContentType.objects.get_for_model(FeedBatch),
            source_object_id=feed_batch.id,
            created_by=user,
        )
        sm_in.full_clean(exclude=None)
        sm_in.save()
        stock_movements.append(sm_in)

    # 8. JournalEntry: Dr 10.05 / Cr 10.01
    debit_sub = _get_subaccount(org, READY_FEED_SUBACCOUNT)
    credit_sub = _get_subaccount(org, RAW_MATERIAL_SUBACCOUNT)
    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=entry_date
    )
    je = JournalEntry(
        organization=org,
        module=task.module,
        doc_number=je_number,
        entry_date=entry_date,
        description=(
            f"Выпуск партии комбикорма {feed_batch.doc_number} · "
            f"задание {task.doc_number} · {actual_qty} кг"
        ),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=total_cost,
        source_content_type=ContentType.objects.get_for_model(ProductionTask),
        source_object_id=task.id,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # 9. Финализация задания
    task.status = ProductionTask.Status.DONE
    task.actual_quantity_kg = actual_qty
    if not task.started_at:
        task.started_at = now
    task.completed_at = now
    task.save(
        update_fields=[
            "status",
            "actual_quantity_kg",
            "started_at",
            "completed_at",
            "updated_at",
        ]
    )

    audit_log(
        organization=task.organization,
        module=task.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=task,
        action_verb=f"executed production task {task.doc_number} → {feed_batch.doc_number}",
    )

    return FeedTaskExecuteResult(
        task=task,
        feed_batch=feed_batch,
        stock_movements=stock_movements,
        journal_entry=je,
    )
