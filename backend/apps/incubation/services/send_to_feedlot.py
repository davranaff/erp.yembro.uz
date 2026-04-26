"""
Сервис `send_chicks_to_feedlot` — перевод суточных цыплят из инкубации в откорм.

По образцу `apps/matochnik/services/send_to_incubation.py`.

Создаёт `InterModuleTransfer(incubation → feedlot)` в state=AWAITING_ACCEPTANCE
и сразу вызывает `accept_transfer` → POSTED.

После: batch.current_module = feedlot, закрывается старый BatchChainStep
инкубации, открывается новый в feedlot, создаются StockMovement/JE через 79.01.

Guards:
    - batch.origin_module.code == 'incubation'
    - batch.current_module.code == 'incubation'
    - batch.state == ACTIVE
    - batch.current_quantity > 0
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.modules.models import Module
from apps.transfers.models import InterModuleTransfer
from apps.transfers.services.accept import (
    accept_transfer,
    TransferAcceptError,
)
from apps.warehouses.models import Warehouse


class SendToFeedlotError(ValidationError):
    pass


@dataclass
class SendToFeedlotResult:
    transfer: InterModuleTransfer
    batch: Batch


@transaction.atomic
def send_chicks_to_feedlot(
    batch: Batch, *, user=None
) -> SendToFeedlotResult:
    batch = Batch.objects.select_for_update().get(pk=batch.pk)
    batch = Batch.objects.select_related(
        "organization", "origin_module", "current_module",
        "current_block", "nomenclature", "unit",
    ).get(pk=batch.pk)

    if not batch.origin_module or batch.origin_module.code != "incubation":
        raise SendToFeedlotError({"__all__": (
            f"Партия {batch.doc_number} не из инкубации "
            f"(origin={batch.origin_module.code if batch.origin_module_id else 'None'})."
        )})

    if batch.state != Batch.State.ACTIVE:
        raise SendToFeedlotError({"state": (
            f"В откорм можно отправить только активную партию, текущий статус: "
            f"{batch.get_state_display()}."
        )})

    if batch.current_quantity is None or batch.current_quantity <= 0:
        raise SendToFeedlotError({"current_quantity": "Партия пуста — нечего отправлять."})

    if (
        batch.current_module_id
        and batch.current_module.code != "incubation"
    ):
        raise SendToFeedlotError({"current_module": (
            f"Партия уже в модуле {batch.current_module.code}, "
            f"повторная передача невозможна."
        )})

    try:
        feedlot_mod = Module.objects.get(code="feedlot")
    except Module.DoesNotExist as exc:
        raise SendToFeedlotError(
            {"__all__": "Модуль 'feedlot' не найден."}
        ) from exc

    incubation_mod = batch.origin_module

    # Склады обоих модулей — берём первый активный.
    from_wh = (
        Warehouse.objects
        .filter(organization=batch.organization, module=incubation_mod, is_active=True)
        .order_by("code")
        .first()
    )
    to_wh = (
        Warehouse.objects
        .filter(organization=batch.organization, module=feedlot_mod, is_active=True)
        .order_by("code")
        .first()
    )
    if from_wh is None:
        raise SendToFeedlotError({"__all__": (
            "Не найден активный склад модуля 'incubation'. Создайте его в разделе Склады."
        )})
    if to_wh is None:
        raise SendToFeedlotError({"__all__": (
            "Не найден активный склад модуля 'feedlot'. Создайте его в разделе Склады."
        )})

    doc_number = next_doc_number(
        InterModuleTransfer,
        organization=batch.organization,
        prefix="ММ",
    )

    transfer = InterModuleTransfer(
        organization=batch.organization,
        doc_number=doc_number,
        transfer_date=datetime.now(timezone.utc),
        from_module=incubation_mod,
        to_module=feedlot_mod,
        from_block=batch.current_block,
        to_block=None,  # feedlot определит сам
        from_warehouse=from_wh,
        to_warehouse=to_wh,
        nomenclature=batch.nomenclature,
        unit=batch.unit,
        quantity=batch.current_quantity,
        cost_uzs=batch.accumulated_cost_uzs or Decimal("0"),
        batch=batch,
        feed_batch=None,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
        notes=f"Передача цыплят {batch.doc_number} в откорм.",
        created_by=user,
    )
    transfer.full_clean(exclude=None)
    transfer.save()

    try:
        accept_transfer(transfer, user=user)
    except TransferAcceptError as exc:
        raise SendToFeedlotError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc

    transfer.refresh_from_db()
    batch.refresh_from_db()

    audit_log(
        organization=batch.organization,
        module=incubation_mod,
        actor=user,
        action=AuditLog.Action.POST,
        entity=batch,
        action_verb=(
            f"chicks {batch.doc_number} sent to feedlot · transfer {transfer.doc_number}"
        ),
    )

    return SendToFeedlotResult(transfer=transfer, batch=batch)
