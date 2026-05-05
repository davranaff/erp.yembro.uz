"""
Связка RawMaterialBatch ↔ StockMovement.

Партия сырья — это «обогащённое» поступление: помимо самого факта прихода
на склад (StockMovement INCOMING) она хранит брутто-вес, влажность, расчёт
по Дювалю, карантин и FIFO-остаток для замеса.

До этого модуля партия и журнал жили параллельно: можно было создать
RawMaterialBatch и не получить запись в /stock, либо наоборот — создать
StockMovement INCOMING и не получить партию для замеса.

Здесь два сервиса:

1. ``create_movement_for_raw_batch`` — вызывается из view'ы при создании
   партии. Создаёт привязанный StockMovement INCOMING (через
   ``source_content_type/source_object_id``) — журнал и партия остаются
   в синхронизации.

2. ``promote_movement_to_raw_batch`` — берёт уже созданный manual-INCOMING
   StockMovement (например, юзер ввёл «приход» в /stock без полей сырья),
   создаёт RawMaterialBatch и **перепривязывает** существующий movement к
   ней. Без дублей в журнале.
"""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import RawMaterialBatch


class RawBatchPromoteError(ValidationError):
    pass


def _date_to_dt(d):
    """`received_date` (date) → datetime в начале дня (UTC)."""
    if isinstance(d, datetime):
        return d
    return datetime.combine(d, time.min, tzinfo=timezone.get_current_timezone())


def create_movement_for_raw_batch(batch: RawMaterialBatch, *, user=None) -> StockMovement:
    """
    Создать привязанный StockMovement INCOMING для свежесозданной партии.

    Используется в RawMaterialBatchViewSet.perform_create — гарантирует,
    что любое поступление сырья отражается в общем журнале склада.

    Если для этой партии уже есть привязанный movement — возвращает его
    (idempotent), не создавая дубль.
    """
    ct = ContentType.objects.get_for_model(RawMaterialBatch)
    existing = StockMovement.objects.filter(
        source_content_type=ct, source_object_id=batch.id,
        kind=StockMovement.Kind.INCOMING,
    ).first()
    if existing is not None:
        return existing

    qty = Decimal(batch.quantity)
    price = Decimal(batch.price_per_unit_uzs)
    when = _date_to_dt(batch.received_date)
    doc_number = next_doc_number(
        StockMovement, organization=batch.organization,
        prefix="СД", on_date=when.date(),
    )
    movement = StockMovement(
        organization=batch.organization,
        module=batch.module,
        doc_number=doc_number,
        kind=StockMovement.Kind.INCOMING,
        date=when,
        nomenclature=batch.nomenclature,
        quantity=qty,
        unit_price_uzs=price,
        amount_uzs=(qty * price).quantize(Decimal("0.01")),
        warehouse_from=None,
        warehouse_to=batch.warehouse,
        counterparty=batch.supplier,
        source_content_type=ct,
        source_object_id=batch.id,
        created_by=user,
    )
    movement.full_clean(exclude=None)
    movement.save()
    return movement


@transaction.atomic
def promote_movement_to_raw_batch(
    movement: StockMovement,
    *,
    moisture_pct_actual: Optional[Decimal] = None,
    dockage_pct_actual: Optional[Decimal] = None,
    shrinkage_pct: Optional[Decimal] = None,
    quarantine_until=None,
    supplier=None,
    storage_bin: str = "",
    notes: str = "",
    user=None,
) -> RawMaterialBatch:
    """
    Превратить ручной INCOMING-движение в RawMaterialBatch.

    Гварды:
        - movement.kind == INCOMING
        - movement не должен быть уже привязан к источнику (manual)
        - Номенклатура должна принадлежать модулю «feed» (по category.module)

    Действия:
        1. Создать RawMaterialBatch с тем же организацией / номенклатурой /
           количеством / ценой / складом / датой что у movement.
        2. Перепривязать движение к новой партии: source_content_type =
           RawMaterialBatch, source_object_id = batch.id. Кол-во и сумму
           НЕ трогаем — они уже корректны и попали в остатки склада.
        3. Не создаём новый StockMovement — иначе будет дубль.

    Возвращает созданную RawMaterialBatch.
    """
    from apps.modules.models import Module

    if movement.kind != StockMovement.Kind.INCOMING:
        raise RawBatchPromoteError(
            {"__all__": "Превратить в партию можно только Приход (INCOMING)."}
        )
    if movement.source_content_type_id is not None or movement.source_object_id is not None:
        raise RawBatchPromoteError(
            {"__all__": (
                "Это движение уже привязано к документу-источнику и не может "
                "быть превращено в партию."
            )}
        )
    if movement.warehouse_to_id is None:
        raise RawBatchPromoteError(
            {"__all__": "У движения нет склада-получателя (warehouse_to)."}
        )

    nom = movement.nomenclature
    cat = nom.category
    if cat.module is None or cat.module.code != "feed":
        raise RawBatchPromoteError(
            {"nomenclature": (
                "Превратить в партию можно только сырьё модуля «Корма» "
                "(категория должна быть привязана к feed)."
            )}
        )

    org = movement.organization
    feed_module = Module.objects.get(code="feed")

    qty = Decimal(movement.quantity)
    price = Decimal(movement.unit_price_uzs)
    received_date = movement.date.date() if hasattr(movement.date, "date") else movement.date

    base_moisture = nom.base_moisture_pct  # snapshot из NomenclatureItem на момент промоушна

    # Если шринкадж не передан — settlement = quantity (приёмка как есть).
    final_quantity = qty
    if shrinkage_pct is not None and shrinkage_pct > 0:
        final_quantity = (qty * (Decimal(1) - Decimal(shrinkage_pct) / Decimal(100))).quantize(
            Decimal("0.001"),
        )

    doc_number = next_doc_number(
        RawMaterialBatch, organization=org, prefix="СЫР",
        on_date=received_date,
    )

    # status: если есть quarantine_until → QUARANTINE, иначе AVAILABLE
    status = (
        RawMaterialBatch.Status.QUARANTINE
        if quarantine_until is not None
        else RawMaterialBatch.Status.AVAILABLE
    )

    batch = RawMaterialBatch(
        organization=org,
        module=feed_module,
        doc_number=doc_number,
        nomenclature=nom,
        supplier=supplier or movement.counterparty,
        warehouse=movement.warehouse_to,
        received_date=received_date,
        storage_bin=storage_bin,
        quantity=final_quantity,
        current_quantity=final_quantity,
        gross_weight_kg=qty,
        settlement_weight_kg=final_quantity,
        moisture_pct_actual=moisture_pct_actual,
        moisture_pct_base=base_moisture,
        dockage_pct_actual=dockage_pct_actual,
        shrinkage_pct=shrinkage_pct,
        unit=nom.unit,
        price_per_unit_uzs=price,
        status=status,
        quarantine_until=quarantine_until,
        notes=notes,
        created_by=user,
    )
    batch.full_clean(exclude=None)
    batch.save()

    # Перепривязка существующего movement
    movement.source_content_type = ContentType.objects.get_for_model(RawMaterialBatch)
    movement.source_object_id = batch.id
    movement.save(update_fields=["source_content_type", "source_object_id", "updated_at"])

    return batch
