"""
Сторно проведённого ProductionTask (DONE-замеса).

Раньше `cancel_production_task` отказывался работать с DONE/RUNNING — не
было способа откатить уже выпущенный замес. Если оператор обнаружил, что
выпуск был с ошибкой (не та партия сырья, перепутанный рецепт, неверный
вес), стоковые движения и JE оставались висеть.

Этот сервис создаёт компенсирующие записи:
    1. По каждому StockMovement (kind=OUTGOING, source=task) — INCOMING
       зеркало на тот же warehouse_from с теми же qty/price. Партия
       сырья (RawMaterialBatch) восстанавливается на исходное количество.
    2. По единственному StockMovement (kind=INCOMING готового корма) —
       OUTGOING зеркало с того же warehouse_to.
    3. По JournalEntry для этого task — сторно с swap Dr↔Cr.
    4. FeedBatch → status=REJECTED, current_quantity_kg = 0.
    5. ProductionTask → status=CANCELLED.

Guards (важны):
    - task.status должен быть DONE
    - FeedBatch не должен иметь дочерних FeedBagLot (если упаковка
      состоялась, нельзя просто откатить — нужно вначале distribute
      bags обратно или через отдельный процесс)
    - FeedBatch.current_quantity_kg должен равняться quantity_kg
      (никакая часть ещё не списана в продажу / другие задачи)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.diff import compute_diff, snapshot_model
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import FeedBatch, ProductionTask, ProductionTaskComponent, RawMaterialBatch


class FeedTaskReverseError(ValidationError):
    pass


@dataclass
class FeedTaskReverseResult:
    task: ProductionTask
    reverse_movements: list = field(default_factory=list)
    reverse_journals: list = field(default_factory=list)
    feed_batch: FeedBatch | None = None


def _restore_raw_quantities(task: ProductionTask) -> None:
    """Вернуть actual_quantity на каждую исходную RawMaterialBatch."""
    components = ProductionTaskComponent.objects.filter(task=task).select_related(
        "source_batch"
    )
    # Блокируем партии в детерминистическом порядке — как и в execute_task.
    batch_ids = sorted({c.source_batch_id for c in components if c.source_batch_id})
    if batch_ids:
        # Захватываем row-locks, чтобы не было гонок с другим execute_task.
        list(
            RawMaterialBatch.objects
            .select_for_update()
            .filter(id__in=batch_ids)
            .order_by("id")
        )
    for comp in components:
        if not comp.source_batch_id or not comp.actual_quantity:
            continue
        RawMaterialBatch.objects.filter(pk=comp.source_batch_id).update(
            current_quantity=F("current_quantity") + comp.actual_quantity,
        )
        # Если партия была DEPLETED — возвращаем в AVAILABLE.
        # Обновляем через .objects.get/save, потому что меняем статус
        # на основе уже инкрементированного остатка.
        batch = RawMaterialBatch.objects.get(pk=comp.source_batch_id)
        if (
            batch.status == RawMaterialBatch.Status.DEPLETED
            and batch.current_quantity > 0
        ):
            batch.status = RawMaterialBatch.Status.AVAILABLE
            batch.save(update_fields=["status", "updated_at"])


@transaction.atomic
def reverse_production_task(
    task: ProductionTask, *, reason: str = "", user=None,
) -> FeedTaskReverseResult:
    """
    Сторно DONE-задания: компенсирующие SM + сторно JE + восстановление
    партий сырья + REJECT готовой партии корма + status=CANCELLED.

    Raises:
        FeedTaskReverseError — если задание не в DONE, или готовая
            партия уже частично потрачена / упакована.
    """
    task = ProductionTask.objects.select_for_update().get(pk=task.pk)
    task = ProductionTask.objects.select_related(
        "organization", "module"
    ).get(pk=task.pk)

    if task.status != ProductionTask.Status.DONE:
        raise FeedTaskReverseError({
            "status": (
                f"Сторно возможно только для DONE-замеса, текущий: "
                f"{task.get_status_display()}."
            ),
        })

    before_snapshot = snapshot_model(task)

    feed_batch = FeedBatch.objects.filter(produced_by_task=task).first()
    if feed_batch is None:
        raise FeedTaskReverseError({
            "__all__": (
                "У задания нет привязанной партии готового корма (FeedBatch). "
                "Возможно execute_task упал не до конца — обратитесь к разработке."
            ),
        })

    # Защита от частичного потребления: если current_quantity_kg уже
    # отличается от quantity_kg, кто-то успел упаковать в мешки или
    # списать на feed_consumption. Сторно станет некорректным.
    if feed_batch.current_quantity_kg != feed_batch.quantity_kg:
        raise FeedTaskReverseError({
            "__all__": (
                f"Часть выпущенной партии {feed_batch.doc_number} уже "
                f"израсходована "
                f"({feed_batch.quantity_kg - feed_batch.current_quantity_kg} "
                f"кг из {feed_batch.quantity_kg}). Сначала сторнируйте "
                f"расход (упаковку, кормление), потом возвращайтесь к замесу."
            ),
        })

    # Также блокируем FeedBagLot — если есть лоты упаковки, тоже нельзя.
    bag_lots_count = feed_batch.feedbaglot_set.count() if hasattr(
        feed_batch, "feedbaglot_set"
    ) else 0
    if bag_lots_count > 0:
        raise FeedTaskReverseError({
            "__all__": (
                f"Партия {feed_batch.doc_number} уже расфасована в мешки "
                f"({bag_lots_count} лот(ов)). Откат замеса заблокирован."
            ),
        })

    org = task.organization
    task_ct = ContentType.objects.get_for_model(ProductionTask)
    fb_ct = ContentType.objects.get_for_model(FeedBatch)

    # 1. Реверс всех StockMovement цепочки замеса.
    # OUTGOING сырья — привязаны source=ProductionTask (task_ct).
    # INCOMING готового корма — привязан source=FeedBatch (fb_ct), не task,
    # потому что execute_task создаёт его после создания FeedBatch.
    # Собираем оба набора в одной transaction-блокировке.
    from django.db.models import Q
    source_movements = list(
        StockMovement.objects.select_for_update().filter(
            Q(source_content_type=task_ct, source_object_id=task.id)
            | Q(source_content_type=fb_ct, source_object_id=feed_batch.id)
        ).order_by("date", "id")
    )
    if not source_movements:
        raise FeedTaskReverseError({
            "__all__": (
                "Не найдены складские движения исходного замеса — нечего "
                "сторнировать. Возможно reverse_production_task уже был "
                "вызван ранее."
            ),
        })

    reverse_movements = []
    for sm in source_movements:
        Kind = StockMovement.Kind
        # Зеркало: OUTGOING становится INCOMING (товар возвращается),
        # INCOMING становится OUTGOING (отзываем приход готового корма).
        if sm.kind == Kind.OUTGOING:
            rev_kind = Kind.INCOMING
            rev_wh_from, rev_wh_to = None, sm.warehouse_from
        elif sm.kind == Kind.INCOMING:
            rev_kind = Kind.OUTGOING
            rev_wh_from, rev_wh_to = sm.warehouse_to, None
        else:
            # transfer / write_off / shrinkage в feed.execute_task не
            # создаются, но на всякий случай оставляем явный отказ.
            raise FeedTaskReverseError({
                "__all__": (
                    f"Неожиданный kind={sm.kind} у движения {sm.doc_number} — "
                    f"сторно не предусмотрено."
                ),
            })

        rev_number = next_doc_number(
            StockMovement, organization=org, prefix="СД", on_date=sm.date,
        )
        rev = StockMovement(
            organization=org,
            module=sm.module,
            doc_number=rev_number,
            kind=rev_kind,
            date=sm.date,
            nomenclature=sm.nomenclature,
            quantity=sm.quantity,
            unit_price_uzs=sm.unit_price_uzs,
            amount_uzs=sm.amount_uzs,
            warehouse_from=rev_wh_from,
            warehouse_to=rev_wh_to,
            counterparty=sm.counterparty,
            batch=sm.batch,
            source_content_type=task_ct,
            source_object_id=task.id,
            created_by=user,
        )
        rev.full_clean(exclude=None)
        rev.save()
        reverse_movements.append(rev)

    # 2. Восстановление quantity на партиях сырья.
    _restore_raw_quantities(task)

    # 3. Сторно JE (Dr ↔ Cr swap).
    source_journals = list(
        JournalEntry.objects.filter(
            source_content_type=task_ct, source_object_id=task.id,
        ).order_by("entry_date", "id")
    )
    reverse_journals = []
    for je in source_journals:
        rev_number = next_doc_number(
            JournalEntry, organization=org, prefix="ПР", on_date=je.entry_date,
        )
        rev_je = JournalEntry(
            organization=org,
            module=je.module,
            doc_number=rev_number,
            entry_date=je.entry_date,
            description=f"Сторно замеса {task.doc_number}: {reason}"[:255],
            debit_subaccount=je.credit_subaccount,
            credit_subaccount=je.debit_subaccount,
            amount_uzs=Decimal(je.amount_uzs),
            currency=je.currency,
            amount_foreign=je.amount_foreign,
            exchange_rate=je.exchange_rate,
            source_content_type=task_ct,
            source_object_id=task.id,
            counterparty=je.counterparty,
            batch=je.batch,
            created_by=user,
        )
        rev_je.full_clean(exclude=None)
        rev_je.save()
        reverse_journals.append(rev_je)

    # 4. FeedBatch → REJECTED, остаток обнуляем.
    feed_batch.status = FeedBatch.Status.REJECTED
    feed_batch.current_quantity_kg = Decimal("0")
    feed_batch.save(update_fields=[
        "status", "current_quantity_kg", "updated_at",
    ])

    # 5. ProductionTask → CANCELLED.
    if reason:
        task.notes = (
            (task.notes + f"\nСторно DONE: {reason}").strip()
            if getattr(task, "notes", "")
            else f"Сторно DONE: {reason}"
        )
    task.status = ProductionTask.Status.CANCELLED
    fields = ["status", "updated_at"]
    if hasattr(task, "notes"):
        fields.append("notes")
    task.save(update_fields=fields)

    audit_log(
        organization=org,
        module=task.module,
        actor=user,
        action=AuditLog.Action.UNPOST,
        entity=task,
        action_verb=f"reversed DONE production task {task.doc_number} ({reason})",
        diff=compute_diff(before_snapshot, snapshot_model(task)),
    )

    return FeedTaskReverseResult(
        task=task,
        reverse_movements=reverse_movements,
        reverse_journals=reverse_journals,
        feed_batch=feed_batch,
    )
