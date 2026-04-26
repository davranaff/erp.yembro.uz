"""
Сервис `post_feed_consumption` — учёт скармливания корма партии откорма.

Что делает в одной atomic-транзакции:
    1. Guards: feedlot_batch активна (placed/growing/ready), feed_batch
       одобрена (status=APPROVED), достаточно остатка корма.
    2. Декремент FeedBatch.current_quantity_kg на total_kg (через F()).
       Если остаток стал 0 → status=DEPLETED.
    3. Расчёт period_fcr (если есть взвешивания на границах периода).
    4. Расчёт per_head_g = (total_kg * 1000) / current_heads.
    5. Создаёт FeedlotFeedConsumption.
    6. Cost allocation: amount_uzs = total_kg × feed_batch.unit_cost_uzs.
       Накапливает в Batch.accumulated_cost_uzs (с птицей идёт стоимость
       съеденного корма — пригодится в slaughter для unit cost тушки).
    7. JournalEntry: Дт 20.02 (Откорм НЗП) / Кт 10.05 (Готовая корма).
    8. StockMovement OUTGOING со склада feed на «потребление».
    9. AuditLog.

GL-policy:
    20.02 — НЗП Откорм (Дт)
    10.05 — Готовый комбикорм на складе (Кт)
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
from apps.feed.models import FeedBatch
from apps.warehouses.models import StockMovement, Warehouse

from ..models import FeedlotBatch, FeedlotFeedConsumption
from .fcr import compute_period_fcr


FEEDLOT_WIP_CODE = "20.02"
FEED_INVENTORY_CODE = "10.05"


class FeedConsumptionError(ValidationError):
    pass


@dataclass
class FeedConsumptionResult:
    consumption: FeedlotFeedConsumption
    feed_batch: FeedBatch
    feedlot_batch: FeedlotBatch
    stock_movement: StockMovement
    journal_entry: JournalEntry
    amount_uzs: Decimal


def _q_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise FeedConsumptionError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


@transaction.atomic
def post_feed_consumption(
    feedlot_batch: FeedlotBatch,
    *,
    feed_batch: FeedBatch,
    total_kg: Decimal,
    period_from_day: int,
    period_to_day: int,
    feed_type: str,
    notes: str = "",
    user=None,
) -> FeedConsumptionResult:
    """
    Списать total_kg корма со склада на партию откорма.

    Args:
        feedlot_batch: партия откорма куда идёт корм.
        feed_batch: партия готового корма со склада feed.
        total_kg: сколько кг скормили.
        period_from_day, period_to_day: за какой период в днях возраста.
        feed_type: 'start' | 'growth' | 'finish'.
    """
    # 1. Lock + guards
    feedlot_batch = FeedlotBatch.objects.select_for_update().get(pk=feedlot_batch.pk)
    feedlot_batch = FeedlotBatch.objects.select_related(
        "organization", "module", "batch"
    ).get(pk=feedlot_batch.pk)

    if feedlot_batch.status not in (
        FeedlotBatch.Status.PLACED,
        FeedlotBatch.Status.GROWING,
        FeedlotBatch.Status.READY_SLAUGHTER,
    ):
        raise FeedConsumptionError(
            {"status": (
                f"Кормить можно только активную партию, текущий статус: "
                f"{feedlot_batch.get_status_display()}."
            )}
        )

    if total_kg is None or Decimal(total_kg) <= 0:
        raise FeedConsumptionError({"total_kg": "Количество должно быть больше нуля."})

    total = Decimal(total_kg)

    if period_from_day < 0 or period_to_day < period_from_day:
        raise FeedConsumptionError(
            {"period_to_day": "Конец периода раньше его начала."}
        )

    if feed_type not in {ft.value for ft in FeedlotFeedConsumption.FeedType}:
        raise FeedConsumptionError({"feed_type": f"Недопустимое значение: {feed_type}."})

    feed_batch = FeedBatch.objects.select_for_update().get(pk=feed_batch.pk)

    if feed_batch.status != FeedBatch.Status.APPROVED:
        raise FeedConsumptionError(
            {"feed_batch": (
                f"Партия корма {feed_batch.doc_number} в статусе "
                f"«{feed_batch.get_status_display()}» — расходовать можно только одобренную."
            )}
        )

    if Decimal(feed_batch.current_quantity_kg) < total:
        raise FeedConsumptionError(
            {"feed_batch": (
                f"Недостаточно остатка в партии корма {feed_batch.doc_number}: "
                f"требуется {total}, доступно {feed_batch.current_quantity_kg} кг."
            )}
        )

    if feed_batch.organization_id != feedlot_batch.organization_id:
        raise FeedConsumptionError(
            {"feed_batch": "Партия корма из другой организации."}
        )

    # 2. Декремент FeedBatch
    FeedBatch.objects.filter(pk=feed_batch.pk).update(
        current_quantity_kg=F("current_quantity_kg") - total
    )
    feed_batch.refresh_from_db(fields=["current_quantity_kg"])
    if feed_batch.current_quantity_kg == 0 and feed_batch.status == FeedBatch.Status.APPROVED:
        feed_batch.status = FeedBatch.Status.DEPLETED
        feed_batch.save(update_fields=["status", "updated_at"])

    # 3. period_fcr (опционально, может быть None если нет взвешиваний)
    fcr = compute_period_fcr(feedlot_batch, period_from_day, period_to_day, total)

    # 4. per_head_g
    heads = feedlot_batch.current_heads or 0
    per_head_g = (
        (total * Decimal("1000") / Decimal(heads)).quantize(Decimal("0.001"))
        if heads > 0 else None
    )

    # 5. FeedlotFeedConsumption
    cons = FeedlotFeedConsumption.objects.create(
        feedlot_batch=feedlot_batch,
        period_from_day=period_from_day,
        period_to_day=period_to_day,
        feed_type=feed_type,
        feed_batch=feed_batch,
        total_kg=total,
        per_head_g=per_head_g,
        period_fcr=fcr,
        notes=notes,
    )

    # 6. Cost allocation: накапливаем стоимость корма на batch
    unit_cost = Decimal(feed_batch.unit_cost_uzs or 0)
    amount_uzs = _q_money(total * unit_cost)
    if amount_uzs > 0:
        Batch.objects.filter(pk=feedlot_batch.batch_id).update(
            accumulated_cost_uzs=F("accumulated_cost_uzs") + amount_uzs
        )

    # 7. JE Дт 20.02 / Кт 10.05
    org = feedlot_batch.organization
    debit = _get_subaccount(org, FEEDLOT_WIP_CODE)
    credit = _get_subaccount(org, FEED_INVENTORY_CODE)
    je_number = next_doc_number(
        JournalEntry,
        organization=org,
        prefix="ПР",
    )
    je = JournalEntry.objects.create(
        organization=org,
        module=feedlot_batch.module,
        doc_number=je_number,
        entry_date=timezone.localdate(),
        description=(
            f"Скармливание корма {feed_batch.doc_number} → "
            f"{feedlot_batch.doc_number} · {total} кг × {unit_cost} = {amount_uzs}"
        ),
        debit_subaccount=debit,
        credit_subaccount=credit,
        amount_uzs=amount_uzs,
        source_content_type=ContentType.objects.get_for_model(FeedlotFeedConsumption),
        source_object_id=cons.id,
        batch=feedlot_batch.batch,
        created_by=user,
    )

    # 8. StockMovement OUTGOING со склада готовой продукции feed
    sm_number = next_doc_number(StockMovement, organization=org, prefix="СД")
    sm = _create_simple_stock_movement(
        org=org, module=feedlot_batch.module, doc_number=sm_number,
        feed_batch=feed_batch, total=total, unit_cost=unit_cost,
        amount_uzs=amount_uzs, batch=feedlot_batch.batch, cons=cons, user=user,
    )

    # 9. AuditLog
    audit_log(
        organization=org,
        module=feedlot_batch.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=cons,
        action_verb=(
            f"feed consumption {total} kg from {feed_batch.doc_number} "
            f"to {feedlot_batch.doc_number}"
        ),
    )

    return FeedConsumptionResult(
        consumption=cons,
        feed_batch=feed_batch,
        feedlot_batch=feedlot_batch,
        stock_movement=sm,
        journal_entry=je,
        amount_uzs=amount_uzs,
    )


def _create_simple_stock_movement(
    *, org, module, doc_number, feed_batch, total, unit_cost,
    amount_uzs, batch, cons, user,
) -> StockMovement:
    """
    Упрощённое создание StockMovement без обращения к recipe_nomenclature,
    которой может не быть на FeedBatch.recipe_version. Берём первую
    nomenclature из nomenclature справочника или из существующего движения
    по этой партии корма (если есть).
    """
    from apps.nomenclature.models import NomenclatureItem
    # Попробуем найти nomenclature по последнему StockMovement этой feed_batch
    nom = None
    last_sm = (
        StockMovement.objects.filter(
            kind=StockMovement.Kind.INCOMING,
            source_object_id=feed_batch.produced_by_task_id,
        )
        .order_by("-date")
        .first()
    )
    if last_sm and last_sm.nomenclature_id:
        nom = last_sm.nomenclature
    if nom is None:
        # Fallback: первая активная номенклатура комбикорма
        nom = NomenclatureItem.objects.filter(
            organization=org, is_active=True,
        ).first()

    return StockMovement.objects.create(
        organization=org,
        module=module,
        doc_number=doc_number,
        kind=StockMovement.Kind.OUTGOING,
        date=timezone.now(),
        nomenclature=nom,
        quantity=total,
        unit_price_uzs=unit_cost,
        amount_uzs=amount_uzs,
        warehouse_from=feed_batch.storage_warehouse,
        warehouse_to=None,
        batch=batch,
        source_content_type=ContentType.objects.get_for_model(FeedlotFeedConsumption),
        source_object_id=cons.id,
        created_by=user,
    )
