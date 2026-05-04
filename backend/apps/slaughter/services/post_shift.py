"""
Сервис `post_slaughter_shift` — провести смену убоя.

Что делает в atomic-транзакции:
    1. Guards:
       - shift.status = ACTIVE или CLOSED
       - source_batch.withdrawal_period_ends <= shift_date (уже проверено в
         SlaughterShift.clean() Phase-5 guard; повторим для race).
       - shift.yields.exists() — хотя бы одна позиция выхода.
       - sum(yield.quantity * unit_implied_kg) ~= live_weight_kg_total
         (допустимое отклонение — проверяем мягко через share_percent).
    2. Списание живой птицы:
       - StockMovement OUTGOING: birds из feedlot batch (warehouse_from = ?).
       - Декремент Batch.current_quantity → 0 (всё ушло на убой).
       - Batch.state = COMPLETED, completed_at = shift_date.
       - BatchCostEntry не создаётся (себестоимость уже накоплена).
    3. Оприходование готовой продукции:
       - Для каждой SlaughterYield создать output_batch если не задан:
         новый Batch с parent_batch = source_batch, origin_module=slaughter,
         accumulated_cost_uzs = source.accumulated_cost * (yield.share_percent / 100).
       - StockMovement INCOMING по каждой SlaughterYield на склад готовой.
    4. JournalEntry:
       - Dr 20.04 (Убойня) / Cr 10.02 (Живая птица)  — списание
       - Dr 43.01 (Тушки) / Cr 20.04 (Убойня)        — оприходование ГП
       amount = source_batch.accumulated_cost_uzs.
    5. shift.status = POSTED, end_time = now.

MVP-упрощение: output_batch на каждую позицию yield создаётся
опционально (только если явно указан SKU готовой тушки). В текущей
версии — генерируем output_batch для всех yields с quantity > 0,
распределяя cost пропорционально share_percent.
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
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement, Warehouse

from ..models import SlaughterQualityCheck, SlaughterShift, SlaughterYield


# GL policy
SLAUGHTER_COST_SUBACCOUNT = "20.04"
LIVE_BIRD_SUBACCOUNT = "10.02"
FINISHED_GOODS_SUBACCOUNT = "43.01"


class SlaughterPostError(ValidationError):
    pass


@dataclass
class SlaughterPostResult:
    shift: SlaughterShift
    source_batch: Batch
    output_batches: list[Batch]
    stock_movements: list[StockMovement]
    journal_entries: list[JournalEntry]


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise SlaughterPostError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


def _quantize_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@transaction.atomic
def post_slaughter_shift(
    shift: SlaughterShift,
    *,
    source_warehouse: Optional[Warehouse] = None,
    output_warehouse: Optional[Warehouse] = None,
    user=None,
) -> SlaughterPostResult:
    """
    Провести смену убоя.

    Args:
        shift: SlaughterShift в статусе ACTIVE/CLOSED.
        source_warehouse: откуда списывается живая птица. Если None —
                          используется warehouse связанный с target_block
                          (получатель feedlot batch).
        output_warehouse: куда оприходуется готовая продукция (43-склад).
    """
    # 1. Lock
    shift = SlaughterShift.objects.select_for_update().get(pk=shift.pk)
    shift = SlaughterShift.objects.select_related(
        "organization", "module", "line_block", "source_batch",
        "source_batch__current_module", "source_batch__current_block",
    ).get(pk=shift.pk)

    # 2. Status guard
    if shift.status not in (
        SlaughterShift.Status.ACTIVE,
        SlaughterShift.Status.CLOSED,
    ):
        raise SlaughterPostError(
            {"status": f"Нельзя провести смену в статусе {shift.get_status_display()}."}
        )

    # 3. Full clean (включая withdrawal-guard!)
    shift.full_clean(exclude=None)

    # 4. Yields должны быть
    yields = list(shift.yields.select_related("nomenclature", "unit"))
    if not yields:
        raise SlaughterPostError(
            {"yields": "В смене нет позиций выхода."}
        )

    org = shift.organization
    source_batch = shift.source_batch
    total_cost = source_batch.accumulated_cost_uzs

    # 4b. Гард: source_batch.current_module == slaughter
    if source_batch.current_module_id != shift.module_id:
        raise SlaughterPostError(
            {
                "source_batch": (
                    "Партия не в модуле убоя. Сначала примите "
                    "транзфер из откорма."
                )
            }
        )

    # 4c. Гард: ветеринарная инспекция пройдена
    qc = SlaughterQualityCheck.objects.filter(shift=shift).first()
    if qc is None or not qc.vet_inspection_passed:
        raise SlaughterPostError(
            {
                "quality_check": (
                    "Невозможно провести смену без отметки ветеринара "
                    "(QualityCheck.vet_inspection_passed=True)."
                )
            }
        )

    # 4d. Гард: сумма выходов ≈ живой вес (±10%)
    _KG_CODES = {"kg", "кг"}
    total_yield_kg = sum(
        (y.quantity for y in yields if y.unit and y.unit.code.lower() in _KG_CODES),
        Decimal("0"),
    )
    live_kg = shift.live_weight_kg_total or Decimal("0")
    if live_kg > 0 and total_yield_kg > 0:
        deviation = abs(total_yield_kg - live_kg) / live_kg
        if deviation > Decimal("0.10"):
            raise SlaughterPostError(
                {
                    "yields": (
                        f"Сумма выходов {total_yield_kg} кг отклоняется от "
                        f"живого веса {live_kg} кг на {deviation * 100:.1f}% "
                        f"(>10%). Проверьте данные."
                    )
                }
            )

    # 5. Warehouses
    if output_warehouse is None:
        raise SlaughterPostError(
            {"output_warehouse": "Укажите склад готовой продукции."}
        )
    if output_warehouse.organization_id != org.id:
        raise SlaughterPostError(
            {"output_warehouse": "Склад из другой организации."}
        )
    # 5b. Гард: source_warehouse обязателен
    if source_warehouse is None:
        raise SlaughterPostError(
            {
                "source_warehouse": (
                    "Не указан склад источник (склад живой птицы). "
                    "Без него OUTGOING StockMovement не создаётся."
                )
            }
        )
    if source_warehouse.organization_id != org.id:
        raise SlaughterPostError(
            {"source_warehouse": "Склад из другой организации."}
        )

    now = timezone.now()
    entry_date = shift.shift_date
    ct_shift = ContentType.objects.get_for_model(SlaughterShift)

    stock_movements: list[StockMovement] = []
    output_batches: list[Batch] = []
    journal_entries: list[JournalEntry] = []

    # 6. StockMovement OUTGOING (списание живой птицы)
    sm_out_number = next_doc_number(
        StockMovement, organization=org, prefix="СД", on_date=entry_date
    )
    sm_out = StockMovement(
        organization=org,
        module=shift.module,
        doc_number=sm_out_number,
        kind=StockMovement.Kind.OUTGOING,
        date=now,
        nomenclature=source_batch.nomenclature,
        quantity=Decimal(shift.live_heads_received),
        unit_price_uzs=(
            (total_cost / shift.live_heads_received).quantize(Decimal("0.01"))
            if shift.live_heads_received
            else Decimal("0.01")
        ),
        amount_uzs=total_cost,
        warehouse_from=source_warehouse,
        warehouse_to=None,
        batch=source_batch,
        source_content_type=ct_shift,
        source_object_id=shift.id,
        created_by=user,
    )
    sm_out.full_clean(exclude=None)
    sm_out.save()
    stock_movements.append(sm_out)

    # 7. JE #1: Dr 20.04 / Cr 10.02
    cost_sub = _get_subaccount(org, SLAUGHTER_COST_SUBACCOUNT)
    bird_sub = _get_subaccount(org, LIVE_BIRD_SUBACCOUNT)
    fg_sub = _get_subaccount(org, FINISHED_GOODS_SUBACCOUNT)

    je_writeoff_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=entry_date
    )
    je_writeoff = JournalEntry(
        organization=org,
        module=shift.module,
        doc_number=je_writeoff_number,
        entry_date=entry_date,
        description=(
            f"Убой {shift.doc_number} · списание живой птицы "
            f"{source_batch.doc_number} ({shift.live_heads_received} гол)"
        ),
        debit_subaccount=cost_sub,
        credit_subaccount=bird_sub,
        amount_uzs=total_cost,
        source_content_type=ct_shift,
        source_object_id=shift.id,
        batch=source_batch,
        created_by=user,
    )
    je_writeoff.full_clean(exclude=None)
    je_writeoff.save()
    journal_entries.append(je_writeoff)

    # 8. Оприходование выхода (yields)
    # Пропорция cost по share_percent. Если share не задан — равномерно.
    total_share = sum(
        (y.share_percent for y in yields if y.share_percent is not None),
        Decimal("0"),
    )

    for yield_row in yields:
        if yield_row.share_percent is not None and total_share > 0:
            allocated_cost = _quantize_money(
                total_cost * yield_row.share_percent / total_share
            )
        else:
            allocated_cost = _quantize_money(total_cost / len(yields))

        # Output batch
        out_batch = yield_row.output_batch
        if out_batch is None:
            out_doc = f"П-{yield_row.nomenclature.sku}-" + next_doc_number(
                Batch, organization=org, prefix="ПВ", on_date=entry_date, width=4
            ).split("-")[-1]
            out_batch = Batch.objects.create(
                organization=org,
                doc_number=out_doc,
                nomenclature=yield_row.nomenclature,
                unit=yield_row.unit,
                origin_module=shift.module,
                current_module=shift.module,
                current_block=shift.line_block,
                parent_batch=source_batch,
                current_quantity=yield_row.quantity,
                initial_quantity=yield_row.quantity,
                accumulated_cost_uzs=allocated_cost,
                started_at=entry_date,
                created_by=user,
            )
            yield_row.output_batch = out_batch
            yield_row.save(update_fields=["output_batch", "updated_at"])
        output_batches.append(out_batch)

        # StockMovement INCOMING на склад готовой продукции
        sm_in_number = next_doc_number(
            StockMovement, organization=org, prefix="СД", on_date=entry_date
        )
        unit_price = (
            (allocated_cost / yield_row.quantity).quantize(Decimal("0.01"))
            if yield_row.quantity
            else Decimal("0.01")
        )
        sm_in = StockMovement(
            organization=org,
            module=shift.module,
            doc_number=sm_in_number,
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=yield_row.nomenclature,
            quantity=yield_row.quantity,
            unit_price_uzs=unit_price,
            amount_uzs=allocated_cost,
            warehouse_to=output_warehouse,
            warehouse_from=None,
            batch=out_batch,
            source_content_type=ct_shift,
            source_object_id=shift.id,
            created_by=user,
        )
        sm_in.full_clean(exclude=None)
        sm_in.save()
        stock_movements.append(sm_in)

    # 9. JE #2: Dr 43.01 / Cr 20.04 (закрытие убойного производства)
    je_finished_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=entry_date
    )
    je_finished = JournalEntry(
        organization=org,
        module=shift.module,
        doc_number=je_finished_number,
        entry_date=entry_date,
        description=(
            f"Убой {shift.doc_number} · оприходование готовой продукции "
            f"({len(yields)} позиций)"
        ),
        debit_subaccount=fg_sub,
        credit_subaccount=cost_sub,
        amount_uzs=total_cost,
        source_content_type=ct_shift,
        source_object_id=shift.id,
        batch=source_batch,
        created_by=user,
    )
    je_finished.full_clean(exclude=None)
    je_finished.save()
    journal_entries.append(je_finished)

    # 10. Закрытие source_batch
    source_batch.current_quantity = Decimal("0")
    source_batch.state = Batch.State.COMPLETED
    source_batch.completed_at = entry_date
    source_batch.save(
        update_fields=["current_quantity", "state", "completed_at", "updated_at"]
    )

    # 11. Финализация shift
    shift.status = SlaughterShift.Status.POSTED
    if not shift.end_time:
        shift.end_time = now
    shift.save(update_fields=["status", "end_time", "updated_at"])

    audit_log(
        organization=shift.organization,
        module=shift.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=shift,
        action_verb=(
            f"posted slaughter shift {shift.doc_number} · "
            f"{source_batch.doc_number} → {len(output_batches)} SKU"
        ),
    )

    return SlaughterPostResult(
        shift=shift,
        source_batch=source_batch,
        output_batches=output_batches,
        stock_movements=stock_movements,
        journal_entries=journal_entries,
    )
