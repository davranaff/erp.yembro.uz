"""
Сервис `post_feed_consumption` — проведение записи суточного расхода корма
родительским стадом.

Делает (в одной atomic-транзакции):
    1. Декремент FeedBatch.current_quantity_kg (если feed_batch задан).
    2. JournalEntry: Дт 20.01 (НЗП маточник) / Кт 10.05 (Корма на складе).
    3. BatchCostEntry(FEED) на последнюю ACTIVE яичную партию стада — чтобы
       накопленная себестоимость партии яиц росла по мере кормления стада.
       Если ACTIVE egg-партии нет, шаг 3 пропускается (только JE+декремент).

Edge cases:
    - feed_batch=None: журналим BFC без списания FeedBatch и без JE, только
      как справочная запись о потреблении (не хватает цены). В тесте это
      проверяется (test_no_feed_batch_skips_posting).
    - quantity_kg > FeedBatch.current_quantity_kg: ValidationError (не списываем в минус).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchCostEntry
from apps.common.services.numbering import next_doc_number
from apps.feed.models import FeedBatch
from apps.modules.models import Module

from ..models import BreedingFeedConsumption


# Субсчета GL (см. apps/accounting/migrations/0005_seed_chart_of_accounts.py)
MATOCHNIK_WIP_CODE = "20.01"      # НЗП маточника
FEED_INVENTORY_CODE = "10.05"     # Корма на складе


class FeedConsumptionPostError(ValidationError):
    pass


@dataclass
class FeedConsumptionPostResult:
    consumption: BreedingFeedConsumption
    journal_entry: Optional[JournalEntry]
    batch_cost_entry: Optional[BatchCostEntry]
    total_cost_uzs: Decimal
    egg_batch: Optional[Batch]


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise FeedConsumptionPostError(
            {"__all__": (
                f"Субсчёт {code} не найден в организации "
                f"{org.code}. Проверьте seed плана счетов."
            )}
        ) from exc


def _find_active_egg_batch(herd, matochnik_mod) -> Optional[Batch]:
    """
    Последняя ACTIVE яичная партия стада. Она находится через
    DailyEggProduction.outgoing_batch (связь herd → batch).
    """
    from ..models import DailyEggProduction
    batch_ids = (
        DailyEggProduction.objects.filter(
            herd=herd, outgoing_batch__isnull=False,
        )
        .values_list("outgoing_batch_id", flat=True)
        .distinct()
    )
    return (
        Batch.objects.filter(
            pk__in=batch_ids,
            state=Batch.State.ACTIVE,
            origin_module=matochnik_mod,
        )
        .order_by("-started_at")
        .first()
    )


@transaction.atomic
def post_feed_consumption(
    consumption: BreedingFeedConsumption, *, user=None
) -> FeedConsumptionPostResult:
    """
    Провести запись суточного расхода корма: списать с FeedBatch, создать JE,
    обновить accumulated_cost_uzs активной egg-партии.

    Вызывается один раз при создании BreedingFeedConsumption (из ViewSet).
    """
    herd = consumption.herd
    org = herd.organization
    feed_batch = consumption.feed_batch

    # Без feed_batch — только журналим BFC (не можем посчитать стоимость).
    if feed_batch is None:
        return FeedConsumptionPostResult(
            consumption=consumption,
            journal_entry=None,
            batch_cost_entry=None,
            total_cost_uzs=Decimal("0"),
            egg_batch=None,
        )

    # Row-lock на feed_batch для безопасного декремента.
    feed_batch = FeedBatch.objects.select_for_update().get(pk=feed_batch.pk)

    qty = Decimal(consumption.quantity_kg)
    if qty > feed_batch.current_quantity_kg:
        raise FeedConsumptionPostError({
            "quantity_kg": (
                f"Недостаточно корма: требуется {qty} кг, "
                f"остаток партии {feed_batch.doc_number} = "
                f"{feed_batch.current_quantity_kg} кг."
            )
        })

    total_cost = (qty * Decimal(feed_batch.unit_cost_uzs)).quantize(Decimal("0.01"))

    # 1. Декремент FeedBatch.current_quantity_kg и статус
    FeedBatch.objects.filter(pk=feed_batch.pk).update(
        current_quantity_kg=F("current_quantity_kg") - qty
    )
    feed_batch.refresh_from_db(fields=["current_quantity_kg"])
    if feed_batch.current_quantity_kg <= 0 and feed_batch.status != FeedBatch.Status.DEPLETED:
        feed_batch.status = FeedBatch.Status.DEPLETED
        feed_batch.save(update_fields=["status", "updated_at"])

    # 2. JournalEntry Дт 20.01 / Кт 10.05
    matochnik_mod = Module.objects.get(code="matochnik")
    debit_sub = _get_subaccount(org, MATOCHNIK_WIP_CODE)
    credit_sub = _get_subaccount(org, FEED_INVENTORY_CODE)

    ct = ContentType.objects.get_for_model(BreedingFeedConsumption)

    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=consumption.date,
    )
    je = JournalEntry(
        organization=org,
        module=matochnik_mod,
        doc_number=je_number,
        entry_date=consumption.date,
        description=(
            f"Кормление стада {herd.doc_number} · "
            f"{feed_batch.doc_number} · {qty} кг"
        ),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=total_cost,
        source_content_type=ct,
        source_object_id=consumption.id,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # 3. BatchCostEntry(FEED) на последней ACTIVE яичной партии стада.
    egg_batch = _find_active_egg_batch(herd, matochnik_mod)
    bce = None
    if egg_batch is not None:
        bce = BatchCostEntry.objects.create(
            batch=egg_batch,
            category=BatchCostEntry.Category.FEED,
            amount_uzs=total_cost,
            description=(
                f"Корм {feed_batch.doc_number} · {qty} кг "
                f"(стадо {herd.doc_number})"
            ),
            occurred_at=timezone.now(),
            module=matochnik_mod,
            source_content_type=ct,
            source_object_id=consumption.id,
            created_by=user,
        )
        Batch.objects.filter(pk=egg_batch.pk).update(
            accumulated_cost_uzs=F("accumulated_cost_uzs") + total_cost
        )

    audit_log(
        organization=org,
        module=matochnik_mod,
        actor=user,
        action=AuditLog.Action.POST,
        entity=consumption,
        action_verb=(
            f"feed consumption {herd.doc_number} · "
            f"{qty} kg · {total_cost} UZS"
        ),
    )

    return FeedConsumptionPostResult(
        consumption=consumption,
        journal_entry=je,
        batch_cost_entry=bce,
        total_cost_uzs=total_cost,
        egg_batch=egg_batch,
    )
