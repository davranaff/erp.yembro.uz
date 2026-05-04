"""
Сервис `place_feedlot_batch` — создать FeedlotBatch для партии цыплят,
поступившей из инкубации (через accept_transfer) и стоящей на складе
модуля feedlot.

НЕ создаёт/не двигает Batch — это уже сделал accept_transfer. FeedlotBatch
это операционная надстройка над Batch: привязывает партию к конкретному
птичнику, отслеживает поголовье, кормление, падёж до отгрузки на убой.

Atomic:
    1. Guards:
       - batch.current_module == feedlot (ожидаем, что партия уже в модуле)
       - batch.current_quantity > 0
       - house_block: kind=FEEDLOT, same org, same module
       - initial_heads > 0 и <= batch.current_quantity
       - нет активного FeedlotBatch для этой batch
    2. Создать FeedlotBatch (status=PLACED).
       current_heads = initial_heads (по умолчанию = batch.current_quantity)
    3. Опц. обновить batch.current_block = house_block.
    4. AuditLog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import ProductionBlock

from ..models import FeedlotBatch


class FeedlotPlaceError(ValidationError):
    pass


@dataclass
class FeedlotPlaceResult:
    feedlot_batch: FeedlotBatch
    batch: Batch


@transaction.atomic
def place_feedlot_batch(
    batch: Batch,
    *,
    house_block: ProductionBlock,
    placed_date: date_type,
    technologist,
    initial_heads: Optional[int] = None,
    target_weight_kg: Optional[Decimal] = None,
    target_slaughter_date: Optional[date_type] = None,
    doc_number: Optional[str] = None,
    notes: str = "",
    user=None,
) -> FeedlotPlaceResult:
    batch = Batch.objects.select_for_update().get(pk=batch.pk)
    batch = Batch.objects.select_related(
        "organization", "current_module", "current_block", "nomenclature", "unit",
    ).get(pk=batch.pk)

    org = batch.organization
    if batch.current_module is None or batch.current_module.code != "feedlot":
        raise FeedlotPlaceError(
            {"batch": (
                f"Партия {batch.doc_number} сейчас не в модуле feedlot "
                f"(текущий: {batch.current_module.code if batch.current_module_id else 'none'})."
            )}
        )
    if batch.current_quantity <= 0:
        raise FeedlotPlaceError(
            {"batch": f"Партия {batch.doc_number} уже пуста."}
        )

    if house_block.organization_id != org.id:
        raise FeedlotPlaceError(
            {"house_block": "Птичник из другой организации."}
        )
    if house_block.module_id != batch.current_module_id:
        raise FeedlotPlaceError(
            {"house_block": "Птичник не принадлежит модулю откорма."}
        )
    if house_block.kind != ProductionBlock.Kind.FEEDLOT:
        raise FeedlotPlaceError(
            {"house_block": "Блок должен быть типа «Птичник откорма»."}
        )

    heads = initial_heads if initial_heads is not None else int(batch.current_quantity)
    if heads <= 0:
        raise FeedlotPlaceError(
            {"initial_heads": "Поголовье должно быть > 0."}
        )
    if Decimal(heads) > batch.current_quantity:
        raise FeedlotPlaceError(
            {"initial_heads": (
                f"Поголовье {heads} > остатка партии {batch.current_quantity}."
            )}
        )

    if FeedlotBatch.objects.filter(
        batch=batch,
        status__in=[
            FeedlotBatch.Status.PLACED,
            FeedlotBatch.Status.GROWING,
            FeedlotBatch.Status.READY_SLAUGHTER,
        ],
    ).exists():
        raise FeedlotPlaceError(
            {"batch": "У этой партии уже есть активное размещение на откорме."}
        )

    if technologist is None:
        raise FeedlotPlaceError({"technologist": "Технолог обязателен."})

    number = doc_number or next_doc_number(
        FeedlotBatch, organization=org, prefix="ФЛ", on_date=placed_date,
    )

    kwargs = dict(
        organization=org,
        module=batch.current_module,
        house_block=house_block,
        batch=batch,
        doc_number=number,
        placed_date=placed_date,
        initial_heads=heads,
        current_heads=heads,
        status=FeedlotBatch.Status.PLACED,
        technologist=technologist,
        notes=notes,
        created_by=user,
    )
    if target_weight_kg is not None:
        kwargs["target_weight_kg"] = target_weight_kg
    if target_slaughter_date is not None:
        kwargs["target_slaughter_date"] = target_slaughter_date

    fb = FeedlotBatch(**kwargs)
    fb.full_clean()
    fb.save()

    # Привязать partию к конкретному птичнику (current_block)
    if batch.current_block_id != house_block.id:
        batch.current_block = house_block
        batch.save(update_fields=["current_block", "updated_at"])

    audit_log(
        organization=org,
        module=batch.current_module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=fb,
        action_verb=(
            f"placed batch {batch.doc_number} in {house_block.code} "
            f"as {fb.doc_number} ({heads} гол)"
        ),
    )

    return FeedlotPlaceResult(feedlot_batch=fb, batch=batch)
