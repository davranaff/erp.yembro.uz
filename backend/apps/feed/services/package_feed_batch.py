"""
Сервис ``package_feed_batch`` — расфасовка партии комбикорма (FeedBatch)
в мешки (FeedBagLot).

Идея: насыпь и фасованные мешки — это две разные сущности учёта.
FeedBatch ведётся в кг (бункер замеса), FeedBagLot — в штуках мешков
(склад мешков). Между ними — явная операция фасовки, которая порождает
StockMovement OUT (kg) из источника + IN (kg) в склад мешков, а себестоимость
наследуется (per-kg → per-bag = × bag_weight_kg).

Что делает в atomic:
    1. Lock + guard: source.status == APPROVED, source.current_quantity_kg ≥
       bag_count × bag_weight_kg, целевой склад той же организации/модуля.
    2. Создать FeedBagLot:
         - bags_initial = bags_remaining = bag_count
         - unit_cost_uzs = source.unit_cost_uzs × bag_weight_kg
         - total_cost_uzs = unit_cost × bags_initial
         - is_medicated/withdrawal — наследуем
    3. Декремент source.current_quantity_kg на bag_count × bag_weight_kg.
       Если ушло в ноль — status = DEPLETED.
    4. StockMovement OUTGOING из source.storage_warehouse (kg).
    5. StockMovement INCOMING в bag_lot.storage_warehouse (kg, та же
       номенклатура — учётная единица не меняется, меняется только склад).
    6. Audit log.

Без JE: бухгалтерски это внутренний transfer между складами одной
организации, цена не меняется. Если позже захотим разделить субсчета
(10.05 «корм готовый» vs 10.06 «корм фасованный») — добавим JE здесь.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import FeedBagLot, FeedBatch


class FeedPackageError(ValidationError):
    pass


@dataclass
class FeedPackageResult:
    bag_lot: FeedBagLot
    source_feed_batch: FeedBatch
    stock_movements: list[StockMovement]


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _resolve_feed_nomenclature(feed_batch: FeedBatch):
    """Та же логика, что в execute_task — резолв через recipe.code."""
    from apps.nomenclature.models import NomenclatureItem
    return NomenclatureItem.objects.filter(
        organization=feed_batch.organization_id,
        sku=feed_batch.recipe_version.recipe.code,
    ).first()


@transaction.atomic
def package_feed_batch(
    source: FeedBatch,
    *,
    bag_count: int,
    bag_weight_kg: Decimal,
    storage_warehouse,
    storage_bin=None,
    notes: str = "",
    user=None,
) -> FeedPackageResult:
    """
    Расфасовать часть (или весь) FeedBatch в N мешков по `bag_weight_kg`.

    Args:
        source: исходная партия комбикорма (status=APPROVED).
        bag_count: сколько мешков расфасовать (целое > 0).
        bag_weight_kg: вес одного мешка (кг, типично 50.000).
        storage_warehouse: склад мешков (Warehouse, модуля feed).
        storage_bin: опциональный ProductionBlock-бункер.
        notes: текстовая заметка.
        user: User для created_by/audit.

    Returns:
        FeedPackageResult с bag_lot и stock_movements.

    Raises:
        FeedPackageError: guards / cross-org / нехватка кг.
    """
    if not isinstance(bag_count, int) or bag_count <= 0:
        raise FeedPackageError({"bag_count": "Должно быть целое > 0."})
    bag_weight = Decimal(str(bag_weight_kg))
    if bag_weight <= 0:
        raise FeedPackageError({"bag_weight_kg": "Вес мешка должен быть > 0."})

    # 1. Lock source
    source = FeedBatch.objects.select_for_update().get(pk=source.pk)
    source = FeedBatch.objects.select_related(
        "organization", "module", "recipe_version", "recipe_version__recipe",
        "storage_warehouse",
    ).get(pk=source.pk)

    if source.status != FeedBatch.Status.APPROVED:
        raise FeedPackageError(
            {"status": (
                f"Фасовать можно только одобренные партии (текущий статус: "
                f"{source.get_status_display()}). Сначала проведите контроль "
                f"качества."
            )}
        )

    org = source.organization
    kg_to_consume = (Decimal(bag_count) * bag_weight).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP
    )
    if Decimal(source.current_quantity_kg) < kg_to_consume:
        raise FeedPackageError(
            {"bag_count": (
                f"Не хватает остатка партии {source.doc_number}: "
                f"требуется {kg_to_consume} кг "
                f"(={bag_count}×{bag_weight}), доступно "
                f"{source.current_quantity_kg} кг."
            )}
        )

    # 2. Validate destination warehouse
    if storage_warehouse.organization_id != org.id:
        raise FeedPackageError(
            {"storage_warehouse": "Склад из другой организации."}
        )
    if storage_warehouse.module_id != source.module_id:
        raise FeedPackageError(
            {"storage_warehouse": "Склад не принадлежит модулю «Корма»."}
        )
    if storage_bin is not None:
        if storage_bin.organization_id != org.id:
            raise FeedPackageError(
                {"storage_bin": "Бункер из другой организации."}
            )

    # 3. Compute costs (наследуем per-kg, в пересчёте на мешок)
    source_unit_cost = Decimal(source.unit_cost_uzs)  # сум/кг
    bag_unit_cost = _quantize_money(source_unit_cost * bag_weight)
    total_cost = _quantize_money(bag_unit_cost * Decimal(bag_count))

    now = timezone.now()
    entry_date = timezone.localdate(now)

    # 4. Generate bag-lot doc number: ФП-{YYYY}-{NNNNN}.
    # Не вшиваем recipe.code в номер (как делает execute_task для FeedBatch) —
    # next_doc_number сканирует строки по regex `{prefix}-{year}-N`, и при
    # custom-формате вторая фасовка возвращала бы тот же seq → unique conflict.
    bl_number = next_doc_number(
        FeedBagLot, organization=org, prefix="ФП", on_date=entry_date, width=5
    )

    bag_lot = FeedBagLot(
        organization=org,
        module=source.module,
        doc_number=bl_number,
        source_feed_batch=source,
        recipe_version=source.recipe_version,
        bag_weight_kg=bag_weight,
        bags_initial=bag_count,
        bags_remaining=bag_count,
        unit_cost_uzs=bag_unit_cost,
        total_cost_uzs=total_cost,
        storage_warehouse=storage_warehouse,
        storage_bin=storage_bin,
        packaged_at=now,
        is_medicated=source.is_medicated,
        withdrawal_period_days=source.withdrawal_period_days,
        withdrawal_period_ends=source.withdrawal_period_ends,
        status=FeedBagLot.Status.ACTIVE,
        notes=notes,
        created_by=user,
    )
    bag_lot.full_clean(exclude=None)
    bag_lot.save()

    # 5. Decrement source kg
    FeedBatch.objects.filter(pk=source.pk).update(
        current_quantity_kg=F("current_quantity_kg") - kg_to_consume
    )
    source.refresh_from_db(fields=["current_quantity_kg"])
    if (
        Decimal(source.current_quantity_kg) == 0
        and source.status == FeedBatch.Status.APPROVED
    ):
        source.status = FeedBatch.Status.DEPLETED
        source.save(update_fields=["status", "updated_at"])

    # 6. StockMovements (по nomenclature готового корма, в кг)
    feed_nom = _resolve_feed_nomenclature(source)
    stock_movements: list[StockMovement] = []

    if feed_nom is not None and source.storage_warehouse_id:
        # OUTGOING из склада-источника (бункер замеса)
        sm_out_number = next_doc_number(
            StockMovement, organization=org, prefix="СД", on_date=entry_date
        )
        sm_out = StockMovement(
            organization=org,
            module=source.module,
            doc_number=sm_out_number,
            kind=StockMovement.Kind.OUTGOING,
            date=now,
            nomenclature=feed_nom,
            quantity=kg_to_consume,
            unit_price_uzs=source_unit_cost.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            amount_uzs=_quantize_money(kg_to_consume * source_unit_cost),
            warehouse_from=source.storage_warehouse,
            warehouse_to=None,
            source_content_type=ContentType.objects.get_for_model(FeedBagLot),
            source_object_id=bag_lot.id,
            created_by=user,
        )
        sm_out.full_clean(exclude=None)
        sm_out.save()
        stock_movements.append(sm_out)

        # INCOMING на склад мешков (та же кг-масса, но «оприходовано как
        # фасованный корм» — отличается через source FK на FeedBagLot)
        sm_in_number = next_doc_number(
            StockMovement, organization=org, prefix="СД", on_date=entry_date
        )
        sm_in = StockMovement(
            organization=org,
            module=source.module,
            doc_number=sm_in_number,
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=feed_nom,
            quantity=kg_to_consume,
            unit_price_uzs=source_unit_cost.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            amount_uzs=_quantize_money(kg_to_consume * source_unit_cost),
            warehouse_from=None,
            warehouse_to=storage_warehouse,
            source_content_type=ContentType.objects.get_for_model(FeedBagLot),
            source_object_id=bag_lot.id,
            created_by=user,
        )
        sm_in.full_clean(exclude=None)
        sm_in.save()
        stock_movements.append(sm_in)

    # 7. Audit
    audit_log(
        organization=org,
        module=source.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=bag_lot,
        action_verb=(
            f"packaged {source.doc_number} → {bag_lot.doc_number} "
            f"({bag_count}×{bag_weight}кг = {kg_to_consume}кг)"
        ),
    )

    return FeedPackageResult(
        bag_lot=bag_lot,
        source_feed_batch=source,
        stock_movements=stock_movements,
    )
