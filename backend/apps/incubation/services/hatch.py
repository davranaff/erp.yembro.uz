"""
Сервис `hatch_incubation_run` — вывод молодняка из инкубационной партии.

Atomic-транзакция:
    1. Guards:
       - run.status = INCUBATING или HATCHING (но не TRANSFERRED/CANCELLED).
       - hatched_count >= 0 и hatched_count <= eggs_loaded.
       - discarded_count >= 0.
       - actual_hatch_date задано.
    2. Создать child Batch (суточный молодняк):
       - parent_batch = run.batch (egg-batch)
       - nomenclature = chick_nomenclature (параметр сервиса)
       - origin_module = incubation
       - current_module = incubation (пока не передали дальше)
       - current_block = hatcher_block run-а (или incubator_block)
       - quantity = hatched_count
       - accumulated_cost_uzs = run.batch.accumulated_cost_uzs
         (вся себестоимость яиц переходит на цыплят).
    3. Закрыть egg-batch:
       - egg_batch.current_quantity = 0
       - egg_batch.state = COMPLETED
       - egg_batch.completed_at = actual_hatch_date
    4. Создать BatchChainStep для chick batch (sequence=1, module=incubation).
    5. Обновить run:
       - status = TRANSFERRED
       - connection to child chick batch (оставим FK в модели, если есть)

Инкубация не делает отдельных StockMovement/JournalEntry в этой версии —
всё накопление себестоимости уже учтено при transfer-е (accept_transfer
Phase B1 создал JE Dr 20.03 / Cr 79.01 при приёме партии). MVP.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounting.models import JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchChainStep
from apps.common.services.numbering import next_doc_number
from apps.nomenclature.models import NomenclatureItem
from apps.warehouses.models import ProductionBlock

from ..models import IncubationRun
from .writeoff import create_writeoff_je


class IncubationHatchError(ValidationError):
    pass


@dataclass
class IncubationHatchResult:
    run: IncubationRun
    chick_batch: Batch
    egg_batch: Batch  # закрыт
    chain_step: BatchChainStep
    writeoff_je: "JournalEntry | None" = None
    writeoff_amount_uzs: Decimal = Decimal("0")


@transaction.atomic
def hatch_incubation_run(
    run: IncubationRun,
    *,
    chick_nomenclature: NomenclatureItem,
    chick_unit=None,
    hatched_count: Optional[int] = None,
    discarded_count: Optional[int] = None,
    actual_hatch_date: Optional[date_type] = None,
    user=None,
) -> IncubationHatchResult:
    """
    Вывести молодняк из инкубационной партии.

    Args:
        run: IncubationRun в статусе INCUBATING/HATCHING.
        chick_nomenclature: номенклатура «Цыплёнок суточный».
        chick_unit: единица измерения для chick batch (default = chick_nomenclature.unit).
        hatched_count: если None — берём из run.hatched_count.
        discarded_count: аналогично.
        actual_hatch_date: если None — берём из run.actual_hatch_date.
    """
    run = IncubationRun.objects.select_for_update().get(pk=run.pk)
    run = IncubationRun.objects.select_related(
        "organization", "module", "incubator_block", "hatcher_block", "batch",
        "batch__current_module", "batch__current_block",
    ).get(pk=run.pk)

    if run.status in (
        IncubationRun.Status.TRANSFERRED,
        IncubationRun.Status.CANCELLED,
    ):
        raise IncubationHatchError(
            {"status": f"Нельзя выводить: статус {run.get_status_display()}."}
        )

    # Накладываем переданные значения
    if hatched_count is not None:
        run.hatched_count = hatched_count
    if discarded_count is not None:
        run.discarded_count = discarded_count
    if actual_hatch_date is not None:
        run.actual_hatch_date = actual_hatch_date

    if run.actual_hatch_date is None:
        raise IncubationHatchError(
            {"actual_hatch_date": "Укажите дату фактического вывода."}
        )
    if run.hatched_count is None or run.hatched_count < 0:
        raise IncubationHatchError(
            {"hatched_count": "Количество выведенных должно быть >= 0."}
        )
    if run.hatched_count > run.eggs_loaded:
        raise IncubationHatchError(
            {"hatched_count": "Выведенных не может быть больше загруженных."}
        )

    org = run.organization
    egg_batch = run.batch

    if chick_nomenclature.organization_id != org.id:
        raise IncubationHatchError(
            {"chick_nomenclature": "Номенклатура из другой организации."}
        )

    chick_unit = chick_unit or chick_nomenclature.unit

    # Списать отход (всё что не выведется): (eggs_loaded - hatched).
    # Это объединяет discarded_count + эмбриональную смертность (fertile - hatched).
    # Писать в 91.02 стоимость только тех яиц, которые НЕ станут цыплятами.
    lost_eggs = max(0, run.eggs_loaded - run.hatched_count)
    writeoff = create_writeoff_je(
        run=run,
        egg_batch=egg_batch,
        eggs_to_writeoff=lost_eggs,
        on_date=run.actual_hatch_date,
        description_prefix=f"Отход инкубации {run.doc_number}",
        user=user,
    )
    # egg_batch.accumulated_cost_uzs был уменьшён в writeoff на writeoff.amount_uzs.
    # Перечитаем, чтобы chick_batch взял корректное значение:
    egg_batch.refresh_from_db(fields=["accumulated_cost_uzs"])

    # Создать chick batch
    doc = next_doc_number(
        Batch, organization=org, prefix="П", on_date=run.actual_hatch_date,
        width=5,
    )

    block = run.hatcher_block or run.incubator_block

    chick_batch = Batch.objects.create(
        organization=org,
        doc_number=doc,
        nomenclature=chick_nomenclature,
        unit=chick_unit,
        origin_module=run.module,
        current_module=run.module,
        current_block=block,
        parent_batch=egg_batch,
        current_quantity=Decimal(run.hatched_count),
        initial_quantity=Decimal(run.hatched_count),
        accumulated_cost_uzs=egg_batch.accumulated_cost_uzs,
        started_at=run.actual_hatch_date,
        created_by=user,
    )

    # Chain step
    from django.utils import timezone

    step = BatchChainStep.objects.create(
        batch=chick_batch,
        sequence=1,
        module=run.module,
        block=block,
        entered_at=timezone.now(),
        quantity_in=Decimal(run.hatched_count),
    )

    # Закрыть egg batch
    egg_batch.current_quantity = Decimal("0")
    egg_batch.state = Batch.State.COMPLETED
    egg_batch.completed_at = run.actual_hatch_date
    egg_batch.save(
        update_fields=["current_quantity", "state", "completed_at", "updated_at"]
    )

    # Обновить run
    run.status = IncubationRun.Status.TRANSFERRED
    run.save(
        update_fields=[
            "status",
            "hatched_count",
            "discarded_count",
            "actual_hatch_date",
            "updated_at",
        ]
    )

    audit_log(
        organization=run.organization,
        module=run.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=run,
        action_verb=f"hatched {run.doc_number} → {chick_batch.doc_number} ({run.hatched_count} гол)",
    )

    return IncubationHatchResult(
        run=run,
        chick_batch=chick_batch,
        egg_batch=egg_batch,
        chain_step=step,
        writeoff_je=writeoff.journal_entry,
        writeoff_amount_uzs=writeoff.amount_uzs,
    )
