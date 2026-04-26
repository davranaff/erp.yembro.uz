"""
Сервис `ship_to_slaughter` — отгрузка партии откорма на убой.

Создаёт InterModuleTransfer (DRAFT → AWAITING_ACCEPTANCE) для передачи
poultry batch из модуля feedlot в модуль slaughter. Проверяет, что
партия не находится в периоде каренции (withdrawal_period_ends).

НЕ выполняет accept_transfer — это отдельное действие приёмщика
(SlaughterShift-foreman через `POST /api/transfers/{id}/accept/`).

Сам ship_to_slaughter — это помощник, который:
    1. Проверяет что batch.current_module = feedlot.
    2. Проверяет withdrawal (опционально — до transfer_date).
    3. Создаёт InterModuleTransfer DRAFT со всеми полями.
    4. Сразу submit → AWAITING_ACCEPTANCE.
    5. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.modules.models import Module
from apps.nomenclature.models import Unit
from apps.transfers.models import InterModuleTransfer
from apps.warehouses.models import ProductionBlock, Warehouse

from ..models import FeedlotBatch


class ShipToSlaughterError(ValidationError):
    pass


@dataclass
class ShipToSlaughterResult:
    transfer: InterModuleTransfer
    feedlot_batch: FeedlotBatch


@transaction.atomic
def ship_to_slaughter(
    feedlot_batch: FeedlotBatch,
    *,
    slaughter_line: ProductionBlock,
    slaughter_warehouse: Warehouse,
    source_warehouse: Warehouse,
    transfer_date=None,
    quantity: Optional[Decimal] = None,
    user=None,
) -> ShipToSlaughterResult:
    """
    Подготовить партию откорма к убою: создать ММ-передачу в статусе
    AWAITING_ACCEPTANCE. Убойщик дальше принимает её через accept_transfer.

    Args:
        feedlot_batch: FeedlotBatch в статусе GROWING/READY_SLAUGHTER.
        slaughter_line: ProductionBlock kind=slaughter_line.
        slaughter_warehouse: склад убойни (живая птица).
        source_warehouse: склад фабрики откорма (живая птица).
        transfer_date: default now().
        quantity: сколько голов. Default = feedlot_batch.current_heads.
    """
    feedlot_batch = FeedlotBatch.objects.select_for_update().get(pk=feedlot_batch.pk)
    feedlot_batch = FeedlotBatch.objects.select_related(
        "organization", "module", "house_block", "batch",
        "batch__current_module", "batch__nomenclature", "batch__unit",
    ).get(pk=feedlot_batch.pk)

    batch = feedlot_batch.batch
    org = feedlot_batch.organization

    if feedlot_batch.status not in (
        FeedlotBatch.Status.GROWING,
        FeedlotBatch.Status.READY_SLAUGHTER,
        FeedlotBatch.Status.PLACED,
    ):
        raise ShipToSlaughterError(
            {
                "status": (
                    f"Статус партии откорма {feedlot_batch.get_status_display()} "
                    f"не позволяет отгрузку."
                )
            }
        )

    if batch.current_module_id != feedlot_batch.module_id:
        raise ShipToSlaughterError(
            {"batch": "Партия сейчас не в модуле этой фабрики откорма."}
        )

    # Модуль убоя
    try:
        slaughter_module = Module.objects.get(code="slaughter")
    except Module.DoesNotExist as exc:
        raise ShipToSlaughterError(
            {"__all__": "Модуль 'slaughter' не найден."}
        ) from exc

    if slaughter_line.module_id != slaughter_module.id:
        raise ShipToSlaughterError(
            {"slaughter_line": "Линия не принадлежит модулю убоя."}
        )
    if slaughter_warehouse.module_id != slaughter_module.id:
        raise ShipToSlaughterError(
            {"slaughter_warehouse": "Склад не принадлежит модулю убоя."}
        )
    if source_warehouse.module_id != feedlot_batch.module_id:
        raise ShipToSlaughterError(
            {"source_warehouse": "Склад-источник не принадлежит модулю откорма."}
        )

    qty = Decimal(feedlot_batch.current_heads) if quantity is None else quantity
    if qty <= 0:
        raise ShipToSlaughterError({"quantity": "Количество должно быть > 0."})

    td = transfer_date or timezone.now()

    # Withdrawal-guard (до создания transfer; slaughter.clean() проверит ещё раз)
    if batch.withdrawal_period_ends:
        date_val = td.date() if hasattr(td, "date") else td
        if batch.withdrawal_period_ends > date_val:
            raise ShipToSlaughterError(
                {
                    "transfer_date": (
                        f"Партия {batch.doc_number}: срок каренции не истёк "
                        f"(до {batch.withdrawal_period_ends})."
                    )
                }
            )

    # Создать transfer
    doc_number = next_doc_number(
        InterModuleTransfer, organization=org, prefix="ММ",
        on_date=td.date() if hasattr(td, "date") else td,
    )
    transfer = InterModuleTransfer(
        organization=org,
        doc_number=doc_number,
        transfer_date=td,
        from_module=feedlot_batch.module,
        to_module=slaughter_module,
        from_block=feedlot_batch.house_block,
        to_block=slaughter_line,
        from_warehouse=source_warehouse,
        to_warehouse=slaughter_warehouse,
        nomenclature=batch.nomenclature,
        unit=batch.unit,
        quantity=qty,
        cost_uzs=batch.accumulated_cost_uzs,
        batch=batch,
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
        created_by=user,
    )
    transfer.full_clean(exclude=None)
    transfer.save()

    # Обновить статус feedlot_batch
    if feedlot_batch.status != FeedlotBatch.Status.SHIPPED:
        feedlot_batch.status = FeedlotBatch.Status.SHIPPED
        feedlot_batch.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=org,
        module=feedlot_batch.module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=transfer,
        action_verb=(
            f"shipped {feedlot_batch.doc_number} to slaughter "
            f"(batch {batch.doc_number}, {qty} гол)"
        ),
    )

    return ShipToSlaughterResult(
        transfer=transfer,
        feedlot_batch=feedlot_batch,
    )
