from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.inventory import StockMovementRepository
from app.repositories.medicine import (
    MedicineBatchRepository,
    MedicineTypeRepository,
)
from app.schemas.medicine import (
    MedicineBatchReadSchema,
    MedicineTypeReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft


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

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        received_quantity = _as_decimal(next_data.get("received_quantity"))
        remaining_quantity = (
            _as_decimal(next_data.get("remaining_quantity"))
            if next_data.get("remaining_quantity") is not None
            else received_quantity
        )
        if remaining_quantity > received_quantity:
            raise ValidationError("remaining_quantity cannot be greater than received_quantity")
        next_data["received_quantity"] = str(received_quantity)
        next_data["remaining_quantity"] = str(remaining_quantity)
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
        new_received = _as_decimal(next_data.get("received_quantity", existing.get("received_quantity")))
        new_remaining = _as_decimal(next_data.get("remaining_quantity", existing.get("remaining_quantity")))

        if new_remaining > new_received:
            raise ValidationError("remaining_quantity cannot be greater than received_quantity")

        next_data["received_quantity"] = str(new_received)
        next_data["remaining_quantity"] = str(new_remaining)
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


__all__ = [
    "MedicineBatchService",
    "MedicineTypeService",
]
