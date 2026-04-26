"""
Сервис `send_eggs_to_incubation` — переместить партию яиц из маточника
в инкубацию за один клик.

Создаёт `InterModuleTransfer` (matochnik → incubation) в состоянии
AWAITING_ACCEPTANCE и сразу вызывает `accept_transfer`, который делает:
  - Парные StockMovement / JournalEntry (Dr 79.01 / Cr 10.02, ...).
  - Закрытие BatchChainStep маточника, открытие нового в инкубации.
  - Обновление Batch.current_module=incubation.

Guards:
  - batch.origin_module.code == 'matochnik'
  - batch.current_module is None OR 'matochnik' (партия ещё в маточнике)
  - batch.state == 'active'
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


class SendToIncubationError(ValidationError):
    pass


@dataclass
class SendToIncubationResult:
    transfer: InterModuleTransfer
    batch: Batch


@transaction.atomic
def send_eggs_to_incubation(
    batch: Batch, *, user=None
) -> SendToIncubationResult:
    # Row-lock
    batch = Batch.objects.select_for_update().get(pk=batch.pk)
    batch = Batch.objects.select_related(
        "organization", "origin_module", "current_module",
        "current_block", "nomenclature", "unit",
    ).get(pk=batch.pk)

    # Guards
    if batch.origin_module.code != "matochnik":
        raise SendToIncubationError(
            {"__all__": (
                f"Партия {batch.doc_number} не из маточника "
                f"(origin={batch.origin_module.code})."
            )}
        )

    if batch.state != Batch.State.ACTIVE:
        raise SendToIncubationError(
            {"state": (
                f"В инкубацию можно отправить только активную партию, "
                f"текущий статус: {batch.get_state_display()}."
            )}
        )

    if batch.current_quantity is None or batch.current_quantity <= 0:
        raise SendToIncubationError(
            {"current_quantity": "Партия пуста — нечего отправлять."}
        )

    if (
        batch.current_module_id
        and batch.current_module.code != "matochnik"
    ):
        raise SendToIncubationError(
            {"current_module": (
                f"Партия уже в модуле {batch.current_module.code}, "
                f"повторная передача невозможна."
            )}
        )

    try:
        incubation_mod = Module.objects.get(code="incubation")
    except Module.DoesNotExist as exc:
        raise SendToIncubationError(
            {"__all__": "Модуль 'incubation' не найден — seed миграция отсутствует."}
        ) from exc

    matochnik_mod = batch.origin_module  # уже matochnik

    # Нужны warehouse-ы для StockMovement (accept_transfer).
    from_wh = (
        Warehouse.objects
        .filter(organization=batch.organization, module=matochnik_mod, is_active=True)
        .order_by("code")
        .first()
    )
    to_wh = (
        Warehouse.objects
        .filter(organization=batch.organization, module=incubation_mod, is_active=True)
        .order_by("code")
        .first()
    )
    if from_wh is None:
        raise SendToIncubationError(
            {"__all__": (
                "Не найден активный склад модуля 'matochnik'. "
                "Создайте его в разделе Склады."
            )}
        )
    if to_wh is None:
        raise SendToIncubationError(
            {"__all__": (
                "Не найден активный склад модуля 'incubation'. "
                "Создайте его в разделе Склады."
            )}
        )

    # Генерация doc_number
    doc_number = next_doc_number(
        InterModuleTransfer,
        organization=batch.organization,
        prefix="ММ",
    )

    # Создаём transfer в AWAITING_ACCEPTANCE, чтобы accept_transfer принял.
    transfer = InterModuleTransfer(
        organization=batch.organization,
        doc_number=doc_number,
        transfer_date=datetime.now(timezone.utc),
        from_module=matochnik_mod,
        to_module=incubation_mod,
        from_block=batch.current_block,
        to_block=None,  # инкубация сама определит
        from_warehouse=from_wh,
        to_warehouse=to_wh,
        nomenclature=batch.nomenclature,
        unit=batch.unit,
        quantity=batch.current_quantity,
        cost_uzs=batch.accumulated_cost_uzs or Decimal("0"),
        batch=batch,
        feed_batch=None,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
        notes=f"Передача яиц {batch.doc_number} в инкубацию.",
        created_by=user,
    )
    transfer.full_clean(exclude=None)
    transfer.save()

    # Сразу проводим
    try:
        accept_transfer(transfer, user=user)
    except TransferAcceptError as exc:
        # Переупаковываем в нашу ошибку чтобы не ломать API-контракт
        raise SendToIncubationError(
            exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        ) from exc

    transfer.refresh_from_db()
    batch.refresh_from_db()

    audit_log(
        organization=batch.organization,
        module=matochnik_mod,
        actor=user,
        action=AuditLog.Action.POST,
        entity=batch,
        action_verb=(
            f"eggs {batch.doc_number} sent to incubation · "
            f"transfer {transfer.doc_number}"
        ),
    )

    return SendToIncubationResult(transfer=transfer, batch=batch)
