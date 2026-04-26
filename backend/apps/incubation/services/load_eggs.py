"""
Сервис `load_eggs_to_incubator` — загрузка яиц в инкубатор.

Заменяет стандартный `POST /api/incubation/runs/` — добавляет guards:
    - batch.origin_module.code == 'matochnik' (яйца пришли от родительского стада)
    - batch.current_module.code == 'incubation' (партия уже передана трансфером)
    - batch.state == ACTIVE
    - batch.current_quantity >= eggs_loaded (хватает яиц)
    - incubator_block.kind == INCUBATION
    - incubator_block.module.code == 'incubation'
    - cross-org integrity

При успехе:
    - создаёт IncubationRun (status=INCUBATING)
    - переводит partition.current_block → incubator_block
    - генерирует doc_number (ИНК-YYYY-NNNNN) если не задан
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type, timedelta
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import ProductionBlock

from ..models import IncubationRun


class LoadEggsError(ValidationError):
    pass


@dataclass
class LoadEggsResult:
    run: IncubationRun


@transaction.atomic
def load_eggs_to_incubator(
    *,
    organization,
    module,
    batch: Batch,
    incubator_block: ProductionBlock,
    loaded_date: date_type,
    eggs_loaded: int,
    technologist,
    days_total: int = 21,
    expected_hatch_date: Optional[date_type] = None,
    doc_number: str = "",
    notes: str = "",
    user=None,
) -> LoadEggsResult:
    # Lock batch
    batch = Batch.objects.select_for_update().get(pk=batch.pk)
    batch = Batch.objects.select_related(
        "origin_module", "current_module", "current_block", "organization",
    ).get(pk=batch.pk)

    # Guards
    if batch.organization_id != organization.id:
        raise LoadEggsError({"batch": "Партия из другой организации."})

    if not batch.origin_module or batch.origin_module.code != "matochnik":
        raise LoadEggsError({"batch": (
            f"Партия не из маточника (origin={batch.origin_module.code if batch.origin_module_id else 'None'})."
        )})

    if batch.state != Batch.State.ACTIVE:
        raise LoadEggsError({"batch": (
            f"Партия должна быть активной, текущий статус: {batch.get_state_display()}."
        )})

    if eggs_loaded <= 0:
        raise LoadEggsError({"eggs_loaded": "Количество должно быть больше нуля."})

    if batch.current_quantity < eggs_loaded:
        raise LoadEggsError({"eggs_loaded": (
            f"В партии {batch.current_quantity} яиц, запрошено {eggs_loaded}."
        )})

    if not batch.current_module or batch.current_module.code != "incubation":
        raise LoadEggsError({"batch": (
            f"Партия должна быть в модуле incubation (сейчас: "
            f"{batch.current_module.code if batch.current_module_id else 'None'}). "
            f"Передайте её из маточника кнопкой «→ В инкубацию»."
        )})

    if incubator_block.organization_id != organization.id:
        raise LoadEggsError({"incubator_block": "Блок из другой организации."})
    if incubator_block.module_id != module.id:
        raise LoadEggsError({"incubator_block": "Блок не принадлежит модулю инкубации."})
    if incubator_block.kind != ProductionBlock.Kind.INCUBATION:
        raise LoadEggsError({"incubator_block": "Блок должен быть инкубационным шкафом."})

    # doc_number
    if not doc_number:
        doc_number = next_doc_number(
            IncubationRun, organization=organization,
            prefix="ИНК", on_date=loaded_date,
        )

    # expected_hatch_date по умолчанию = loaded + days_total
    if expected_hatch_date is None:
        expected_hatch_date = loaded_date + timedelta(days=days_total)

    # Создаём run
    run = IncubationRun(
        organization=organization,
        module=module,
        incubator_block=incubator_block,
        batch=batch,
        doc_number=doc_number,
        loaded_date=loaded_date,
        expected_hatch_date=expected_hatch_date,
        eggs_loaded=eggs_loaded,
        days_total=days_total,
        technologist=technologist,
        notes=notes,
        created_by=user,
        status=IncubationRun.Status.INCUBATING,
    )
    run.full_clean(exclude=None)
    run.save()

    # Переносим batch в incubator_block (всё ещё в модуле incubation)
    if batch.current_block_id != incubator_block.id:
        batch.current_block = incubator_block
        batch.save(update_fields=["current_block", "updated_at"])

    audit_log(
        organization=organization,
        module=module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=run,
        action_verb=(
            f"loaded {eggs_loaded} eggs from {batch.doc_number} "
            f"to incubator {incubator_block.code} · run {run.doc_number}"
        ),
    )

    return LoadEggsResult(run=run)
