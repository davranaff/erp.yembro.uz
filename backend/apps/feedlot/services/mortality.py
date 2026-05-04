"""
Сервис `apply_mortality` — учёт падежа на feedlot-партии.

Что делает в одной atomic-транзакции:
    1. Guards: dead_count > 0, current_heads >= dead_count.
    2. Создаёт FeedlotMortality.
    3. Декремент FeedlotBatch.current_heads и Batch.current_quantity.
    4. Cost allocation: рассчитывает unit_cost = batch.accumulated_cost / heads_before
       и уменьшает Batch.accumulated_cost_uzs на (dead_count × unit_cost).
       Это гарантирует что мёртвая птица не несёт cost на оставшихся.
    5. JournalEntry: Дт 91.02 (Прочие расходы) / Кт 20.02 (Откорм НЗП)
       на (dead_count × unit_cost). Падёж становится убытком сразу.
    6. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number

from ..models import FeedlotBatch, FeedlotMortality


# GL-policy
OPEX_OUT_CODE = "91.02"
FEEDLOT_WIP_CODE = "20.02"


class MortalityError(ValidationError):
    pass


@dataclass
class MortalityResult:
    record: FeedlotMortality
    feedlot_batch: FeedlotBatch
    batch: Batch
    journal_entry: Optional[JournalEntry] = None
    loss_amount_uzs: Decimal = Decimal("0")


def _q_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_subaccount(org, code: str) -> Optional[GLSubaccount]:
    """
    Опционально: если плана счетов нет (тесты) — возвращаем None и
    просто пропускаем JE (модель работает, бухгалтерии не возникает).
    """
    return GLSubaccount.objects.filter(
        account__organization=org, code=code,
    ).select_related("account").first()


@transaction.atomic
def apply_mortality(
    feedlot_batch: FeedlotBatch,
    *,
    date: date_type,
    day_of_age: int,
    dead_count: int,
    cause: str = "",
    notes: str = "",
    user=None,
) -> MortalityResult:
    if dead_count <= 0:
        raise MortalityError({"dead_count": "Должно быть больше нуля."})

    feedlot_batch = FeedlotBatch.objects.select_for_update().get(pk=feedlot_batch.pk)
    feedlot_batch = FeedlotBatch.objects.select_related(
        "batch", "organization", "module",
    ).get(pk=feedlot_batch.pk)

    if feedlot_batch.current_heads < dead_count:
        raise MortalityError(
            {
                "dead_count": (
                    f"Падёж {dead_count} > текущее поголовье "
                    f"{feedlot_batch.current_heads}."
                )
            }
        )

    # Snapshot до декремента — нужен для расчёта unit_cost
    heads_before = feedlot_batch.current_heads
    batch = feedlot_batch.batch
    cost_before = Decimal(batch.accumulated_cost_uzs or 0)
    unit_cost = (
        (cost_before / Decimal(heads_before)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        if heads_before > 0 and cost_before > 0
        else Decimal("0")
    )
    loss_amount = _q_money(unit_cost * Decimal(dead_count))

    record = FeedlotMortality.objects.create(
        feedlot_batch=feedlot_batch,
        date=date,
        day_of_age=day_of_age,
        dead_count=dead_count,
        cause=cause,
        notes=notes,
        recorded_by=user,
    )

    # Декремент current_heads через F()
    FeedlotBatch.objects.filter(pk=feedlot_batch.pk).update(
        current_heads=F("current_heads") - dead_count
    )
    feedlot_batch.refresh_from_db(fields=["current_heads"])

    # Декремент batch.current_quantity и accumulated_cost
    update_kwargs = {"current_quantity": F("current_quantity") - Decimal(dead_count)}
    if loss_amount > 0:
        update_kwargs["accumulated_cost_uzs"] = (
            F("accumulated_cost_uzs") - loss_amount
        )
    Batch.objects.filter(pk=batch.pk).update(**update_kwargs)
    batch.refresh_from_db(fields=["current_quantity", "accumulated_cost_uzs"])

    # JournalEntry: Дт 91.02 / Кт 20.02 (только если loss_amount > 0)
    je = None
    if loss_amount > 0:
        org = feedlot_batch.organization
        debit = _get_subaccount(org, OPEX_OUT_CODE)
        credit = _get_subaccount(org, FEEDLOT_WIP_CODE)
        if debit and credit:
            je_number = next_doc_number(
                JournalEntry, organization=org, prefix="ПР",
            )
            je = JournalEntry.objects.create(
                organization=org,
                module=feedlot_batch.module,
                doc_number=je_number,
                entry_date=date,
                description=(
                    f"Падёж {feedlot_batch.doc_number} · {dead_count} гол × "
                    f"{unit_cost} = {loss_amount}"
                ),
                debit_subaccount=debit,
                credit_subaccount=credit,
                amount_uzs=loss_amount,
                source_content_type=ContentType.objects.get_for_model(FeedlotMortality),
                source_object_id=record.id,
                batch=batch,
                created_by=user,
            )

    audit_log(
        organization=feedlot_batch.organization,
        module=feedlot_batch.module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=record,
        action_verb=(
            f"mortality {dead_count} head in {feedlot_batch.doc_number} "
            f"day {day_of_age} · loss {loss_amount}"
        ),
    )

    return MortalityResult(
        record=record,
        feedlot_batch=feedlot_batch,
        batch=batch,
        journal_entry=je,
        loss_amount_uzs=loss_amount,
    )
