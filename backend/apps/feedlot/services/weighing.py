"""
Сервис `record_weighing` — контрольное взвешивание партии откорма.

Что делает в одной atomic-транзакции:
    1. Guards: feedlot_batch активна (не shipped), sample_size > 0,
       avg_weight_kg > 0. Уникальность (feedlot_batch, day_of_age) — на модели.
    2. Считает gain_kg = avg_weight − previous_avg_weight (если есть прошлое
       взвешивание).
    3. Создаёт DailyWeighing.
    4. Status transitions:
       - Если status == PLACED → переводит в GROWING (первое взвешивание =
         подтверждение что птица начала расти, статус двинулся).
       - Если avg_weight_kg ≥ target_weight_kg и status ∈ {PLACED, GROWING}
         → переводит в READY_SLAUGHTER.
    5. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import DailyWeighing, FeedlotBatch
from .fcr import get_latest_weighing


class WeighingError(ValidationError):
    pass


@dataclass
class WeighingResult:
    weighing: DailyWeighing
    feedlot_batch: FeedlotBatch
    status_changed: bool


def _q_kg(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def record_weighing(
    feedlot_batch: FeedlotBatch,
    *,
    date: date_type,
    day_of_age: int,
    sample_size: int,
    avg_weight_kg: Decimal,
    notes: str = "",
    user=None,
) -> WeighingResult:
    feedlot_batch = FeedlotBatch.objects.select_for_update().get(pk=feedlot_batch.pk)

    if feedlot_batch.status == FeedlotBatch.Status.SHIPPED:
        raise WeighingError(
            {"status": "Нельзя взвешивать отгруженную партию."}
        )

    if sample_size is None or sample_size <= 0:
        raise WeighingError({"sample_size": "Должно быть больше нуля."})

    avg = Decimal(avg_weight_kg) if avg_weight_kg is not None else None
    if avg is None or avg <= 0:
        raise WeighingError({"avg_weight_kg": "Должно быть больше нуля."})

    if day_of_age is None or day_of_age < 0:
        raise WeighingError({"day_of_age": "Должно быть >= 0."})

    # Уникальность по (feedlot_batch, day_of_age) — проверяем явно для
    # понятной ошибки (на модели тоже unique_together).
    if DailyWeighing.objects.filter(
        feedlot_batch=feedlot_batch, day_of_age=day_of_age,
    ).exists():
        raise WeighingError(
            {"day_of_age": f"Взвешивание за день {day_of_age} уже записано."}
        )

    # Расчёт gain_kg от предыдущего взвешивания
    prev = get_latest_weighing(feedlot_batch)
    gain = None
    if prev and Decimal(prev.avg_weight_kg) <= avg:
        gain = _q_kg(avg - Decimal(prev.avg_weight_kg))

    # Создание записи
    weighing = DailyWeighing.objects.create(
        feedlot_batch=feedlot_batch,
        date=date,
        day_of_age=day_of_age,
        sample_size=sample_size,
        avg_weight_kg=_q_kg(avg),
        gain_kg=gain,
        operator=user,
        notes=notes,
    )

    # Status transitions
    status_changed = False
    new_status = feedlot_batch.status

    if feedlot_batch.status == FeedlotBatch.Status.PLACED:
        new_status = FeedlotBatch.Status.GROWING
        status_changed = True

    target = Decimal(feedlot_batch.target_weight_kg or 0)
    if (
        target > 0
        and avg >= target
        and new_status in (
            FeedlotBatch.Status.PLACED,
            FeedlotBatch.Status.GROWING,
        )
    ):
        new_status = FeedlotBatch.Status.READY_SLAUGHTER
        status_changed = True

    if status_changed:
        feedlot_batch.status = new_status
        feedlot_batch.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=feedlot_batch.organization,
        module=feedlot_batch.module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=weighing,
        action_verb=(
            f"weighing day {day_of_age} avg={avg}kg sample={sample_size} "
            f"in {feedlot_batch.doc_number}"
        ),
    )

    return WeighingResult(
        weighing=weighing,
        feedlot_batch=feedlot_batch,
        status_changed=status_changed,
    )
