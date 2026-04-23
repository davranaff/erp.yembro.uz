from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from app.core.exceptions import ValidationError
from app.repositories.finance import SupplierDebtRepository
from app.repositories.inventory import StockMovementRepository
from app.repositories.medicine import (
    MedicineBatchRepository,
    MedicineConsumptionRepository,
    MedicineTypeRepository,
)
from app.schemas.medicine import (
    MedicineBatchReadSchema,
    MedicineConsumptionReadSchema,
    MedicineTypeReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft
from app.services.units import resolve_measurement_unit_id


AUTO_MEDICINE_ARRIVAL_AP_MARKER_PREFIX = "[auto-medicine-arrival-ap:"


def _build_auto_ap_marker(batch_id: str) -> str:
    return f"{AUTO_MEDICINE_ARRIVAL_AP_MARKER_PREFIX}{batch_id}]"


def _compose_auto_debt_note(marker: str, source_note: Any) -> str:
    note_text = str(source_note).strip() if source_note is not None else ""
    if not note_text:
        return marker
    if marker in note_text:
        return note_text
    return f"{note_text}\n{marker}"


def _resolve_auto_debt_status(amount_total: Decimal, amount_paid: Decimal) -> str:
    if amount_paid <= Decimal("0"):
        return "open"
    if amount_paid >= amount_total:
        return "closed"
    return "partially_paid"


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0)).quantize(Decimal("0.001"))


def _medicine_key(batch_id: str) -> str:
    return f"medicine_batch:{batch_id}"


class MedicineBatchService(BaseService):
    read_schema = MedicineBatchReadSchema

    def __init__(self, repository: MedicineBatchRepository) -> None:
        super().__init__(repository=repository)

    async def _consumed_quantity(self, batch_id: str) -> Decimal:
        row = await self.repository.db.fetchval(
            "SELECT COALESCE(SUM(quantity), 0) FROM medicine_consumptions WHERE batch_id = $1",
            batch_id,
        )
        return Decimal(str(row or 0))

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        received_quantity = _as_decimal(next_data.get("received_quantity"))
        next_data["received_quantity"] = str(received_quantity)
        next_data["remaining_quantity"] = str(received_quantity)
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        next_data.pop("remaining_quantity", None)
        new_received = _as_decimal(next_data.get("received_quantity", existing.get("received_quantity")))
        consumed = await self._consumed_quantity(str(entity_id))
        if new_received < consumed:
            raise ValidationError(
                "received_quantity cannot be less than already-consumed quantity",
            )
        next_data["received_quantity"] = str(new_received)
        next_data["remaining_quantity"] = str(
            (new_received - consumed).quantize(Decimal("0.001"))
        )
        return next_data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        received_quantity = _as_decimal(entity.get("received_quantity"))
        movement_rows: list[StockMovementDraft] = []
        if received_quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=_medicine_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=received_quantity,
                    unit=str(entity.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="medicine_batches",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("batch_code")) if entity.get("batch_code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_batches",
            reference_id=str(entity["id"]),
            movements=movement_rows,
        )

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="medicine_batches",
            reference_id=str(deleted_entity["id"]),
        )


class MedicineTypeService(BaseService):
    read_schema = MedicineTypeReadSchema

    def __init__(self, repository: MedicineTypeRepository) -> None:
        super().__init__(repository=repository)


class MedicineConsumptionService(CreatedByActorMixin, BaseService):
    read_schema = MedicineConsumptionReadSchema

    def __init__(self, repository: MedicineConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _get_batch_or_raise(self, batch_id: str) -> Mapping[str, Any]:
        batch = await MedicineBatchRepository(self.repository.db).get_by_id_optional(batch_id)
        if batch is None:
            raise ValidationError("batch_id is invalid")
        return batch

    async def _validate_factory_flock(
        self,
        flock_id: str,
        *,
        organization_id: str,
    ) -> None:
        row = await self.repository.db.fetchrow(
            "SELECT organization_id FROM factory_flocks WHERE id = $1",
            flock_id,
        )
        if row is None:
            raise ValidationError("factory_flock_id is invalid")
        if str(row["organization_id"]) != str(organization_id):
            raise ValidationError("factory_flock belongs to a different organization")

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        batch_id = next_data.get("batch_id")
        if batch_id is None:
            raise ValidationError("batch_id is required")
        batch = await self._get_batch_or_raise(str(batch_id))

        if str(batch["organization_id"]) != str(next_data.get("organization_id") or batch["organization_id"]):
            raise ValidationError("batch belongs to a different organization")
        next_data["organization_id"] = str(batch["organization_id"])

        department_raw = next_data.get("department_id")
        if department_raw is None or str(department_raw).strip() == "":
            next_data["department_id"] = str(batch["department_id"])
        elif str(department_raw) != str(batch["department_id"]):
            raise ValidationError("department_id must match the batch department")

        quantity = _as_decimal(next_data.get("quantity"))
        if quantity <= 0:
            raise ValidationError("quantity must be positive")
        batch_remaining = _as_decimal(batch.get("remaining_quantity"))
        if quantity > batch_remaining:
            raise ValidationError(
                "quantity exceeds batch remaining_quantity",
            )
        next_data["quantity"] = str(quantity)
        next_data["unit"] = str(next_data.get("unit") or batch.get("unit") or "pcs")

        flock_raw = next_data.get("factory_flock_id")
        if flock_raw is not None and str(flock_raw).strip() != "":
            await self._validate_factory_flock(
                str(flock_raw),
                organization_id=str(batch["organization_id"]),
            )
            next_data["factory_flock_id"] = str(flock_raw)
        else:
            next_data["factory_flock_id"] = None
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        target_batch_id = str(next_data.get("batch_id") or existing["batch_id"])
        batch = await self._get_batch_or_raise(target_batch_id)

        if "organization_id" in next_data and str(next_data["organization_id"]) != str(batch["organization_id"]):
            raise ValidationError("organization_id must match the batch organization")
        next_data["organization_id"] = str(batch["organization_id"])

        if "department_id" in next_data and str(next_data["department_id"]) != str(batch["department_id"]):
            raise ValidationError("department_id must match the batch department")

        if "quantity" in next_data:
            quantity = _as_decimal(next_data["quantity"])
            if quantity <= 0:
                raise ValidationError("quantity must be positive")
            existing_qty = _as_decimal(existing.get("quantity"))
            batch_remaining = _as_decimal(batch.get("remaining_quantity"))
            same_batch = str(existing.get("batch_id")) == target_batch_id
            delta = (quantity - existing_qty) if same_batch else quantity
            if delta > batch_remaining:
                raise ValidationError(
                    "quantity exceeds batch remaining_quantity",
                )
            next_data["quantity"] = str(quantity)

        if "unit" in next_data and next_data["unit"]:
            next_data["unit"] = str(next_data["unit"])

        if "factory_flock_id" in next_data:
            flock_raw = next_data.get("factory_flock_id")
            if flock_raw is None or str(flock_raw).strip() == "":
                next_data["factory_flock_id"] = None
            else:
                await self._validate_factory_flock(
                    str(flock_raw),
                    organization_id=str(batch["organization_id"]),
                )
                next_data["factory_flock_id"] = str(flock_raw)
        return next_data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        batch = await self._get_batch_or_raise(str(entity["batch_id"]))
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=_medicine_key(str(entity["batch_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or batch.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="medicine_consumptions",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(batch["warehouse_id"]) if batch.get("warehouse_id") else None,
                    note=(
                        str(entity.get("purpose"))
                        if entity.get("purpose") is not None
                        else None
                    ),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_consumptions",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _recalc_batch_remaining(self, batch_id: str) -> None:
        """Держит medicine_batches.remaining_quantity в синхроне с реальным
        расходом. До этой фикса колонка оставалась равной received_quantity
        навсегда, из-за чего проверка «quantity > batch_remaining» была
        фикцией и позволяла расходовать больше, чем есть."""
        await self.repository.db.execute(
            """
            UPDATE medicine_batches
            SET remaining_quantity = GREATEST(
                received_quantity - COALESCE((
                    SELECT SUM(quantity)
                    FROM medicine_consumptions
                    WHERE batch_id = $1
                ), 0),
                0
            ),
            updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            batch_id,
        )

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)
        await self._recalc_batch_remaining(str(entity["batch_id"]))

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)
        await self._recalc_batch_remaining(str(after["batch_id"]))
        if str(before.get("batch_id")) != str(after.get("batch_id")):
            await self._recalc_batch_remaining(str(before["batch_id"]))

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="medicine_consumptions",
            reference_id=str(deleted_entity["id"]),
        )
        await self._recalc_batch_remaining(str(deleted_entity["batch_id"]))


__all__ = [
    "MedicineBatchService",
    "MedicineTypeService",
    "MedicineConsumptionService",
]
