"""
Сервис `receive_vet_stock_batch` — приёмка партии ветпрепарата.

Создаёт VetStockBatch (status=QUARANTINE по умолчанию) с авто-сгенерированным
штрих-кодом, плюс привязанный StockMovement INCOMING (источник = VetStockBatch).
Без INCOMING остаток в журнале склада был отрицательный (только OUTGOING при
лечении/продаже) — формула balance = incoming − outgoing давала кашу.
Симметрично паттерну feed `create_movement_for_raw_batch` и
vet `receive_vet_accessory`.

Замечание про PurchaseOrder: confirm() закупа тоже создаёт INCOMING на
warehouse_to. Чтобы не словить двойной счёт по vet-лотам, штатный
flow таков: PurchaseOrder остаётся в DRAFT (служит audit-FK), а physical
receipt идёт через эту функцию. Тесты подтверждают что в проде PO.confirm
для vet не вызывается, а движений в журнале склада не было.

Плюс отдельный сервис `release_vet_stock_from_quarantine` — перевод
QUARANTINE → AVAILABLE после проверки (ветврач подтвердил, что лот
цел и стерилен).

Atomic:
    1. Guards: cross-org (drug, warehouse, supplier, purchase); quantity > 0;
       expiration_date > received_date; warehouse.module == vet;
       purchase обязателен (для compliance/audit).
    2. Генерация doc_number (ВП-YYYY-NNNNN).
    3. Авто-генерация barcode: `VET-{sku}-{lot}-{rand4}` уникален в рамках org.
    4. Create VetStockBatch со status=start_status (default QUARANTINE).
       current_quantity = quantity.
    5. Create StockMovement(kind=INCOMING, warehouse_to=warehouse,
       source=VetStockBatch). Idempotent — если для этого лота уже есть
       привязанный INCOMING, не дублируем.
    6. AuditLog.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Unit
from apps.purchases.models import PurchaseOrder
from apps.warehouses.models import StockMovement, Warehouse

from ..models import VetDrug, VetStockBatch


class VetStockReceiveError(ValidationError):
    pass


@dataclass
class VetStockReceiveResult:
    stock_batch: VetStockBatch
    stock_movement: StockMovement


@transaction.atomic
def receive_vet_stock_batch(
    *,
    organization,
    drug: VetDrug,
    lot_number: str,
    warehouse: Warehouse,
    supplier: Counterparty,
    received_date: date_type,
    expiration_date: date_type,
    quantity: Decimal,
    unit: Unit,
    price_per_unit_uzs: Decimal,
    purchase: Optional[PurchaseOrder] = None,
    quarantine_until: Optional[date_type] = None,
    start_status: str = VetStockBatch.Status.QUARANTINE,
    doc_number: Optional[str] = None,
    barcode: Optional[str] = None,
    notes: str = "",
    user=None,
) -> VetStockReceiveResult:
    if quantity <= 0:
        raise VetStockReceiveError({"quantity": "Должно быть > 0."})
    if expiration_date < received_date:
        raise VetStockReceiveError(
            {"expiration_date": "Срок годности раньше даты приёмки."}
        )
    if purchase is None:
        raise VetStockReceiveError(
            {"purchase": (
                "Укажите PurchaseOrder — закуп обязателен для compliance/audit. "
                "Если препарат поступил без закупа, создайте сначала PurchaseOrder."
            )}
        )

    if drug.organization_id != organization.id:
        raise VetStockReceiveError({"drug": "Препарат из другой организации."})
    if warehouse.organization_id != organization.id:
        raise VetStockReceiveError({"warehouse": "Склад из другой организации."})
    if supplier.organization_id != organization.id:
        raise VetStockReceiveError({"supplier": "Поставщик из другой организации."})
    if purchase.organization_id != organization.id:
        raise VetStockReceiveError({"purchase": "Закуп из другой организации."})

    try:
        vet_module = Module.objects.get(code="vet")
    except Module.DoesNotExist as exc:
        raise VetStockReceiveError(
            {"__all__": "Модуль 'vet' не найден."}
        ) from exc

    if warehouse.module_id != vet_module.id:
        raise VetStockReceiveError(
            {"warehouse": "Склад не принадлежит модулю ветеринарии."}
        )

    number = doc_number or next_doc_number(
        VetStockBatch, organization=organization, prefix="ВП",
        on_date=received_date,
    )

    # Авто-генерация штрих-кода если не задан явно.
    # Формат: VET-<SKU>-<LOT>-<RAND4>. Уникален в рамках организации.
    if not barcode:
        sku = drug.nomenclature.sku.upper().replace(" ", "")
        lot = lot_number.upper().replace(" ", "")
        # Защита от коллизии: 3 попытки сгенерировать
        for _ in range(3):
            candidate = f"VET-{sku}-{lot}-{secrets.token_hex(2).upper()}"
            if not VetStockBatch.objects.filter(
                organization=organization, barcode=candidate,
            ).exists():
                barcode = candidate
                break
        else:
            raise VetStockReceiveError(
                {"barcode": "Не удалось сгенерировать уникальный barcode."}
            )

    sb = VetStockBatch(
        organization=organization,
        module=vet_module,
        doc_number=number,
        drug=drug,
        lot_number=lot_number,
        warehouse=warehouse,
        supplier=supplier,
        purchase=purchase,
        received_date=received_date,
        expiration_date=expiration_date,
        quantity=quantity,
        current_quantity=quantity,
        unit=unit,
        price_per_unit_uzs=price_per_unit_uzs,
        status=start_status,
        quarantine_until=quarantine_until,
        barcode=barcode,
        notes=notes,
        created_by=user,
    )
    sb.full_clean()
    sb.save()

    sm = _create_incoming_movement_for_lot(sb, user=user)

    audit_log(
        organization=organization,
        module=vet_module,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=sb,
        action_verb=(
            f"received vet stock {sb.doc_number} lot {lot_number} "
            f"({quantity} {unit.code} of {drug.nomenclature.sku})"
        ),
    )

    return VetStockReceiveResult(stock_batch=sb, stock_movement=sm)


def _create_incoming_movement_for_lot(
    batch: VetStockBatch, *, user=None,
) -> StockMovement:
    """
    Создать привязанный StockMovement INCOMING для лота препарата.

    Idempotent: если для этой VetStockBatch уже есть INCOMING (предыдущий
    запуск, или лот создан старым кодом и потом перепринят) — возвращаем
    существующий без создания дубля.
    """
    ct = ContentType.objects.get_for_model(VetStockBatch)
    existing = StockMovement.objects.filter(
        source_content_type=ct, source_object_id=batch.id,
        kind=StockMovement.Kind.INCOMING,
    ).first()
    if existing is not None:
        return existing

    qty = Decimal(batch.quantity).quantize(Decimal("0.001"))
    price = Decimal(batch.price_per_unit_uzs)
    amount = (qty * price).quantize(Decimal("0.01"))

    sm_number = next_doc_number(
        StockMovement, organization=batch.organization,
        prefix="СД", on_date=batch.received_date,
    )

    sm = StockMovement(
        organization=batch.organization,
        module=batch.module,
        doc_number=sm_number,
        kind=StockMovement.Kind.INCOMING,
        date=timezone.now(),
        nomenclature=batch.drug.nomenclature,
        quantity=qty,
        unit_price_uzs=price,
        amount_uzs=amount,
        warehouse_from=None,
        warehouse_to=batch.warehouse,
        counterparty=batch.supplier,
        source_content_type=ct,
        source_object_id=batch.id,
        created_by=user,
    )
    sm.full_clean(exclude=None)
    sm.save()
    return sm


@transaction.atomic
def release_vet_stock_from_quarantine(
    stock_batch: VetStockBatch,
    *,
    user=None,
) -> VetStockBatch:
    """Перевод лота QUARANTINE → AVAILABLE (ветврач подтвердил)."""
    stock_batch = VetStockBatch.objects.select_for_update().get(pk=stock_batch.pk)

    if stock_batch.status != VetStockBatch.Status.QUARANTINE:
        raise VetStockReceiveError(
            {"status": (
                f"Релиз возможен только из QUARANTINE, текущий: "
                f"{stock_batch.get_status_display()}."
            )}
        )

    stock_batch.status = VetStockBatch.Status.AVAILABLE
    stock_batch.save(update_fields=["status", "updated_at"])

    audit_log(
        organization=stock_batch.organization,
        module=stock_batch.module,
        actor=user,
        action=AuditLog.Action.UPDATE,
        entity=stock_batch,
        action_verb=f"released vet stock {stock_batch.doc_number} from quarantine",
    )
    return stock_batch
