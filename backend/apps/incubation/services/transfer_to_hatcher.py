"""
Сервис `transfer_to_hatcher` — перевод партии инкубации из инкубатора
на выводной шкаф (INCUBATING → HATCHING).

Не создаёт JE/SM — меняет только status и hatcher_block.
Собственно «вывод» и создание партии цыплят — отдельный сервис `hatch`.

Atomic:
    1. Guards:
       - run.status = INCUBATING (единственный валидный источник)
       - hatcher_block: kind = HATCHER, same org, same module
    2. run.hatcher_block = <block>
       run.status = HATCHING
    3. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.warehouses.models import ProductionBlock

from ..models import IncubationRun


class IncubationTransferError(ValidationError):
    pass


@dataclass
class TransferToHatcherResult:
    run: IncubationRun


@transaction.atomic
def transfer_to_hatcher(
    run: IncubationRun,
    *,
    hatcher_block: ProductionBlock,
    user=None,
) -> TransferToHatcherResult:
    run = IncubationRun.objects.select_for_update().get(pk=run.pk)

    if run.status != IncubationRun.Status.INCUBATING:
        raise IncubationTransferError(
            {"status": (
                f"Перевод на вывод возможен только из INCUBATING, "
                f"текущий: {run.get_status_display()}."
            )}
        )

    if hatcher_block.organization_id != run.organization_id:
        raise IncubationTransferError(
            {"hatcher_block": "Выводной шкаф из другой организации."}
        )
    if hatcher_block.module_id != run.module_id:
        raise IncubationTransferError(
            {"hatcher_block": "Выводной шкаф не принадлежит модулю инкубации."}
        )
    if hatcher_block.kind != ProductionBlock.Kind.HATCHER:
        raise IncubationTransferError(
            {"hatcher_block": "Блок должен быть типа «Выводной шкаф»."}
        )

    run.hatcher_block = hatcher_block
    run.status = IncubationRun.Status.HATCHING
    run.save(update_fields=["hatcher_block", "status", "updated_at"])

    audit_log(
        organization=run.organization,
        module=run.module,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=run,
        action_verb=f"transferred run {run.doc_number} to hatcher {hatcher_block.code}",
    )

    return TransferToHatcherResult(run=run)
