"""
Сервис `crystallize_egg_batch` — собрать суточные яйцесборы в партию яиц
для отправки в инкубацию.

Atomic:
    1. Guards:
       - Все DailyEggProduction за период должны принадлежать указанному herd.
       - Сумма (eggs_collected - unfit_eggs) > 0.
       - Все записи ещё не привязаны к outgoing_batch.
    2. Создать Batch (egg):
       - nomenclature = egg_nomenclature (параметр)
       - origin_module = matochnik
       - current_module = matochnik
       - current_block = herd.block
       - current_quantity = сумма "чистых" яиц
       - initial_quantity = то же
       - accumulated_cost_uzs = 0 (себестоимость появится позже,
         когда начнут накапливаться BatchCostEntry на корм/препараты/зарплату)
    3. Привязать каждую DailyEggProduction.outgoing_batch = новая партия.
    4. BatchChainStep #1 в matochnik/block.
    5. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchChainStep
from apps.common.services.numbering import next_doc_number
from apps.nomenclature.models import NomenclatureItem

from ..models import BreedingHerd, DailyEggProduction


class EggCrystallizeError(ValidationError):
    pass


@dataclass
class EggCrystallizeResult:
    batch: Batch
    herd: BreedingHerd
    records_count: int
    total_eggs: int
    chain_step: BatchChainStep


@transaction.atomic
def crystallize_egg_batch(
    herd: BreedingHerd,
    *,
    egg_nomenclature: NomenclatureItem,
    date_from: date_type,
    date_to: date_type,
    doc_number: Optional[str] = None,
    user=None,
) -> EggCrystallizeResult:
    """
    Собрать суточные яйцесборы за [date_from, date_to] в один Egg Batch.

    Args:
        herd: BreedingHerd — стадо, от которого собираем.
        egg_nomenclature: NomenclatureItem (категория «Яйцо»).
        date_from, date_to: включительный диапазон дат.
        doc_number: опц., если не задан — сгенерируется.
        user: актор.
    """
    herd = BreedingHerd.objects.select_for_update().get(pk=herd.pk)
    org = herd.organization

    if egg_nomenclature.organization_id != org.id:
        raise EggCrystallizeError(
            {"egg_nomenclature": "Номенклатура из другой организации."}
        )
    if date_from > date_to:
        raise EggCrystallizeError(
            {"date_to": "Конец диапазона раньше начала."}
        )

    records_qs = DailyEggProduction.objects.select_for_update().filter(
        herd=herd,
        date__gte=date_from,
        date__lte=date_to,
        outgoing_batch__isnull=True,  # ещё не привязаны
    )
    records = list(records_qs)
    if not records:
        raise EggCrystallizeError(
            {
                "records": (
                    f"Нет несвязанных яйцесборов за {date_from}..{date_to} "
                    f"для стада {herd.doc_number}."
                )
            }
        )

    total_eggs = 0
    for r in records:
        net = (r.eggs_collected or 0) - (r.unfit_eggs or 0)
        if net > 0:
            total_eggs += net
    if total_eggs <= 0:
        raise EggCrystallizeError(
            {"records": "Суммарно чистых яиц — 0, партию не создать."}
        )

    # Создать партию
    number = doc_number or next_doc_number(
        Batch, organization=org, prefix="П-Я",
        on_date=date_to, width=5,
    )
    batch = Batch.objects.create(
        organization=org,
        doc_number=number,
        nomenclature=egg_nomenclature,
        unit=egg_nomenclature.unit,
        origin_module=herd.module,
        current_module=herd.module,
        current_block=herd.block,
        current_quantity=Decimal(total_eggs),
        initial_quantity=Decimal(total_eggs),
        accumulated_cost_uzs=Decimal("0"),
        started_at=date_from,
        created_by=user,
    )

    # Привязать все records
    records_qs.update(outgoing_batch=batch)

    # Chain step
    step = BatchChainStep.objects.create(
        batch=batch,
        sequence=1,
        module=herd.module,
        block=herd.block,
        entered_at=timezone.now(),
        quantity_in=Decimal(total_eggs),
    )

    audit_log(
        organization=org,
        module=herd.module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=batch,
        action_verb=(
            f"crystallized egg batch {batch.doc_number} from herd "
            f"{herd.doc_number} ({total_eggs} шт)"
        ),
    )

    return EggCrystallizeResult(
        batch=batch,
        herd=herd,
        records_count=len(records),
        total_eggs=total_eggs,
        chain_step=step,
    )
