"""
Сервис `depopulate_herd` — снятие родительского стада (либо частичная
редукция current_heads, либо полное снятие с переводом в статус
DEPOPULATED).

Atomic:
    1. Guards:
       - herd.status in {GROWING, PRODUCING}
       - reduce_by > 0
       - reduce_by <= herd.current_heads
    2. herd.current_heads -= reduce_by (через F()).
    3. Если current_heads == 0 → status = DEPOPULATED.
    4. Опц. BreedingMortality запись с причиной «плановое снятие»
       (если mark_as_mortality=True) — удобно для аналитики.
    5. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log

from ..models import BreedingHerd, BreedingMortality


class HerdDepopulateError(ValidationError):
    pass


@dataclass
class HerdDepopulateResult:
    herd: BreedingHerd
    mortality_record: Optional[BreedingMortality]


@transaction.atomic
def depopulate_herd(
    herd: BreedingHerd,
    *,
    reduce_by: int,
    date: Optional[date_type] = None,
    reason: str = "",
    mark_as_mortality: bool = False,
    user=None,
) -> HerdDepopulateResult:
    if reduce_by <= 0:
        raise HerdDepopulateError({"reduce_by": "Должно быть > 0."})

    herd = BreedingHerd.objects.select_for_update().get(pk=herd.pk)

    if herd.status not in (
        BreedingHerd.Status.GROWING,
        BreedingHerd.Status.PRODUCING,
    ):
        raise HerdDepopulateError(
            {"status": (
                f"Снятие возможно из GROWING/PRODUCING, "
                f"текущий: {herd.get_status_display()}."
            )}
        )

    if reduce_by > herd.current_heads:
        raise HerdDepopulateError(
            {"reduce_by": (
                f"Снимаем {reduce_by}, текущее поголовье {herd.current_heads}."
            )}
        )

    when = date or timezone.localdate()

    mortality_record = None
    if mark_as_mortality:
        # unique_together=(herd, date) — если за день уже есть запись, мержим.
        existing = BreedingMortality.objects.filter(herd=herd, date=when).first()
        if existing:
            # UPDATE — сигнал post_save(created=False) НЕ декрементит
            # current_heads, делаем вручную.
            existing.dead_count = existing.dead_count + reduce_by
            existing.notes = (
                (existing.notes + f"\n+{reduce_by}: {reason}").strip()
                if existing.notes else f"+{reduce_by}: {reason}"
            )
            existing.save(update_fields=["dead_count", "notes", "updated_at"])
            BreedingHerd.objects.filter(pk=herd.pk).update(
                current_heads=F("current_heads") - reduce_by
            )
            mortality_record = existing
        else:
            # CREATE — сигнал post_save(created=True) сам уменьшит current_heads.
            mortality_record = BreedingMortality.objects.create(
                herd=herd, date=when, dead_count=reduce_by,
                cause="плановое снятие", notes=reason,
                recorded_by=user,
            )
    else:
        # Без пометки как падёж — просто уменьшаем поголовье.
        BreedingHerd.objects.filter(pk=herd.pk).update(
            current_heads=F("current_heads") - reduce_by
        )

    herd.refresh_from_db(fields=["current_heads", "status"])

    if herd.current_heads <= 0 and herd.status != BreedingHerd.Status.DEPOPULATED:
        herd.current_heads = 0
        herd.status = BreedingHerd.Status.DEPOPULATED
        herd.save(update_fields=["current_heads", "status", "updated_at"])

    audit_log(
        organization=herd.organization,
        module=herd.module,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=herd,
        action_verb=(
            f"depopulated herd {herd.doc_number} by {reduce_by} "
            f"(now {herd.current_heads} heads) — {reason}"
        ),
    )

    return HerdDepopulateResult(herd=herd, mortality_record=mortality_record)
